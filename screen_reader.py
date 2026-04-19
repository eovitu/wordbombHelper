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
from pynput import mouse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import platform

# Configure Tesseract path based on OS
if platform.system() == 'Windows':
    # Common installation path for Tesseract on Windows
    win_tess_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(win_tess_path):
        pytesseract.pytesseract.tesseract_cmd = win_tess_path
    else:
        # Fallback to just 'tesseract' and hope it's in PATH
        pytesseract.pytesseract.tesseract_cmd = 'tesseract'
else:
    # Linux/Mac path
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

class ScreenReader:
    def __init__(self, callback_found_word=None):
        """
        :param callback_found_word: Function to call when a prompt is found.
               Must accept (prompt_text: str) and return True if word was typed, False otherwise.
        """
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
        
        # Frame hash cache — skip processing if screen is visually identical between polls
        self._last_frame_hash = None

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

    def update_region_from_overlay(self, region_data):
        """
        Called by the overlay window to update the current region.
        It updates both turn/prompt regions to be the single rectangle.
        """
        x1 = region_data['x1']
        y1 = region_data['y1']
        
        self.turn_region = {
            'x1': x1, 'y1': y1, 
            'width': region_data['width'], 
            'height': region_data['height']
        }
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
            if not self.turn_region or not self.prompt_region:
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
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("Stopped watching screen")

    def _capture_and_ocr(self):
        """Capture the region and return (full_text_upper, prompt_text, is_my_turn)."""
        is_my_turn = False
        if not self.prompt_region:
            return None, None, False

        monitor = {
            "top": self.prompt_region['y1'],
            "left": self.prompt_region['x1'],
            "width": self.prompt_region['width'],
            "height": self.prompt_region['height']
        }
        
        # Capture using mss with a local instance (thread-safe: no shared state)
        with mss.mss() as sct:
            sct_img = sct.grab(monitor)
        
        # Frame cache: skip the expensive pipeline if screen is visually identical
        frame_hash = hash(bytes(sct_img.raw))
        if frame_hash == self._last_frame_hash:
            return "", None, False
        self._last_frame_hash = frame_hash

        # Convert to numpy array (mss returns BGRA)
        img_bgr = np.array(sct_img)
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2BGR)
        
        # OPTIMIZATION: Do color masking directly on the raw, non-upscaled image first!
        hsv_small = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        
        # Ranges for "SUA VEZ" button colors
        lower_yellow = np.array([20, 100, 100])
        upper_yellow = np.array([35, 255, 255])
        lower_blue = np.array([100, 150, 150])
        upper_blue = np.array([130, 255, 255])
        
        mask_yellow_small = cv2.inRange(hsv_small, lower_yellow, upper_yellow)
        mask_blue_small = cv2.inRange(hsv_small, lower_blue, upper_blue)

        # Early exit on small image (Thresholds / 4. 500/4 = 125, we use 100)
        if cv2.countNonZero(mask_yellow_small) <= 100 and cv2.countNonZero(mask_blue_small) <= 100:
            return "", None, False

        # Upscale for better OCR (2x is enough for performance)
        h, w = img_bgr.shape[:2]
        img_large = cv2.resize(img_bgr, (w * 2, h * 2), interpolation=cv2.INTER_LINEAR)

        # 1. TURN DETECTION (Full Image Analysis)
        hsv_full = cv2.cvtColor(img_large, cv2.COLOR_BGR2HSV)
        
        mask_yellow_full = cv2.inRange(hsv_full, lower_yellow, upper_yellow)
        mask_blue_full = cv2.inRange(hsv_full, lower_blue, upper_blue)
        
        yellow_pixels = cv2.countNonZero(mask_yellow_full)
        blue_pixels = cv2.countNonZero(mask_blue_full)

        # 2. PROMPT EXTRACTION (Balanced Cropping)
        # Vertical: Crop to top 35% (Stricter than 38% to be safe)
        crop_h = int(img_large.shape[0] * 0.35)
        # Horizontal: Center 40% (ignore names/noise at edges)
        large_w = img_large.shape[1]
        crop_x_start = int(large_w * 0.30)
        crop_x_end = int(large_w * 0.70)
        
        img_cropped = img_large[0:crop_h, crop_x_start:crop_x_end]
        hsv_cropped = cv2.cvtColor(img_cropped, cv2.COLOR_BGR2HSV)
        
        # White letters (Prompt)
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 50, 255])
        mask_white = cv2.inRange(hsv_cropped, lower_white, upper_white)
        
        # Mask for Yellow/Blue buttons inside cropped area
        mask_yellow_crop = cv2.inRange(hsv_cropped, lower_yellow, upper_yellow)
        mask_blue_crop = cv2.inRange(hsv_cropped, lower_blue, upper_blue)
        combined_mask = cv2.bitwise_or(mask_white, mask_yellow_crop)
        combined_mask = cv2.bitwise_or(combined_mask, mask_blue_crop)
        
        # Denoise only (Skipping dilation to keep gaps open for 'E', 'R', 'N')
        denoised = cv2.medianBlur(combined_mask, 3)
        
        # Final sharpening and thresholding for Tesseract
        final_processed = cv2.bitwise_not(denoised)
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        final_processed = cv2.filter2D(final_processed, -1, kernel)
        _, final_processed = cv2.threshold(final_processed, 150, 255, cv2.THRESH_BINARY)

        self._last_processed_img = final_processed
        
        if self.save_debug_screenshots:
            try:
                debug_path = os.path.join(self.debug_screenshots_dir, "last_processed.png")
                cv2.imwrite(debug_path, final_processed)
            except Exception as e:
                logger.error(f"Failed to save debug screenshot: {e}")
        
        # Convert back to PIL for Tesseract
        pil_to_ocr = Image.fromarray(final_processed)
        
        # OCR with Portuguese and English
        tess_lang = 'por+eng'
        # PSM 7: Usually the prompt is a single line/blob in the cropped area
        tessdata_path = os.path.join(os.getcwd(), 'tessdata')
        config = f'--tessdata-dir "{tessdata_path}" --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz '
        full_text = pytesseract.image_to_string(pil_to_ocr, lang=tess_lang, config=config).strip().upper()
        
        logger.debug(f"OCR RAW: '{full_text}'")

        # Detect "SUA VEZ" or "YOUR TURN"
        # yellow_pixels and blue_pixels were already calculated above
        
        # Higher thresholds to avoid false positives from background pixels
        # On a 3x upscaled 329x161 image, a real button has >1000 colored pixels
        color_detected = yellow_pixels > 1000 or blue_pixels > 1000
        
        # Method 2: OCR Keywords (Fallback)
        turn_keywords = ["VEZ", "TURN", "YOUR", "SUA", "VE2", "UEZ"]
        keyword_detected = any(kw in full_text for kw in turn_keywords)
        
        # Decoupled turn detection from OCR success
        # STRICTER VALIDATION: 
        # - >5000 pixels: High confidence color detect
        # - 1500-5000 pixels: Needs keyword (SUA VEZ) to confirm
        # - <1500 pixels: Always ignore (UI noise/player names)
        
        if (yellow_pixels > 5000 or blue_pixels > 5000):
            is_my_turn = True
            logger.debug(f"SUA VEZ validated by high-confidence color! (Y:{yellow_pixels}, B:{blue_pixels})")
        elif (yellow_pixels > 1500 or blue_pixels > 1500) and keyword_detected:
            is_my_turn = True
            logger.debug(f"SUA VEZ validated by color + keyword (Y:{yellow_pixels}, B:{blue_pixels})")
        elif keyword_detected and not (yellow_pixels > 500 or blue_pixels > 500):
            # If we see the keyword but NO color at all, it's likely a hallucination or another player.
            logger.debug(f"Ignoring turn keyword: pixels too low (Y:{yellow_pixels}, B:{blue_pixels})")
            is_my_turn = False

        # Extract prompt: look for the most likely syllable
        prompt_text = None
        
        # UI Keywords: ONLY things that are 100% not prompts
        ui_keywords = [
            "SUA", "VEZ", "YOUR", "TURN", "VE2", "UEZ", "VAR", "SORA", "BANE", 
            "SOLO"
        ]
        
        # Method 2: Joined Candidates (Handle "A N T" -> "ANT")
        # Split by any whitespace and filter out UI Junk
        parts = full_text.split()
        joined_candidates = []
        for p in parts:
            clean = ''.join(filter(str.isalpha, p)).upper()
            if clean and clean not in ui_keywords:
                joined_candidates.append(clean)
        
        # Re-join all fragments into one potential prompt
        full_candidate = "".join(joined_candidates).lower()
        
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
            
            if not is_ghost:
                prompt_text = full_candidate
                logger.debug(f"Prompt extracted: '{prompt_text}'")
            else:
                logger.debug(f"Ghost prompt '{full_candidate}' ignored (suffix of '{self.last_word_typed}')")
        
        return full_text, prompt_text, is_my_turn

    def _watch_loop(self):
        while not self.stop_event.is_set():
            try:
                full_text, prompt_text, is_my_turn = self._capture_and_ocr()
                
                if full_text is None:
                    time.sleep(0.5)
                    continue

                # === CORE LOGIC ===
                # Only act if "SUA VEZ" is detected
                if not is_my_turn:
                    time.sleep(0.1)  # Faster poll when not our turn
                    continue
                
                # It IS our turn. Extract the prompt.
                if not prompt_text or len(prompt_text) < 1:
                    # SUA VEZ is showing but we can't read the prompt clearly
                    time.sleep(0.1)
                    continue

                self._log(f"SUA VEZ detected! Prompt: '{prompt_text}'")
                self._last_frame_hash = None  # Reset cache — active turn, always want fresh frames
                
                # === TYPE + RETRY LOOP ===
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
                    _, new_prompt, still_my_turn = self._capture_and_ocr()
                    
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
            "turn_region": self.turn_region,
            "prompt_region": self.prompt_region
        }
