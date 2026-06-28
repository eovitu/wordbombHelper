"""ScreenReader — captura de tela + OCR para detectar turno e sílaba no WordBomb."""
import os
import shutil
import threading
import time
import logging

import cv2
import mss
import numpy as np
import pytesseract
from PIL import Image
from pynput import mouse
import platform

from shared.parsing import normalize_capture_region
from ocr_engine import WarmTesseract, OcrEngineUnavailable

logger = logging.getLogger(__name__)

# ── Tesseract path ──────────────────────────────────────────────────────────
if platform.system() == "Windows":
    _win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    pytesseract.pytesseract.tesseract_cmd = _win if os.path.isfile(_win) else (shutil.which("tesseract") or "tesseract")
else:
    for _p in ("/usr/bin/tesseract", "/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract"):
        if os.path.isfile(_p):
            pytesseract.pytesseract.tesseract_cmd = _p
            break
    else:
        pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract") or "tesseract"

# tessdata empacotado no projeto. Usamos TESSDATA_PREFIX em vez de --tessdata-dir
# porque pytesseract quebra o config nos espaços do caminho.
_BUNDLED_TESSDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tessdata")
if os.path.isdir(_BUNDLED_TESSDATA):
    os.environ["TESSDATA_PREFIX"] = _BUNDLED_TESSDATA

# Config OCR: legacy engine (oem 0) é 2-4x mais rápido que LSTM para texto simples.
# psm 11 = sparse text: encontra todas as palavras (sílaba + "SUA VEZ") sem assumir layout.
# Whitelist inclui hífen e apóstrofe para ler prompts como M-V e PA'U corretamente.
# Fallback para oem 3 (auto) se tessdata não tiver modelo legacy.
_OCR_CONFIG_FAST = "--oem 0 --psm 11 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-' "
_OCR_CONFIG_FALLBACK = "--oem 3 --psm 11 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-' "

# Whitelist (só os chars) para o engine in-process via C-API.
_OCR_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-'"
_OCR_PSM = 11  # sparse text: encontra sílaba + "SUA VEZ" como tokens separados


