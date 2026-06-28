"""Pipeline B — aprendizado assíncrono de palavras já jogadas (independente do Pipeline A).

Objetivo: ler o painel SOLVE (da extensão Room Inspector) num ritmo BAIXO (500-1000ms),
numa thread DEDICADA, com engine OCR e captura mss PRÓPRIOS, e marcar as palavras válidas
(verdes) como usadas no WordManager — sem nunca tocar na latência do OCR do prompt.

Princípios:
- Totalmente isolado: thread própria, WarmTesseract próprio, mss próprio.
- Opcional: se o engine não carrega ou a região não está calibrada, o scanner se
  AUTODESATIVA silenciosamente; o resto do app continua normal.
- Modular: a fonte de palavras é abstraída em `UsedWordSource`, então a leitura via OCR
  pode ser trocada no futuro (DOM/WS/etc.) sem mexer no laço do scanner.
- Só marca palavras VERDES: isolamos o texto verde por máscara HSV antes do OCR, então
  palavras inválidas (vermelhas) nem chegam ao Tesseract.
"""
import logging
import threading

import cv2
import mss
import numpy as np

from ocr_engine import WarmTesseract, OcrEngineUnavailable
from shared.parsing import normalize_capture_region

logger = logging.getLogger(__name__)

_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-'"


class UsedWordSource:
    """Interface de fonte de palavras-usadas. Implementações devem ser trocáveis."""

    def available(self):
        raise NotImplementedError

    def poll(self):
        """Retorna a lista de palavras (cruas) visíveis agora. Pode conter duplicatas."""
        raise NotImplementedError

    def close(self):
        pass


class OcrSolvePanelSource(UsedWordSource):
    """Fonte via OCR do painel SOLVE: máscara de verde → OCR in-process (engine próprio)."""

    def __init__(self, region_store, tesseract_cmd, tessdata_dir):
        self.region_store = region_store
        self._tesseract_cmd = tesseract_cmd
        self._tessdata = tessdata_dir
        self._engine = None
        self._engine_tried = False
        self._engine_ok = False
        self._engine_lock = threading.Lock()
        self._sct = None  # mss próprio, criado lazy NA thread do scanner
        # Faixa HSV do texto verde (palavra válida). Ajustável.
        self.green_lower = np.array([35, 60, 70])
        self.green_upper = np.array([90, 255, 255])
        self.min_green_pixels = 30
        self.upscale = 2.0

    def region_ready(self):
        """Checagem barata (sem inicializar engine) se a região SOLVE está calibrada."""
        return normalize_capture_region(self.region_store.get_region()) is not None

    def _ensure_engine(self):
        if self._engine_tried:
            return self._engine_ok
        with self._engine_lock:
            if self._engine_tried:
                return self._engine_ok
            return self._init_engine_locked()

    def _init_engine_locked(self):
        self._engine_tried = True
        try:
            self._engine = WarmTesseract(self._tesseract_cmd, self._tessdata, lang="eng")
            # psm 6 = bloco uniforme: lê a lista de palavras (uma por linha) sem busca esparsa cara.
            self._engine.configure(psm=6, whitelist=_WHITELIST)
            self._engine_ok = True
            logger.info("Pipeline B: engine OCR dedicado pronto")
        except OcrEngineUnavailable as exc:
            logger.warning("Pipeline B desativado: OCR indisponível (%s)", exc)
            self._engine_ok = False
        return self._engine_ok

    def available(self):
        if not self._ensure_engine():
            return False
        return normalize_capture_region(self.region_store.get_region()) is not None

    def poll(self):
        coords = normalize_capture_region(self.region_store.get_region())
        if not coords or not self._engine_ok:
            return []
        if self._sct is None:
            self._sct = mss.mss()  # criado lazy NA thread do scanner (mss não é thread-safe)
        monitor = {"top": coords["y1"], "left": coords["x1"],
                   "width": coords["width"], "height": coords["height"]}
        if monitor["width"] < 8 or monitor["height"] < 8:
            return []
        sct_img = self._sct.grab(monitor)
        # frombuffer direto (sem cópia bytes()): cvtColor já produz o array de trabalho.
        img_bgr = np.frombuffer(sct_img.raw, dtype=np.uint8).reshape(
            sct_img.height, sct_img.width, 4)
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2BGR)

        # Isola SÓ o texto verde (palavras válidas). Vermelho/branco/cinza são descartados.
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.green_lower, self.green_upper)
        if cv2.countNonZero(mask) < self.min_green_pixels:
            return []  # painel vazio / sem palavras válidas no momento

        if self.upscale > 1.01:
            mask = cv2.resize(mask, None, fx=self.upscale, fy=self.upscale,
                              interpolation=cv2.INTER_LINEAR)
        proc = cv2.bitwise_not(mask)  # texto preto em fundo branco para o Tesseract

        try:
            tokens = self._engine.read_tokens(proc)
        except Exception as exc:
            logger.debug("Pipeline B: falha de leitura (%s)", exc)
            return []
        return [t for (t, _conf, _h) in tokens if t]

    def close(self):
        try:
            if self._sct is not None:
                self._sct.close()
        except Exception:
            pass
        try:
            if self._engine is not None:
                self._engine.close()
        except Exception:
            pass


class UsedWordScanner:
    """Laço de fundo que aprende palavras já jogadas e as marca no WordManager."""

    def __init__(self, word_manager, source, lang_getter, interval=0.75, is_active=None):
        self.word_manager = word_manager
        self.source = source
        self.lang_getter = lang_getter          # callable -> idioma atual (str)
        self.interval = interval                # segundos entre varreduras (0.5-1.0)
        self.is_active = is_active              # callable -> só varre se True (ex: em partida)
        self._seen = set()                      # chaves já marcadas (dedup)
        self._thread = None
        self._stop = threading.Event()
        self._idle_warned = False
        self.learned_count = 0

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="UsedWordScanner")
        self._thread.start()
        logger.info("Pipeline B: scanner de palavras-usadas iniciado (intervalo=%.0fms)",
                    self.interval * 1000)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.5)
        self.source.close()

    def reset(self):
        """Esquece as palavras aprendidas (novo match)."""
        self._seen.clear()
        self.learned_count = 0

    def _run(self):
        while not self._stop.is_set():
            try:
                if self.is_active and not self.is_active():
                    self._stop.wait(0.5)  # fora de partida: não captura nada
                    continue
                if not self.source.available():
                    if not self._idle_warned:
                        logger.info("Pipeline B ocioso (engine ou região indisponível) — "
                                    "calibre o painel SOLVE para ativar.")
                        self._idle_warned = True
                    self._stop.wait(1.0)
                    continue
                self._idle_warned = False

                words = self.source.poll()
                lang = self.lang_getter() if self.lang_getter else None
                for raw in words:
                    key = self.word_manager.normalize_token(raw)
                    if not key or len(key) < 2 or key in self._seen:
                        continue
                    self._seen.add(key)  # marca como vista mesmo se não casar (evita reprocesso)
                    try:
                        if self.word_manager.mark_used_ocr(raw, lang):
                            self.learned_count += 1
                            logger.debug("Pipeline B: '%s' marcada como usada", key)
                    except Exception as exc:
                        logger.debug("Pipeline B: erro ao marcar '%s' (%s)", key, exc)
            except Exception as exc:
                logger.error("Pipeline B: erro no laço (%s)", exc)
            self._stop.wait(self.interval)
