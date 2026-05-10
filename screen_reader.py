import time
import threading
import mss
import mss.tools
from PIL import Image
import pytesseract
import logging
import cv2
import numpy as np
import os
import shutil
from pynput import mouse

from shared.parsing import normalize_capture_region

logger = logging.getLogger(__name__)

import platform

# Configure Tesseract path based on OS
if platform.system() == 'Windows':
    win_tess_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.isfile(win_tess_path):
        pytesseract.pytesseract.tesseract_cmd = win_tess_path
    else:
        pytesseract.pytesseract.tesseract_cmd = shutil.which('tesseract') or 'tesseract'
else:
    _unix_candidates = ('/usr/bin/tesseract', '/usr/local/bin/tesseract', '/opt/homebrew/bin/tesseract')
    for _tess_bin in _unix_candidates:
        if os.path.isfile(_tess_bin):
            pytesseract.pytesseract.tesseract_cmd = _tess_bin
            break
    else:
        pytesseract.pytesseract.tesseract_cmd = shutil.which('tesseract') or 'tesseract'

class ScreenReader:
    def __init__(self, autoplay_state=None, callback_found_word=None):
        """
        :param autoplay_state: AutoplayStateService instance.
        :param callback_found_word: Function to call when a prompt is found.
        """
        self.autoplay_state = autoplay_state
        self.callback_found_word = callback_found_word
        
        # Calibration data
        self.turn_region = None
        self.prompt_region = None
        
        # State
        self.is_watching = False
        self.status = "Idle"  # Idle, Calibrating, Watching, Parsing
        self.calibration_step = None
        self.temp_points = []
        
        self.thread = None
        self.stop_event = threading.Event()
        
        # Internal state for OCR
        self._last_processed_img = None
        
        # Mouse listener
        self.mouse_listener = None

        # Log callback for frontend
        self.log_callback = None

        # Max retries when SUA VEZ persists after typing
        self.max_retries = 5
        # Screenshot logging for debugging
        self.debug_screenshots_dir = os.path.join(os.getcwd(), "debug_screenshots")
        if not os.path.exists(self.debug_screenshots_dir):
            os.makedirs(self.debug_screenshots_dir)
        self.save_debug_screenshots = False
        self.last_word_typed = ""
        self.suggested_word = ""
        # Last stabilized OCR syllable — shown in frontend while awaiting word lookup
        self.preview_prompt = ""
        
        # Frame hash cache — skip processing if screen is visually identical between polls
        self._last_frame_hash = None
        
        # Persistence: don't cycle words if prompt is the same
        self.last_suggested_prompt = ""
        self._turn_confirm_streak = 0
        self._prompt_confirm_streak = 0
        self._last_prompt_candidate = ""
        # Keeps OCR / turn-detection semantics in sync with _last_frame_hash
        self._last_capture_result = ("", None, False)

    @staticmethod
    def _clean_ocr_token(text):
        return ''.join(ch for ch in (text or '') if ch.isalpha()).upper()

    def _extract_prompt_candidate(self, pil_to_ocr, tess_lang, config):
        ui_keywords = {
            "SUA", "VEZ", "YOUR", "TURN", "VE2", "UEZ", "VAR", "SORA", "BANE",
            "SOLO"
        }

        try:
            ocr_data = pytesseract.image_to_data(
                pil_to_ocr,
                lang=tess_lang,
                config=config,
                output_type=pytesseract.Output.DICT,
            )
        except Exception:
            ocr_data = None

        best_candidate = ""
        best_confidence = -1.0

        if ocr_data:
            for txt, conf in zip(ocr_data.get("text", []), ocr_data.get("conf", [])):
                clean = self._clean_ocr_token(txt)
                if not clean or clean in ui_keywords:
                    continue
                try:
                    conf_val = float(conf)
                except Exception:
                    conf_val = -1.0
                if conf_val > best_confidence:
                    best_candidate = clean
                    best_confidence = conf_val

        if best_candidate:
            return best_candidate.lower(), best_confidence

        try:
            fallback_text = pytesseract.image_to_string(pil_to_ocr, lang=tess_lang, config=config).strip().upper()
        except Exception:
            fallback_text = ""

        fallback_candidate = self._clean_ocr_token(fallback_text)
        if fallback_candidate and fallback_candidate not in ui_keywords:
            return fallback_candidate.lower(), 0.0

        return "", -1.0

    def set_callback(self, callback):
        self.callback_found_word = callback

    def set_log_callback(self, callback):
        self.log_callback = callback

    def _log(self, msg):
        logger.debug(msg)
        if self.log_callback:
            try:
                self.log_callback(msg)
            except Exception:
                pass

    def update_region_from_overlay(self, region_data):
        """
        Called by the overlay window to update the current region.
        It updates both turn/prompt regions to be the single rectangle.
        """
        coords = normalize_capture_region(
            {
                "x1": region_data.get("x1"),
                "y1": region_data.get("y1"),
                "width": region_data.get("width"),
                "height": region_data.get("height"),
            }
        )
        if not coords:
            logger.error("Overlay supplied invalid capture region: %s", region_data)
            return

        self.turn_region = coords
        self.prompt_region = self.turn_region

        if not self.is_watching:
            self.start_watching()

    def start_calibration(self):
        """Start calibration mode and listen for mouse clicks."""
        self.status = "Calibrating"
        self.calibration_step = 'turn_start'
        self.temp_points = []
        # Start mouse listener
        if self.mouse_listener:
            self.mouse_listener.stop()
        self.mouse_listener = mouse.Listener(on_click=self._on_click)
        self.mouse_listener.start()
        logger.info("Calibration started - click top-left of the prompt + SUA VEZ area")

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
        logger.info(f"Calibration click processed: {result}")
        
        if result['status'] == 'done':
            self.stop_calibration()

    def handle_calibration_click(self, x, y):
        """
        Called by the mouse listener when a click is detected.
        """
        if self.status != "Calibrating":
            return {"status": "error", "message": "Not in calibration mode"}

        try:
            x = int(round(float(x)))
            y = int(round(float(y)))
        except (TypeError, ValueError):
            return {"status": "error", "message": "Invalid coordinates"}

        logger.info(f"Calibration click at {x}, {y} for step {self.calibration_step}")

        if self.calibration_step == 'turn_start':
            self.temp_points = [(x, y)]
            self.calibration_step = 'turn_end'
            return {"status": "next", "message": "Click bottom-right of the ENTIRE BOX (Prompt + 'SUA VEZ')", "step": "turn_end"}
            
        elif self.calibration_step == 'turn_end':
            start_x, start_y = self.temp_points[0]
            region = self._normalize_rect(start_x, start_y, x, y)
            self.turn_region = region
            self.prompt_region = region
            
            self.temp_points = []
            self.status = "Idle"
            self.calibration_step = None
            
            logger.info(f"Calibration complete. Unified Region: {region}")
            return {"status": "done", "message": "Calibration Complete! (Single Region Mode)", "regions": self.get_state()}
            
        return {"status": "error", "message": "Unknown step"}

    def _normalize_rect(self, x1, y1, x2, y2):
        return {
            'x1': int(min(x1, x2)),
            'y1': int(min(y1, y2)),
            'x2': int(max(x1, x2)),
            'y2': int(max(y1, y2)),
            'width': int(abs(x2 - x1)),
            'height': int(abs(y2 - y1))
        }

    def toggle_watching(self):
        if self.is_watching:
            self.stop_watching()
            return False
        else:
            if not normalize_capture_region(self.turn_region) or not normalize_capture_region(self.prompt_region):
                logger.error("Cannot start watching: regions not calibrated")
                return False
            self.start_watching()
            return True

    def start_watching(self):
        if self.is_watching:
            return
        
        self.is_watching = True
        self.status = "Watching"
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.thread.start()
        logger.info("Started watching screen")

    def stop_watching(self):
        if not self.is_watching:
            return
            
        self.is_watching = False
        self.status = "Idle"
        self.stop_event.set()
        
        # Cleanup mss instance if needed (though we keep it for faster re-start)
        # self._sct.close() 
        
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("Stopped watching screen")

    def _capture_and_ocr(self, sct):
        """Capture the region and return (full_text_upper, prompt_text, is_my_turn)."""
        is_my_turn = False
        coords = normalize_capture_region(self.turn_region)
        if not coords:
            logger.warning("Calibrated capture region invalid or incomplete; re-calibrate.")
            return None, None, False
        monitor = {
            "top": coords['y1'],
            "left": coords['x1'],
            "width": coords['width'],
            "height": coords['height'],
        }
        if monitor["width"] < 8 or monitor["height"] < 8:
            logger.warning("Capture region smaller than minimum; re-calibrate.")
            return None, None, False
        
        # Use the provided mss instance
        sct_img = sct.grab(monitor)
        
        # Frame cache: skip the expensive pipeline if screen is visually identical
        raw_bytes = bytes(sct_img.raw)
        frame_hash = hash(raw_bytes)
        if (
            self._last_frame_hash is not None
            and frame_hash == self._last_frame_hash
        ):
            return self._last_capture_result

        # Convert to numpy array (mss returns BGRA)
        img_bgr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(sct_img.height, sct_img.width, 4)
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2BGR)
        
        # NEW: Remove border pixels to avoid detecting the overlay's own border colors
        border_px = 12
        if img_bgr.shape[0] > border_px * 2 and img_bgr.shape[1] > border_px * 2:
            img_bgr = img_bgr[border_px:-border_px, border_px:-border_px]

        # OPTIMIZATION: Do color masking directly on the raw, non-upscaled image first!
        hsv_small = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        
        # Ranges for "SUA VEZ" button colors
        lower_yellow = np.array([20, 100, 100])
        upper_yellow = np.array([35, 255, 255])
        lower_blue = np.array([100, 150, 150])
        upper_blue = np.array([130, 255, 255])
        # RED (User's specific theme) - Red wraps around 0 and 180 in HSV
        lower_red1 = np.array([0, 150, 100])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 150, 100])
        upper_red2 = np.array([180, 255, 255])
        
        mask_yellow_small = cv2.inRange(hsv_small, lower_yellow, upper_yellow)
        mask_blue_small = cv2.inRange(hsv_small, lower_blue, upper_blue)
        mask_red_small = cv2.bitwise_or(cv2.inRange(hsv_small, lower_red1, upper_red1), 
                                        cv2.inRange(hsv_small, lower_red2, upper_red2))

        # Early exit on small image (Thresholds / 4. 500/4 = 125, we use 100)
        if cv2.countNonZero(mask_yellow_small) <= 100 and \
           cv2.countNonZero(mask_blue_small) <= 100 and \
           cv2.countNonZero(mask_red_small) <= 100:
            res = ("", None, False)
            self._last_capture_result = res
            self._last_frame_hash = frame_hash
            return res

        # Upscale for better OCR (2x is enough for performance)
        # Use INTER_NEAREST for speed if resolution is decent
        h, w = img_bgr.shape[:2]
        interp = cv2.INTER_NEAREST if w >= 300 else cv2.INTER_LINEAR
        img_large = cv2.resize(img_bgr, (w * 2, h * 2), interpolation=interp)

        # 1. TURN DETECTION (Full Image Analysis)
        hsv_full = cv2.cvtColor(img_large, cv2.COLOR_BGR2HSV)
        
        mask_yellow_full = cv2.inRange(hsv_full, lower_yellow, upper_yellow)
        mask_blue_full = cv2.inRange(hsv_full, lower_blue, upper_blue)
        mask_red_full = cv2.bitwise_or(cv2.inRange(hsv_full, lower_red1, upper_red1), 
                                       cv2.inRange(hsv_full, lower_red2, upper_red2))
        
        yellow_pixels = cv2.countNonZero(mask_yellow_full)
        blue_pixels = cv2.countNonZero(mask_blue_full)
        red_pixels = cv2.countNonZero(mask_red_full)

        # 2. PROMPT EXTRACTION (Balanced Cropping)
        # We divide the image into Top Zone (Prompt) and Bottom Zone (Turn Indicator)
        # Vertical: Prompt is usually in the upper 60%
        h, w = img_large.shape[:2]
        prompt_zone = img_large[0:int(h * 0.65), :]
        turn_zone = img_large[int(h * 0.55):, :] # Overlap slightly for robustness

        # Focus prompt extraction on the prompt_zone
        hsv_cropped = cv2.cvtColor(prompt_zone, cv2.COLOR_BGR2HSV)
        
        # White letters (Prompt)
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 50, 255])
        mask_white = cv2.inRange(hsv_cropped, lower_white, upper_white)
        
        # Mask for Yellow/Blue/Red buttons inside prompt area (to exclude them from text OCR)
        mask_yellow_crop = cv2.inRange(hsv_cropped, lower_yellow, upper_yellow)
        mask_blue_crop = cv2.inRange(hsv_cropped, lower_blue, upper_blue)
        mask_red_crop = cv2.bitwise_or(cv2.inRange(hsv_cropped, lower_red1, upper_red1), 
                                       cv2.inRange(hsv_cropped, lower_red2, upper_red2))
        
        combined_mask = cv2.bitwise_or(mask_white, mask_yellow_crop)
        combined_mask = cv2.bitwise_or(combined_mask, mask_blue_crop)
        combined_mask = cv2.bitwise_or(combined_mask, mask_red_crop)
        
        # Denoise and Enhance
        denoised = cv2.medianBlur(combined_mask, 3)
        
        # Final sharpening and thresholding for Tesseract
        final_processed = cv2.bitwise_not(denoised)
        final_processed = cv2.threshold(final_processed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

        self._last_processed_img = final_processed
        
        if self.save_debug_screenshots:
            try:
                debug_path = os.path.join(self.debug_screenshots_dir, "last_processed.png")
                cv2.imwrite(debug_path, final_processed)
            except Exception as e:
                logger.error(f"Failed to save debug screenshot: {e}")
        
        # Convert back to PIL for Tesseract
        prompt_pil_to_ocr = Image.fromarray(final_processed)
        
        # OCR with Portuguese and English
        tess_lang = 'por+eng'
        tessdata_path = os.path.abspath('tessdata').replace('\\', '/')
        config = f'--tessdata-dir {tessdata_path} --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz '

        # Detect "SUA VEZ" or "YOUR TURN" specifically in the TURN ZONE
        hsv_turn = cv2.cvtColor(turn_zone, cv2.COLOR_BGR2HSV)
        mask_yellow_turn = cv2.countNonZero(cv2.inRange(hsv_turn, lower_yellow, upper_yellow))
        mask_blue_turn = cv2.countNonZero(cv2.inRange(hsv_turn, lower_blue, upper_blue))
        mask_red_turn = cv2.countNonZero(cv2.bitwise_or(cv2.inRange(hsv_turn, lower_red1, upper_red1),
                                                         cv2.inRange(hsv_turn, lower_red2, upper_red2)))

        # OCR check on the whole image (or just bottom) to confirm keywords
        full_pil = Image.fromarray(cv2.bitwise_not(cv2.threshold(cv2.cvtColor(img_large, cv2.COLOR_BGR2GRAY), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]))
        full_text = pytesseract.image_to_string(full_pil, lang=tess_lang, config=config).strip().upper()
        
        logger.debug(f"OCR RAW: '{full_text}'")

        # Higher thresholds to avoid false positives from background pixels
        color_detected = mask_yellow_turn > 1000 or mask_blue_turn > 1000 or mask_red_turn > 1000
        
        # Method 2: OCR Keywords (Fallback)
        turn_keywords = ["VEZ", "TURN", "YOUR", "SUA", "VE2", "UEZ"]
        keyword_detected = any(kw in full_text for kw in turn_keywords)

        turn_candidate = False
        if (mask_yellow_turn > 8000 or mask_blue_turn > 8000 or mask_red_turn > 8000):
            turn_candidate = True
        elif (mask_yellow_turn > 2000 or mask_blue_turn > 2000 or mask_red_turn > 2000) and keyword_detected:
            turn_candidate = True

        if turn_candidate:
            self._turn_confirm_streak += 1
        else:
            self._turn_confirm_streak = 0

        if self._turn_confirm_streak >= 1: # Faster response for user
            is_my_turn = True
        else:
            is_my_turn = False

        # Extract prompt: look for the most likely syllable
        prompt_text = None
        full_candidate, candidate_conf = self._extract_prompt_candidate(prompt_pil_to_ocr, tess_lang, config)

        if full_candidate and 2 <= len(full_candidate) <= 4:
            # Ghost Prompt Protection: Ensure it's not just a suffix of our last typed word
            # e.g. Typed "BANANA", prompt is "NA" -> likely ghosting
            is_ghost = False
            if self.last_word_typed:
                last_lower = self.last_word_typed.lower()
                if last_lower.endswith(full_candidate) and len(full_candidate) >= 2:
                    # If it's a suffix, it MIGHT be a ghost. 
                    # But if "SUA VEZ" was just detected by color, we trust it more.
                    if not color_detected:
                        is_ghost = True
            
            validation_ok = candidate_conf >= 55.0 or (candidate_conf >= 35.0 and color_detected) or (color_detected and keyword_detected)

            if not is_ghost and validation_ok:
                prompt_text = full_candidate
                logger.debug(
                    f"Prompt validated by Tesseract: '{prompt_text}' (conf={candidate_conf:.1f}, color={color_detected}, keyword={keyword_detected})"
                )
            else:
                logger.debug(
                    f"Prompt candidate rejected: '{full_candidate}' (conf={candidate_conf:.1f}, color={color_detected}, keyword={keyword_detected}, ghost={is_ghost})"
                )
        
        payload = ((full_text or "").strip(), prompt_text, bool(is_my_turn))
        self._last_capture_result = payload
        self._last_frame_hash = frame_hash
        return payload

    def _watch_loop(self):
        with mss.mss() as sct:
            while not self.stop_event.is_set():
                try:
                    full_text, prompt_text, is_my_turn = self._capture_and_ocr(sct)
                    
                    if full_text is None:
                        time.sleep(0.5)
                        continue

                    # === CORE LOGIC ===
                    # Only act if "SUA VEZ" is detected
                    if not is_my_turn:
                        self.preview_prompt = ""
                        if self.suggested_word != "":
                            self.suggested_word = ""
                            self.last_suggested_prompt = ""
                            if self.callback_found_word:
                                self.callback_found_word("")
                        time.sleep(0.1)  # Faster poll when not our turn
                        continue
                    
                    # It IS our turn. Extract the prompt.
                    if not prompt_text or len(prompt_text) < 1:
                        self.preview_prompt = ""
                        self._prompt_confirm_streak = 0
                        self._last_prompt_candidate = ""
                        # SUA VEZ is showing but we can't read the prompt clearly
                        time.sleep(0.1)
                        continue

                    if prompt_text == self._last_prompt_candidate:
                        self._prompt_confirm_streak += 1
                    else:
                        self._last_prompt_candidate = prompt_text
                        self._prompt_confirm_streak = 1

                    if self._prompt_confirm_streak < 2:
                        time.sleep(0.1)
                        continue

                    self.preview_prompt = prompt_text

                    # PERSISTENCE: If prompt is the same as last time, don't re-calculate or flicker
                    if prompt_text == self.last_suggested_prompt:
                        time.sleep(0.2)
                        continue
                    
                    self._log(f"Prompt validated by Tesseract: '{prompt_text}'")
                    self.last_suggested_prompt = prompt_text
                    self._last_frame_hash = None  # Reset cache — active turn, always want fresh frames
                    
                    # Check if we should auto-type or just suggest (default: suggest only)
                    auto_type = False
                    if self.autoplay_state:
                        config = self.autoplay_state.snapshot_config()
                        auto_type = config.get("auto_type", False)

                    if not auto_type:
                        if self.callback_found_word:
                            self.callback_found_word(prompt_text)
                        time.sleep(0.2)
                        continue

                    # === TYPE + RETRY LOOP (Only if auto_type is ON) ===
                    retries = 0
                    current_prompt = prompt_text
                    while retries < self.max_retries and not self.stop_event.is_set():
                        if self.callback_found_word:
                            typed = self.callback_found_word(current_prompt)
                            if not typed:
                                self._log(f"No word found for '{current_prompt}', giving up.")
                                break
                        else:
                            break
                        
                        # Wait for typing to finish + game to process
                        time.sleep(0.4)
                        
                        # Force fresh capture for retry check (bypass frame cache)
                        self._last_frame_hash = None
                        _, new_prompt, still_my_turn = self._capture_and_ocr(sct)
                        
                        if not still_my_turn:
                            self._log("Word accepted! Waiting for next turn...")
                            break
                        
                        if not new_prompt:
                            # Prompt disappeared or OCR failed. Break and let outer loop re-scan.
                            self._log("Prompt missing or OCR failed during retry. Re-scanning...")
                            break

                        if new_prompt != current_prompt:
                            self._log(f"Prompt changed to '{new_prompt}'. Likely accepted (Solo Mode)!")
                            break
                        
                        # Same prompt + turn indicator still showing = rejection
                        retries += 1
                        self._log(f"Same prompt '{current_prompt}' still showing, trying another word... (attempt {retries + 1})")
                    
                    # Minimal delay before scanning again
                    time.sleep(0.2)
                    
                except Exception as e:
                    logger.error(f"Error in watch loop: {e}")
                    time.sleep(1)


    def get_state(self):
        return {
            "status": self.status,
            "is_watching": self.is_watching,
            "calibration_step": self.calibration_step,
            "regions_set": bool(self.turn_region and self.prompt_region),
            "suggested_word": self.suggested_word,
            "preview_prompt": self.preview_prompt,
            "turn_region": self.turn_region,
            "prompt_region": self.prompt_region
        }
