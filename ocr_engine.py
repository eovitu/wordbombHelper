"""OCR in-process via libtesseract (ctypes) — engine carregado UMA vez na RAM.

Motivação (medido jun/2026): `pytesseract.image_to_data` faz spawn de `tesseract.exe`
+ leitura do tessdata do disco A CADA chamada. Ocioso isso custa ~130ms; sob contenção
(jogo WebGL + gravador de tela) estica para 1-2s aleatoriamente. Mantendo o engine vivo
in-process via a C-API, cada leitura cai para ~5-8ms ESTÁVEL, sem subprocess, sem I/O de
disco por frame. ctypes é stdlib → sem dependência nova, funciona no Python 3.14.

Uso:
    eng = WarmTesseract(tesseract_cmd, tessdata_dir, lang="eng")
    eng.configure(psm=11, whitelist="ABC...-'")
    tokens = eng.read_tokens(gray_uint8_img)  # [(text, conf, height), ...]

Se a DLL não puder ser carregada (outro SO, build sem lib, etc.), o construtor levanta
`OcrEngineUnavailable` e o chamador deve cair para o caminho pytesseract (subprocess).
"""
import ctypes as ctypes_mod
import logging
import os
import threading

logger = logging.getLogger(__name__)

# Nível de iteração da C-API: RIL_BLOCK=0, RIL_PARA=1, RIL_TEXTLINE=2, RIL_WORD=3.
_RIL_WORD = 3


class OcrEngineUnavailable(Exception):
    """libtesseract não pôde ser localizada/carregada/inicializada."""


def _find_libtesseract(tesseract_cmd):
    """Localiza a DLL/so do libtesseract. Retorna caminho ou None."""
    candidates = []
    # 1) Ao lado do tesseract.exe (instalação típica no Windows).
    if tesseract_cmd and os.path.isfile(tesseract_cmd):
        d = os.path.dirname(tesseract_cmd)
        for name in ("libtesseract-5.dll", "libtesseract-4.dll", "libtesseract.dll"):
            candidates.append(os.path.join(d, name))
    # 2) Busca no loader do SO (Linux/Mac e PATH do Windows).
    try:
        from ctypes.util import find_library
        for base in ("tesseract", "libtesseract"):
            found = find_library(base)
            if found:
                candidates.append(found)
    except Exception:
        pass
    for c in candidates:
        if c and (os.path.isfile(c) or os.path.sep not in c):
            return c
    return None


