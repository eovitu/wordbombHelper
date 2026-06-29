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
        # Região PRIMEIRO: se o usuário não calibrou o painel SOLVE, nem carregamos o
        # engine dedicado (~30-50MB). Pipeline B só custa recursos quando de fato em uso.
        if normalize_capture_region(self.region_store.get_region()) is None:
            return False
        return self._ensure_engine()

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
        return [tok[0] for tok in tokens if tok[0]]

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

    def __init__(self, word_manager, source, lang_getter, interval=0.75, is_active=None,
                 ambiguous_store=None):
        self.word_manager = word_manager
        self.source = source
        self.lang_getter = lang_getter          # callable -> idioma atual (str)
        self.interval = interval                # segundos entre varreduras (0.5-1.0)
        self.is_active = is_active              # callable -> só varre se True (ex: em partida)
        self.ambiguous_store = ambiguous_store  # registro de leituras ambíguas (manutenção)
        self._seen = set()                      # chaves já marcadas (dedup)
        self._thread = None
        self._stop = threading.Event()
        self._idle_warned = False
        self.learned_count = 0
        # Sincronização para catch-up dirigido por evento (Pipeline A pede um scan na hora).
        # Mantém as duas pipelines desacopladas: A só chama request_catch_up(); B faz o scan
        # na PRÓPRIA thread (mss/engine não cruzam threads).
        self._cv = threading.Condition()
        self._catch_up_flag = False
        self._scan_seq = 0
        # Log das palavras aprendidas (para exibir na tela). seq cresce sempre (mesmo após
        # reset) para o front usar high-water-mark e não re-renderizar entradas antigas.
        self._learned_log = []
        self._learned_seq = 0
        self._learned_lock = threading.Lock()

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
        with self._cv:
            self._cv.notify_all()  # acorda o laço/quem espera catch-up
        if self._thread:
            self._thread.join(timeout=1.5)
        self.source.close()

    def reset(self):
        """Esquece as palavras aprendidas (novo match)."""
        self._seen.clear()
        self.learned_count = 0
        with self._learned_lock:
            self._learned_log.clear()  # seq NÃO zera (high-water-mark do front)

    def learned_log(self, count=30):
        """Snapshot das últimas palavras aprendidas (para exibição na tela)."""
        with self._learned_lock:
            return list(self._learned_log[-count:])

    def request_catch_up(self, timeout=0.18):
        """Pipeline A chama no início do MEU turno: força um scan imediato e espera (limitado)
        ele terminar, para a palavra recém-jogada pelo oponente já estar marcada antes da
        sugestão. Retorna rápido (sem travar) se Pipeline B não estiver utilizável."""
        if self._stop.is_set():
            return
        if self.is_active and not self.is_active():
            return
        if not self.source.region_ready():   # B não configurado → não espera, não congela
            return
        with self._cv:
            target = self._scan_seq + 1
            self._catch_up_flag = True
            self._cv.notify_all()
            self._cv.wait_for(lambda: self._scan_seq >= target or self._stop.is_set(),
                              timeout=timeout)

    def _wait_next(self, timeout):
        """Dorme até o intervalo OU até um pedido de catch-up (o que vier primeiro)."""
        with self._cv:
            self._cv.wait_for(lambda: self._catch_up_flag or self._stop.is_set(), timeout=timeout)

    def _scan_and_learn(self):
        words = self.source.poll()
        lang = self.lang_getter() if self.lang_getter else None
        for raw in words:
            key = self.word_manager.normalize_token(raw)
            if not key or len(key) < 2 or key in self._seen:
                continue
            self._seen.add(key)  # marca como vista mesmo se não casar (evita reprocesso)
            try:
                status, canonical = self.word_manager.resolve_played_ocr(raw, lang)
                if status == "marked":
                    self.learned_count += 1
                    with self._learned_lock:
                        self._learned_seq += 1
                        self._learned_log.append({"id": self._learned_seq, "word": canonical})
                        if len(self._learned_log) > 50:
                            self._learned_log.pop(0)
                elif status == "ambiguous" and self.ambiguous_store:
                    # Conservador: não marcamos. Registramos p/ o usuário revisar depois.
                    self.ambiguous_store.record(key)
            except Exception as exc:
                logger.debug("Pipeline B: erro ao resolver '%s' (%s)", key, exc)
        # Sinaliza conclusão deste scan (acorda quem pediu catch-up).
        with self._cv:
            self._scan_seq += 1
            self._catch_up_flag = False
            self._cv.notify_all()

    def _run(self):
        while not self._stop.is_set():
            try:
                if self.is_active and not self.is_active():
                    self._wait_next(0.5)  # fora de partida: não captura nada
                    continue
                if not self.source.available():
                    if not self._idle_warned:
                        logger.info("Pipeline B ocioso (engine ou região indisponível) — "
                                    "calibre o painel SOLVE para ativar.")
                        self._idle_warned = True
                    self._wait_next(1.0)
                    continue
                self._idle_warned = False
                self._scan_and_learn()
            except Exception as exc:
                logger.error("Pipeline B: erro no laço (%s)", exc)
            self._wait_next(self.interval)
