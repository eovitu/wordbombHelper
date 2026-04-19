import cv2
import numpy as np
import pytesseract
from PIL import Image
import mss
import logging
import platform
import os

logger = logging.getLogger(__name__)

# Configure Tesseract path based on OS
if platform.system() == 'Windows':
    win_tess_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(win_tess_path):
        pytesseract.pytesseract.tesseract_cmd = win_tess_path
    else:
        pytesseract.pytesseract.tesseract_cmd = 'tesseract'
else:
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

class GridReader:
    def __init__(self, debug_dir="debug_screenshots"):
        self.debug_dir = debug_dir
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)

    def read_grid(self, region):
        """
        region: dict {'x1': int, 'y1': int, 'width': int, 'height': int}
        Returns: list of lists (5x5) containing characters, and cell screen coordinates
        """
        if not region or region['width'] < 50 or region['height'] < 50:
            logger.error(f"Region is too small or invalid: {region}")
            return None, None

        monitor = {
            "top": region['y1'],
            "left": region['x1'],
            "width": region['width'],
            "height": region['height']
        }

        with mss.mss() as sct:
            sct_img = sct.grab(monitor)
            
        img_bgr = np.array(sct_img)
        img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2BGR)
        
        # Save raw capture for debugging
        cv2.imwrite(os.path.join(self.debug_dir, "grid_raw.png"), img_bgr)

        # The image is a 5x5 grid. 
        # Calculate cell width and height
        cell_w = img_bgr.shape[1] // 5
        cell_h = img_bgr.shape[0] // 5
        
        if cell_w < 5 or cell_h < 5:
            logger.error(f"Cells are too small to read! cell_w={cell_w}, cell_h={cell_h}")
            return None, None

        grid_matrix = []
        cell_coords = [] # Store center coordinate of each cell for mouse dragging

        for row in range(5):
            row_chars = []
            row_coords = []
            for col in range(5):
                # Calculate cell bounds
                x_start = col * cell_w
                y_start = row * cell_h
                x_end = x_start + cell_w
                y_end = y_start + cell_h
                
                # Screen coordinates for the center of the cell
                screen_cx = region['x1'] + x_start + (cell_w // 2)
                screen_cy = region['y1'] + y_start + (cell_h // 2)
                row_coords.append((screen_cx, screen_cy))
                
                # Extract cell image
                cell_img = img_bgr[y_start:y_end, x_start:x_end]
                
                # Extract center area to avoid corner icons/points
                m_h = int(cell_h * 0.12)
                m_w = int(cell_w * 0.12)
                inner_cell = cell_img[m_h:cell_h-m_h, m_w:cell_w-m_w]

                # Stable preprocessing: less distortion, enough detail for OCR
                upscaled = cv2.resize(inner_cell, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
                gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
                clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                gray = clahe.apply(gray)

                # Binary mask for contour geometry only
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                bg_color = (int(thresh[0, 0]) + int(thresh[0, -1]) + int(thresh[-1, 0]) + int(thresh[-1, -1])) / 4
                if bg_color > 128:
                    thresh = cv2.bitwise_not(thresh)

                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
                thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not contours:
                    row_chars.append('.')
                    continue

                center_h, center_w = thresh.shape[0] // 2, thresh.shape[1] // 2
                best_contour = None
                max_score = -1
                for cnt in contours:
                    cx, cy, cw, ch = cv2.boundingRect(cnt)
                    if cw < 4 or ch < 4:
                        continue
                    area = cw * ch
                    dist_to_center = np.sqrt((cx + cw / 2 - center_w) ** 2 + (cy + ch / 2 - center_h) ** 2)
                    score = area / (dist_to_center + 1)
                    if score > max_score:
                        max_score = score
                        best_contour = cnt

                if best_contour is None:
                    row_chars.append('.')
                    continue

                x, y, w, h = cv2.boundingRect(best_contour)
                aspect_ratio = w / float(h) if h > 0 else 0.0

                # Hyphen is a short horizontal stroke. Keep this test strict.
                if aspect_ratio > 2.0 and h < int(upscaled.shape[0] * 0.30):
                    row_chars.append('-')
                    continue

                if w < 5 or h < 5:
                    row_chars.append('.')
                    continue

                # OCR on grayscale ROI around the detected contour
                pad = 2
                y0 = max(0, y - pad)
                y1 = min(gray.shape[0], y + h + pad)
                x0 = max(0, x - pad)
                x1 = min(gray.shape[1], x + w + pad)
                letter_roi = gray[y0:y1, x0:x1]

                candidates = []
                for variant in self._build_ocr_variants(letter_roi):
                    char, conf = self._ocr_char_with_conf(variant)
                    candidates.append((char, conf))

                best_char, best_conf = max(candidates, key=lambda it: it[1]) if candidates else ('.', -1)

                # Fallback only when OCR is weak/empty.
                if best_char == '.' and self._looks_like_m(thresh[y:y+h, x:x+w]):
                    best_char = 'M'

                if best_char not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ-':
                    best_char = '.'

                # Save per-cell debug image with final decision.
                debug_filename = os.path.join(self.debug_dir, f"cell_{row}_{col}_{best_char}.png")
                cv2.imwrite(debug_filename, self._to_tesseract_canvas(cv2.threshold(letter_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]))

                row_chars.append(best_char)
                
            grid_matrix.append(row_chars)
            cell_coords.append(row_coords)

        logger.info(f"Grid Parsing Complete:\n{np.array(grid_matrix)}")

        return grid_matrix, cell_coords

    def _build_ocr_variants(self, gray_roi):
        """Build multiple OCR-ready variants from a grayscale ROI."""
        variants = []

        # Variant 1: OTSU binary
        _, v1 = cv2.threshold(gray_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(self._to_tesseract_canvas(v1))

        # Variant 2: Adaptive threshold
        v2 = cv2.adaptiveThreshold(
            gray_roi,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            2,
        )
        variants.append(self._to_tesseract_canvas(v2))

        # Variant 3: CLAHE + OTSU
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        eq = clahe.apply(gray_roi)
        _, v3 = cv2.threshold(eq, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants.append(self._to_tesseract_canvas(v3))

        return variants

    def _to_tesseract_canvas(self, binary_img):
        """Normalize binary image to black text on white background with border."""
        img = binary_img.copy()
        bg_color = (int(img[0, 0]) + int(img[0, -1]) + int(img[-1, 0]) + int(img[-1, -1])) / 4
        if bg_color < 128:
            img = cv2.bitwise_not(img)

        img = cv2.copyMakeBorder(img, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
        img = cv2.resize(img, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)
        return img

    def _ocr_char_with_conf(self, prepared_img):
        """Run single-char OCR and return (char, confidence)."""
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ-")
        config = r'--oem 3 --psm 10 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ-'
        pil_img = Image.fromarray(prepared_img)

        try:
            data = pytesseract.image_to_data(
                pil_img,
                config=config,
                output_type=pytesseract.Output.DICT,
            )
            best_char = '.'
            best_conf = -1.0
            for txt, conf in zip(data.get("text", []), data.get("conf", [])):
                txt = (txt or "").strip().upper()
                if not txt:
                    continue
                try:
                    conf_val = float(conf)
                except Exception:
                    conf_val = -1.0
                for ch in txt:
                    if ch in allowed and conf_val > best_conf:
                        best_char = ch
                        best_conf = conf_val
            if best_char != '.':
                return best_char, best_conf
        except Exception:
            pass

        try:
            txt = pytesseract.image_to_string(pil_img, config=config).strip().upper()
            if txt:
                for ch in txt:
                    if ch in allowed:
                        return ch, 0.0
        except Exception:
            pass

        return '.', -1.0

    def _looks_like_m(self, binary_roi):
        """Fallback check for M when OCR fails: multiple vertical peaks and wide shape."""
        try:
            if binary_roi is None or binary_roi.size == 0:
                return False

            roi = binary_roi.copy()
            bg_color = (int(roi[0, 0]) + int(roi[0, -1]) + int(roi[-1, 0]) + int(roi[-1, -1])) / 4
            if bg_color > 128:
                roi = cv2.bitwise_not(roi)

            h, w = roi.shape[:2]
            if h < 8 or w < 8 or (w / float(h)) < 0.75:
                return False

            col = np.sum(roi > 0, axis=0).astype(np.float32)
            if np.max(col) <= 0:
                return False
            col = col / np.max(col)

            peaks = []
            for i in range(1, len(col) - 1):
                if col[i - 1] < col[i] > col[i + 1] and col[i] > 0.45:
                    peaks.append(i)

            if len(peaks) < 3:
                return False

            return peaks[0] < len(col) // 3 and peaks[-1] > (2 * len(col)) // 3
        except Exception:
            return False