class WarmTesseract:
    def __init__(self, tesseract_cmd, tessdata_dir, lang="eng"):
        lib_path = _find_libtesseract(tesseract_cmd)
        if not lib_path:
            raise OcrEngineUnavailable("libtesseract não encontrada")

        # No Windows, as DLLs dependentes ficam na pasta do tesseract — adiciona ao loader.
        try:
            if tesseract_cmd and os.path.isfile(tesseract_cmd) and hasattr(os, "add_dll_directory"):
                os.add_dll_directory(os.path.dirname(tesseract_cmd))
        except Exception:
            pass

        try:
            lib = ctypes_mod.CDLL(lib_path)
        except OSError as exc:
            raise OcrEngineUnavailable(f"Falha ao carregar {lib_path}: {exc}") from exc

        self._lib = lib
        self._lock = threading.Lock()
        self._img_ref = None  # mantém o buffer vivo entre SetImage e Recognize
        self._bind_signatures()

        if not os.path.isdir(tessdata_dir):
            raise OcrEngineUnavailable(f"tessdata_dir inválido: {tessdata_dir}")

        self._api = lib.TessBaseAPICreate()
        if not self._api:
            raise OcrEngineUnavailable("TessBaseAPICreate retornou NULL")

        rc = lib.TessBaseAPIInit3(self._api, tessdata_dir.encode("utf-8"), lang.encode("ascii"))
        if rc != 0:
            lib.TessBaseAPIDelete(self._api)
            raise OcrEngineUnavailable(f"TessBaseAPIInit3 falhou (rc={rc}, lang={lang})")

        # Silencia o spam "Estimating resolution as N" (vai para debug_file).
        lib.TessBaseAPISetVariable(self._api, b"debug_file", b"NUL" if os.name == "nt" else b"/dev/null")

        self.lib_path = lib_path
        logger.info("OCR in-process ativo (libtesseract: %s, lang=%s)", os.path.basename(lib_path), lang)

    def _bind_signatures(self):
        c = ctypes_mod
        sig = {
            "TessBaseAPICreate": ([], c.c_void_p),
            "TessBaseAPIDelete": ([c.c_void_p], None),
            "TessBaseAPIInit3": ([c.c_void_p, c.c_char_p, c.c_char_p], c.c_int),
            "TessBaseAPISetPageSegMode": ([c.c_void_p, c.c_int], None),
            "TessBaseAPISetVariable": ([c.c_void_p, c.c_char_p, c.c_char_p], c.c_int),
            "TessBaseAPISetImage": ([c.c_void_p, c.c_char_p, c.c_int, c.c_int, c.c_int, c.c_int], None),
            "TessBaseAPIRecognize": ([c.c_void_p, c.c_void_p], c.c_int),
            "TessBaseAPIGetIterator": ([c.c_void_p], c.c_void_p),
            "TessResultIteratorGetPageIterator": ([c.c_void_p], c.c_void_p),
            "TessResultIteratorGetUTF8Text": ([c.c_void_p, c.c_int], c.c_void_p),
            "TessResultIteratorConfidence": ([c.c_void_p, c.c_int], c.c_float),
            "TessResultIteratorNext": ([c.c_void_p, c.c_int], c.c_int),
            "TessPageIteratorBoundingBox": (
                [c.c_void_p, c.c_int, c.POINTER(c.c_int), c.POINTER(c.c_int),
                 c.POINTER(c.c_int), c.POINTER(c.c_int)], c.c_int),
            "TessResultIteratorDelete": ([c.c_void_p], None),
            "TessDeleteText": ([c.c_void_p], None),
        }
        for name, (argtypes, restype) in sig.items():
            fn = getattr(self._lib, name)
            fn.argtypes = argtypes
            if restype is not None:
                fn.restype = restype

    def configure(self, psm=11, whitelist=None):
        lib = self._lib
        lib.TessBaseAPISetPageSegMode(self._api, int(psm))
        if whitelist is not None:
            lib.TessBaseAPISetVariable(self._api, b"tessedit_char_whitelist", whitelist.encode("ascii"))

    def read_tokens(self, gray_img):
        """OCR de uma imagem grayscale (numpy uint8, 1 canal) → [(text, conf, height)]."""
        import numpy as np
        c = ctypes_mod
        if gray_img.ndim != 2:
            raise ValueError("read_tokens espera imagem grayscale 2D")
        img = np.ascontiguousarray(gray_img, dtype=np.uint8)
        h, w = img.shape

        with self._lock:
            self._img_ref = img  # impede o GC de coletar o buffer durante Recognize
            self._lib.TessBaseAPISetImage(self._api, img.ctypes.data_as(c.c_char_p), w, h, 1, w)
            self._lib.TessBaseAPIRecognize(self._api, None)

            ri = self._lib.TessBaseAPIGetIterator(self._api)
            if not ri:
                return []
            pi = self._lib.TessResultIteratorGetPageIterator(ri)
            tokens = []
            x1, y1, x2, y2 = c.c_int(), c.c_int(), c.c_int(), c.c_int()
            try:
                while True:
                    ptr = self._lib.TessResultIteratorGetUTF8Text(ri, _RIL_WORD)
                    text = ""
                    if ptr:
                        text = c.string_at(ptr).decode("utf-8", "ignore").strip()
                        self._lib.TessDeleteText(ptr)
                    if text:
                        conf = float(self._lib.TessResultIteratorConfidence(ri, _RIL_WORD))
                        if self._lib.TessPageIteratorBoundingBox(
                                pi, _RIL_WORD, c.byref(x1), c.byref(y1), c.byref(x2), c.byref(y2)):
                            height = y2.value - y1.value
                        else:
                            height = 0
                        tokens.append((text, conf, height))
                    if not self._lib.TessResultIteratorNext(ri, _RIL_WORD):
                        break
            finally:
                self._lib.TessResultIteratorDelete(ri)
                self._img_ref = None
            return tokens

    def close(self):
        try:
            if getattr(self, "_api", None):
                self._lib.TessBaseAPIDelete(self._api)
                self._api = None
        except Exception:
            pass