class ScreenReader:
    def __init__(self, autoplay_state=None, callback_found_word=None):
        self.autoplay_state = autoplay_state
        self.callback_found_word = callback_found_word

        # Calibração
        self.turn_region = None
        self.prompt_region = None

        # Estado
        self.is_watching = False
        self.status = "Idle"
        self.calibration_step = None
        self.temp_points = []

        self.thread = None
        self.stop_event = threading.Event()

        self.mouse_listener = None
        self.log_callback = None
        self.on_region_calibrated = None
        # Calibração de uma 2ª região (painel SOLVE / Pipeline B). Não afeta o Pipeline A.
        self.on_solve_region_calibrated = None
        self._calib_target = "turn"

        # Runtime state
        self.last_word_typed = ""
        self.suggested_word = ""
        self.preview_prompt = ""
        self.last_suggested_prompt = ""

        # ── Parâmetros de detecção ───────────────────────────────────────────
        self.turn_keywords = ["SUA VEZ", "SUAVEZ", "VEZ", "YOUR TURN", "YOURTURN", "TURN", "YOUR", "SUA"]

        # Pixels brancos mínimos para considerar que há conteúdo (early-exit barato).
        self.min_white_pixels = 40

        # Tamanho aceitável da sílaba (prompt).
        self.min_prompt_len = 2
        self.max_prompt_len = 6  # até 6 para prompts com hífen/apóstrofe (ex: m-v, pa'u)

        # Altura mínima (px) do token na imagem escalada para ser candidato a prompt.
        # Prompts reais: 40-90px. "SUA VEZ": ~18px. Ruído: 4-22px.
        # 35px exclui mais ruído sem risco: prompts reais têm folga acima desse valor.
        self.min_prompt_height = 35

        # Confiança mínima para aceitar a sílaba.
        self.prompt_conf_threshold = 45.0

        # Confiança para aceitar no 1º frame sem aguardar 2ª leitura.
        # Leitura limpa do prompt tem conf alta (>70) → aceita na hora (latência mínima).
        # Leitura instável/garbage tem conf menor → exige 2 frames idênticos (anti-flash).
        # Isto resolve o "4 prompts errados rapidão" SEM dobrar a latência do caso comum:
        # o garbage transitório raramente repete E raramente tem conf alta.
        self.instant_accept_conf = 70.0

        # Debounce de fim de turno: 1 frame sem keyword encerra (sem pisca-pisca graças
        # ao frame-hash — frames idênticos não são reprocessados).
        self.turn_off_misses = 1

        # ── Estabilidade temporal do prompt (lock/hysteresis) ────────────────
        # Depois que um prompt é comprometido (mostrado), ele fica TRAVADO. Uma leitura
        # DIFERENTE (de animação/texto digitado/ruído) só rouba o lock se aparecer de forma
        # consistente por N frames seguidos. Oclusão transitória (prompt sumir 1-2 frames)
        # NÃO solta o lock — só o fim do turno ou um prompt novo confirmado.
        self.switch_confirm_frames = 3   # frames seguidos de um prompt novo p/ trocar o lock
        self.unlock_absent_frames = 25   # salvaguarda: solta lock se sumir por MUITOS frames
        self._challenger = ""            # candidato != lock juntando evidência p/ trocar
        self._challenger_streak = 0
        self._absent_streak = 0          # frames sem prompt válido com o lock ativo

        # Largura máxima (px) da imagem enviada ao OCR.
        # Em turno: 2x para máxima legibilidade da sílaba.
        # Fora do turno: 1.5x é suficiente para "SUA VEZ" e gera 44% menos pixels → OCR mais rápido.
        self.ocr_max_width = 1600          # cap quando é nosso turno
        self.ocr_max_width_keyword = 1200  # cap quando procura keyword (fora do turno)

        # Modo debug OCR: salva last_processed.png em debug_screenshots/ quando ativo.
        self.save_debug_screenshots = os.getenv("WORDBOMB_OCR_DEBUG", "").strip() in ("1", "true", "True", "yes")
        self._debug_dir = os.path.join(os.getcwd(), "debug_screenshots")

        # OCR in-process (libtesseract via ctypes): ~5-8ms estável, sem subprocess.
        # Inicializado lazy na 1ª leitura. Se a DLL não carregar, cai para pytesseract.
        self._warm_ocr = None
        self._warm_ocr_tried = False
        self._warm_ocr_init_lock = threading.Lock()

        # Fallback subprocess: tenta oem 0 (legacy/rápido); cai para oem 3 se falhar.
        self._ocr_config = _OCR_CONFIG_FAST
        self._ocr_config_verified = False  # testado na primeira leitura
        self._first_ocr_done = False       # diagnóstico de velocidade na 1ª chamada

        # Caches internos
        self._last_frame_hash = None
        self._last_capture_result = ("", None, False)
        self._last_is_my_turn = False
        self._last_prompt_conf = -1.0
        self._turn_confirm_streak = 0
        self._turn_miss_streak = 0
        self._prompt_confirm_streak = 0
        self._last_prompt_candidate = ""

        # Palavras de UI que o OCR pode ler mas não são o prompt.
        self._UI_KEYWORDS = {
            "SUA", "VEZ", "SUAVEZ", "YOUR", "TURN", "YOURTURN",
            "VE2", "UEZ", "VAR", "SORA", "BANE", "SOLO",
            "NOVO", "NOVA",
        }

        # Máx de tentativas antes de desistir de um prompt rejeitado.
        self.max_retries = 5

    # ── Logging ─────────────────────────────────────────────────────────────

    def set_callback(self, callback):
        self.callback_found_word = callback

    def set_log_callback(self, callback):
        self.log_callback = callback

    def _log(self, msg):
        logger.info(msg)
        if self.log_callback:
            try:
                self.log_callback(msg)
            except Exception:
                pass

    # ── OCR core ────────────────────────────────────────────────────────────

    @staticmethod
    def _clean_ocr_token(text):
        # Preserva hífen e apóstrofe para ler prompts como M-V e PA'U corretamente.
        return "".join(ch for ch in (text or "") if ch.isalpha() or ch in "-'").upper()

    def _ensure_warm_ocr(self):
        """Inicializa o engine in-process na 1ª chamada. Idempotente e thread-safe."""
        if self._warm_ocr_tried:
            return
        with self._warm_ocr_init_lock:
            if self._warm_ocr_tried:  # double-check sob lock
                return
            try:
                tessdata = os.environ.get("TESSDATA_PREFIX", _BUNDLED_TESSDATA)
                self._warm_ocr = WarmTesseract(
                    pytesseract.pytesseract.tesseract_cmd, tessdata, lang="eng")
                self._warm_ocr.configure(psm=_OCR_PSM, whitelist=_OCR_WHITELIST)
            except OcrEngineUnavailable as exc:
                logger.warning("OCR in-process indisponível (%s) — usando pytesseract "
                               "(subprocess, mais lento e sujeito a stalls)", exc)
                self._warm_ocr = None
            finally:
                self._warm_ocr_tried = True

    def _get_ocr_tokens(self, gray_img):
        """Retorna [(text, conf, height)] via engine in-process, com fallback subprocess."""
        self._ensure_warm_ocr()
        if self._warm_ocr is not None:
            try:
                return self._warm_ocr.read_tokens(gray_img)
            except Exception as exc:
                logger.error("OCR in-process falhou (%s) — desativando, fallback subprocess", exc)
                self._warm_ocr = None
        return self._pytesseract_tokens(gray_img)

    def _pytesseract_tokens(self, gray_img):
        """Caminho legado: pytesseract via subprocess. Retorna [(text, conf, height)]."""
        pil_img = Image.fromarray(gray_img)
        try:
            data = pytesseract.image_to_data(
                pil_img, lang="eng", config=self._ocr_config,
                output_type=pytesseract.Output.DICT)
        except Exception as exc:
            if not self._ocr_config_verified and self._ocr_config == _OCR_CONFIG_FAST:
                logger.warning("oem 0 falhou (%s) — usando oem 3 (LSTM)", exc)
                self._ocr_config = _OCR_CONFIG_FALLBACK
                try:
                    data = pytesseract.image_to_data(
                        pil_img, lang="eng", config=self._ocr_config,
                        output_type=pytesseract.Output.DICT)
                except Exception:
                    return []
            else:
                return []
        self._ocr_config_verified = True
        texts = data.get("text", [])
        confs = data.get("conf", [])
        heights = data.get("height", [])
        out = []
        for i, txt in enumerate(texts):
            if not (txt or "").strip():
                continue
            try:
                conf = float(confs[i])
            except (TypeError, ValueError, IndexError):
                conf = -1.0
            try:
                height = int(heights[i])
            except (TypeError, ValueError, IndexError):
                height = 0
            out.append((txt, conf, height))
        return out

    def _read_prompt_and_turn(self, gray_img):
        """Uma leitura de OCR → (sílaba, confiança, keyword_turno_detectada).

        Detecta sílaba (maior token na tela, excluindo UI) e se "SUA VEZ"/"TURN"
        está presente, numa única passada sobre os tokens do Tesseract.
        """
        raw_tokens = self._get_ocr_tokens(gray_img)

        tokens = []
        best_candidate, best_confidence, best_height = "", -1.0, -1

        for txt, conf_val, height in raw_tokens:
            clean = self._clean_ocr_token(txt)
            if not clean:
                continue
            tokens.append(clean)

            if clean in self._UI_KEYWORDS:
                continue
            if not (self.min_prompt_len <= len(clean) <= self.max_prompt_len):
                continue
            # Garbage filter: tokens muito pequenos são ruído (ex: noise de renderização).
            # Prompts reais têm height >= 40px na imagem 2x; "SUA VEZ" tem ~18px.
            if height < self.min_prompt_height:
                continue

            # Sílaba = maior token na tela (altura de fonte), confiança como desempate.
            if height > best_height or (height == best_height and conf_val > best_confidence):
                best_candidate, best_confidence, best_height = clean.lower(), conf_val, height

        # joined sem hífen/apóstrofe para não quebrar keyword detection se OCR ler "SUA-VEZ".
        joined_alpha = "".join(ch for ch in "".join(tokens) if ch.isalpha())
        keyword_detected = any(kw.replace(" ", "").replace("-", "").replace("'", "") in joined_alpha
                               for kw in self.turn_keywords)

        if tokens:
            logger.debug("OCR tokens: %s | keyword=%s | candidato=%r conf=%.1f",
                         tokens, keyword_detected, best_candidate, best_confidence)

        return best_candidate, best_confidence, keyword_detected

    # ── Captura + processamento ──────────────────────────────────────────────

    def _capture_and_ocr(self, sct):
        """Captura a região calibrada e devolve (candidato, prompt, is_my_turn)."""
        coords = normalize_capture_region(self.turn_region)
        if not coords:
            logger.warning("Região de captura inválida — recalibre.")
            return None, None, False

        monitor = {
            "top": coords["y1"],
            "left": coords["x1"],
            "width": coords["width"],
            "height": coords["height"],
        }
        if monitor["width"] < 8 or monitor["height"] < 8:
            logger.warning("Região de captura muito pequena — recalibre.")
            return None, None, False

        sct_img = sct.grab(monitor)

        # Frame cache: pula pipeline caro se a tela não mudou.
        raw_bytes = bytes(sct_img.raw)
        frame_hash = hash(raw_bytes)
        if self._last_frame_hash is not None and frame_hash == self._last_frame_hash:
            return self._last_capture_result

        # BGRA → BGR
        img_bgr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(sct_img.height, sct_img.width, 4)
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2BGR)

        # Remove borda do overlay (evita captar moldura vermelha).
        border_px = 12
        if img_bgr.shape[0] > border_px * 2 and img_bgr.shape[1] > border_px * 2:
            img_bgr = img_bgr[border_px:-border_px, border_px:-border_px]

        # Early-exit barato: quase sem pixels brancos = lobby/entre rodadas.
        # V >= 200 (era 180): threshold mais alto → menos ruído capturado → imagem mais limpa
        # → LSTM processa menos pixels → OCR mais rápido. "SUA VEZ" continua capturado (V≈255).
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 60, 255])
        hsv_small = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        white_count = cv2.countNonZero(cv2.inRange(hsv_small, lower_white, upper_white))
        if white_count <= self.min_white_pixels:
            res = ("", None, False)
            self._last_capture_result = res
            self._last_frame_hash = frame_hash
            return res

        # Escala adaptativa: fora do turno usa 1.5x max (44% menos pixels → OCR mais rápido
        # para detectar "SUA VEZ"). Dentro do turno usa 2x para máxima legibilidade da sílaba.
        h0, w0 = img_bgr.shape[:2]
        max_w = self.ocr_max_width if self._turn_confirm_streak >= 1 else self.ocr_max_width_keyword
        scale = min(2.0, max_w / w0) if w0 > 0 else 2.0
        scale = max(1.0, scale)
        if scale > 1.01:
            img_large = cv2.resize(img_bgr, (int(w0 * scale), int(h0 * scale)), interpolation=cv2.INTER_LINEAR)
        else:
            img_large = img_bgr

        # Isola texto branco → imagem binária preto-no-branco para o Tesseract.
        hsv_full = cv2.cvtColor(img_large, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv_full, lower_white, upper_white)
        _, proc = cv2.threshold(cv2.bitwise_not(mask), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        if self.save_debug_screenshots:
            try:
                os.makedirs(self._debug_dir, exist_ok=True)
                cv2.imwrite(os.path.join(self._debug_dir, "last_processed.png"), proc)
            except Exception as e:
                logger.error("Falha ao salvar debug screenshot: %s", e)

        _t0 = time.perf_counter()
        candidate, candidate_conf, keyword_detected = self._read_prompt_and_turn(proc)
        ocr_ms = (time.perf_counter() - _t0) * 1000.0

        # Diagnóstico na 1ª chamada: confirma se o engine in-process está ativo.
        if not self._first_ocr_done:
            self._first_ocr_done = True
            engine = "in-process(ctypes)" if self._warm_ocr is not None else "subprocess(pytesseract)"
            logger.info("Primeiro OCR: %.0fms | img=%dx%d | engine=%s",
                        ocr_ms, img_large.shape[1], img_large.shape[0], engine)
            if self._warm_ocr is None and ocr_ms > 600:
                logger.warning(
                    "OCR lento (%.0fms) via subprocess — engine in-process não carregou. "
                    "Verifique libtesseract na pasta do Tesseract.", ocr_ms)

        # ── Detecção de turno com debounce ─────────────────────────────────
        if keyword_detected:
            self._turn_confirm_streak += 1
            self._turn_miss_streak = 0
        else:
            self._turn_miss_streak += 1
            if self._turn_miss_streak >= self.turn_off_misses:
                self._turn_confirm_streak = 0
        is_my_turn = self._turn_confirm_streak >= 1

        # ── Sílaba ─────────────────────────────────────────────────────────
        prompt_text = None
        if is_my_turn and candidate:
            is_ghost = bool(
                self.last_word_typed
                and self.last_word_typed.lower().endswith(candidate)
                and not keyword_detected
            )
            validation_ok = candidate_conf >= self.prompt_conf_threshold or keyword_detected
            if not is_ghost and validation_ok:
                prompt_text = candidate
            else:
                logger.debug("Prompt rejeitado: %r (conf=%.1f, keyword=%s, ghost=%s)",
                             candidate, candidate_conf, keyword_detected, is_ghost)

        self._last_prompt_conf = candidate_conf if prompt_text else -1.0

        logger.debug(
            "OCR %.0fms | img=%dx%d | white=%d | keyword=%s | conf_streak=%d miss=%d "
            "| my_turn=%s | candidato=%r conf=%.1f → prompt=%r",
            ocr_ms, img_large.shape[1], img_large.shape[0],
            white_count, keyword_detected, self._turn_confirm_streak, self._turn_miss_streak,
            bool(is_my_turn), candidate, candidate_conf, prompt_text,
        )

        payload = (candidate, prompt_text, bool(is_my_turn))
        self._last_capture_result = payload
        self._last_frame_hash = frame_hash
        return payload

    # ── Máquina de estados do prompt (lock/hysteresis) ───────────────────────

    def _commit_prompt(self, prompt_text):
        """Compromete um prompt novo: trava nele, loga e dispara a busca da palavra.
        Chamado só em aquisição inicial ou troca confirmada — nunca por leitura transitória."""
        self.last_suggested_prompt = prompt_text
        self.preview_prompt = prompt_text
        self._challenger = ""
        self._challenger_streak = 0
        self._absent_streak = 0
        self._prompt_confirm_streak = 0
        self._last_prompt_candidate = prompt_text
        self._last_frame_hash = None  # força leitura fresca no próximo frame
        # Não logamos "Prompt:" aqui — o callback (word_service) já o faz, evitando duplicata.
        if self.callback_found_word:
            return self.callback_found_word(prompt_text)
        return None

    def _maybe_autotype(self, prompt_text, sct):
        """Loop de re-tentativa do auto-type (só roda se config auto_type=True).
        A 1ª digitação já saiu via callback em _commit_prompt; aqui verificamos se a
        palavra foi aceita e, se o prompt continua igual, tentamos outra."""
        if not (self.autoplay_state and self.autoplay_state.snapshot_config().get("auto_type", False)):
            return
        retries = 0
        while retries < self.max_retries and not self.stop_event.is_set():
            time.sleep(0.3)  # aguarda digitação + processamento do jogo
            self._last_frame_hash = None
            _, new_prompt, still_my_turn = self._capture_and_ocr(sct)
            if not still_my_turn:
                self._log("Palavra aceita! Aguardando próximo turno...")
                break
            if not new_prompt or new_prompt != prompt_text:
                self._log("Prompt mudou/sumiu — re-escaneando...")
                break
            retries += 1
            self._log(f"Prompt '{prompt_text}' ainda visível, tentando outra palavra... ({retries + 1})")
            if self.callback_found_word and not self.callback_found_word(prompt_text):
                self._log(f"Nenhuma palavra para '{prompt_text}', desistindo.")
                break

    def _clear_prompt_lock(self):
        """Solta o lock e limpa a sugestão (fim de turno ou prompt realmente sumiu)."""
        had_lock = bool(self.last_suggested_prompt or self.suggested_word)
        self.last_suggested_prompt = ""
        self.preview_prompt = ""
        self.suggested_word = ""
        self._challenger = ""
        self._challenger_streak = 0
        self._absent_streak = 0
        self._prompt_confirm_streak = 0
        self._last_prompt_candidate = ""
        if had_lock and self.callback_found_word:
            self.callback_found_word("")

    # ── Watch loop ──────────────────────────────────────────────────────────

    def _watch_loop(self):
        with mss.mss() as sct:
            while not self.stop_event.is_set():
                try:
                    full_text, prompt_text, is_my_turn = self._capture_and_ocr(sct)

                    if full_text is None:
                        time.sleep(0.5)
                        continue

                    # Loga apenas transições de turno.
                    if is_my_turn != self._last_is_my_turn:
                        self._log("Turno detectado (SUA VEZ)" if is_my_turn else "Turno encerrado")
                        self._last_is_my_turn = is_my_turn

                    if not is_my_turn:
                        if self.last_suggested_prompt or self.suggested_word:
                            self._clear_prompt_lock()
                        time.sleep(0.08)  # polling relaxado fora do turno
                        continue

                    # ── É nossa vez: máquina de estados com lock/hysteresis ──
                    locked = self.last_suggested_prompt

                    # (1) Nenhum candidato válido neste frame.
                    if not prompt_text:
                        if locked:
                            # Mantém o lock: oclusão transitória (bomba/animação cobrindo o
                            # prompt) NÃO é evidência de mudança. Só solta após muitos frames.
                            self._absent_streak += 1
                            if self._absent_streak >= self.unlock_absent_frames:
                                self._log("Prompt ausente por muitos frames — soltando lock.")
                                self._clear_prompt_lock()
                        else:
                            self._prompt_confirm_streak = 0
                            self._last_prompt_candidate = ""
                        continue

                    # (2) Reafirmação: mesma sílaba já travada → mantém, poupa CPU.
                    if locked and prompt_text == locked:
                        self._absent_streak = 0
                        self._challenger = ""
                        self._challenger_streak = 0
                        self.preview_prompt = prompt_text
                        time.sleep(0.04)  # estável: não gasta CPU à toa, segue responsivo
                        continue

                    # (3) Aquisição inicial (ainda sem lock).
                    if not locked:
                        if prompt_text == self._last_prompt_candidate:
                            self._prompt_confirm_streak += 1
                        else:
                            self._last_prompt_candidate = prompt_text
                            self._prompt_confirm_streak = 1
                        high_conf = self._last_prompt_conf >= self.instant_accept_conf
                        if self._prompt_confirm_streak < 2 and not high_conf:
                            continue  # sinal fraco: confirma no 2º frame antes de travar
                        self._commit_prompt(prompt_text)
                        self._maybe_autotype(prompt_text, sct)
                        continue

                    # (4) Desafio ao lock: sílaba DIFERENTE da travada.
                    # Só rouba o lock se o desafiante repetir switch_confirm_frames seguidos —
                    # leitura transitória de animação/texto digitado é ignorada.
                    self._absent_streak = 0
                    if prompt_text == self._challenger:
                        self._challenger_streak += 1
                    else:
                        self._challenger = prompt_text
                        self._challenger_streak = 1
                    if self._challenger_streak >= self.switch_confirm_frames:
                        self._log(f"Prompt mudou: '{locked}' → '{prompt_text}' "
                                  f"(confirmado {self._challenger_streak}x)")
                        self._commit_prompt(prompt_text)
                        self._maybe_autotype(prompt_text, sct)
                    # senão: ignora a leitura transitória, mantém lock e UI estáveis.

                except Exception as e:
                    logger.error("Erro no watch loop: %s", e)
                    time.sleep(1)

    # ── Calibração ──────────────────────────────────────────────────────────

    def update_region_from_overlay(self, region_data):
        coords = normalize_capture_region({
            "x1": region_data.get("x1"),
            "y1": region_data.get("y1"),
            "width": region_data.get("width"),
            "height": region_data.get("height"),
        })
        if not coords:
            logger.error("Região inválida do overlay: %s", region_data)
            return
        self.turn_region = coords
        self.prompt_region = self.turn_region
        if not self.is_watching:
            self.start_watching()

    def start_calibration(self, target="turn"):
        self._calib_target = "solve" if target == "solve" else "turn"
        self.status = "Calibrating"
        self.calibration_step = "turn_start"
        self.temp_points = []
        if self.mouse_listener:
            self.mouse_listener.stop()
        self.mouse_listener = mouse.Listener(on_click=self._on_click)
        self.mouse_listener.start()
        alvo = "painel SOLVE (palavras dos jogadores)" if self._calib_target == "solve" else "prompt + SUA VEZ"
        logger.info("Calibração iniciada (%s) — clique no canto superior-esquerdo de: %s",
                    self._calib_target, alvo)

    def stop_calibration(self):
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        if self.status == "Calibrating":
            self.status = "Idle"
            self.calibration_step = None

    def _on_click(self, x, y, button, pressed):
        if not pressed:
            return
        result = self.handle_calibration_click(x, y)
        logger.info("Click de calibração processado: %s", result)
        if result["status"] == "done":
            self.stop_calibration()

    def handle_calibration_click(self, x, y):
        if self.status != "Calibrating":
            return {"status": "error", "message": "Não está em modo de calibração"}
        try:
            x, y = int(round(float(x))), int(round(float(y)))
        except (TypeError, ValueError):
            return {"status": "error", "message": "Coordenadas inválidas"}

        logger.info("Click de calibração em (%d, %d), step=%s", x, y, self.calibration_step)

        if self.calibration_step == "turn_start":
            self.temp_points = [(x, y)]
            self.calibration_step = "turn_end"
            return {"status": "next", "message": "Clique no canto inferior-direito", "step": "turn_end"}

        if self.calibration_step == "turn_end":
            sx, sy = self.temp_points[0]
            region = self._normalize_rect(sx, sy, x, y)
            target = self._calib_target
            self.temp_points = []
            self.status = "Idle"
            self.calibration_step = None
            self._calib_target = "turn"

            if target == "solve":
                # Pipeline B: região do painel SOLVE. NÃO mexe no Pipeline A.
                if self.on_solve_region_calibrated:
                    try:
                        self.on_solve_region_calibrated(region)
                    except Exception as e:
                        logger.error("Falha ao persistir região do painel SOLVE: %s", e)
                logger.info("Calibração do painel SOLVE concluída. Região: %s", region)
                return {"status": "done", "target": "solve", "message": "Painel SOLVE calibrado!", "regions": self.get_state()}

            self.turn_region = region
            self.prompt_region = region
            if self.on_region_calibrated:
                try:
                    self.on_region_calibrated(region)
                except Exception as e:
                    logger.error("Falha ao persistir região calibrada: %s", e)

            logger.info("Calibração concluída. Região: %s", region)
            return {"status": "done", "target": "turn", "message": "Calibração concluída!", "regions": self.get_state()}

        return {"status": "error", "message": "Step desconhecido"}

    @staticmethod
    def _normalize_rect(x1, y1, x2, y2):
        return {
            "x1": int(min(x1, x2)),
            "y1": int(min(y1, y2)),
            "x2": int(max(x1, x2)),
            "y2": int(max(y1, y2)),
            "width": int(abs(x2 - x1)),
            "height": int(abs(y2 - y1)),
        }

    # ── Controle do loop ────────────────────────────────────────────────────

    def toggle_watching(self):
        if self.is_watching:
            self.stop_watching()
            return False
        if not normalize_capture_region(self.turn_region) or not normalize_capture_region(self.prompt_region):
            logger.error("Não é possível iniciar: região não calibrada")
            return False
        self.start_watching()
        return True

    def _prewarm_ocr(self):
        """Inicializa o engine in-process e faz uma leitura dummy antes do 1º turno.
        Tira o custo de init (~carga do tessdata) do caminho crítico.
        """
        try:
            self._ensure_warm_ocr()
            blank = np.full((40, 120), 255, dtype=np.uint8)
            self._read_prompt_and_turn(blank)
            engine = "in-process(ctypes)" if self._warm_ocr is not None else "subprocess(pytesseract)"
            logger.info("OCR pré-aquecido (%s)", engine)
        except Exception as e:
            logger.debug("Pré-aquecimento OCR ignorado: %s", e)

    def start_watching(self):
        if self.is_watching:
            return
        self.is_watching = True
        self.status = "Watching"
        self.stop_event.clear()
        # Pré-aquece tessdata em background — não bloqueia o start.
        threading.Thread(target=self._prewarm_ocr, daemon=True).start()
        self.thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.thread.start()
        logger.info("Iniciou monitoramento de tela")

    def stop_watching(self):
        if not self.is_watching:
            return
        self.is_watching = False
        self.status = "Idle"
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("Parou monitoramento de tela")

    # ── Estado público ──────────────────────────────────────────────────────

    def get_state(self):
        return {
            "status": self.status,
            "is_watching": self.is_watching,
            "calibration_step": self.calibration_step,
            "calib_target": self._calib_target,
            "regions_set": bool(self.turn_region and self.prompt_region),
            "suggested_word": self.suggested_word,
            "preview_prompt": self.preview_prompt,
            "turn_region": self.turn_region,
            "prompt_region": self.prompt_region,
        }
