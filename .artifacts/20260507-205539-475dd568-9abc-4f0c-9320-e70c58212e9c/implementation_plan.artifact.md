# Implementation Plan - Fixing Auto-Play OCR and Overlay Stability

This plan addresses the issues where the Auto-Play feature misreads the prompt (often reading "ess" instead of the actual syllable) and the application crashes due to Tkinter thread safety issues.

## Problem Analysis

1.  **OCR Misreading ("ess" issue)**:
    - The `screen_reader.py` uses a very restrictive vertical crop (top 35% of the box), which often misses the prompt if it's centered.
    - The overlay border (purple) falls within the HSV range for BLUE turn detection, causing the program to think it's always the player's turn even when it's not.
    - When it thinks it's its turn but can't find the real prompt, it reads noise (like "ess") and types irrelevant words.
2.  **Tkinter Stability**:
    - `TclError: bad window path name` occurs because `Toplevel` windows are destroyed when closed by the user, but the code still tries to access them.
    - Thread safety issues when calling UI methods from the `screen_reader` thread.

## Proposed Changes

### [Screen Reader]

Improve OCR accuracy and turn detection by excluding the overlay border and being more flexible with prompt location.

#### [screen_reader.py](file:///C:/Users/vitu/Documents/wordbomb/screen_reader.py)

- **Border Exclusion**: Crop 10 pixels from each side of the captured image before processing to remove the overlay's own border from color detection.
- **Flexible Prompt Cropping**: Increase the vertical crop from 35% to 65% to ensure the prompt is captured even if it's lower in the box.
- **Improved Turn Validation**: Add a check to ensure `is_my_turn` isn't triggered by the overlay's own colors if cropping didn't remove them.

```python
# In _capture_and_ocr
sct_img = sct.grab(monitor)
# ...
img_bgr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(sct_img.height, sct_img.width, 4)
img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2BGR)

# NEW: Remove border pixels to avoid detecting the overlay itself
border = 10
if img_bgr.shape[0] > border*2 and img_bgr.shape[1] > border*2:
    img_bgr = img_bgr[border:-border, border:-border]
```

---

### [Overlay Manager]

Fix Tkinter crashes and improve window management.

#### [overlay_manager.py](file:///C:/Users/vitu/Documents/wordbomb/overlay_manager.py)

- **Window Persistence**: Override the `WM_DELETE_WINDOW` protocol for the result window to `withdraw()` instead of `destroy()`.
- **Existence Checks**: Add `winfo_exists()` checks before calling `withdraw()` or `deiconify()`.
- **Thread Safety**: Ensure all UI calls are wrapped in `root.after`.

```python
# In OverlayApp.__init__
self.result_root.protocol("WM_DELETE_WINDOW", self.hide_result)

# In hide_result
def hide_result(self):
    if hasattr(self, 'result_root') and self.result_root.winfo_exists():
        self.result_root.withdraw()
        self._result_visible = False
```

---

### [Application Logic]

#### [word_service.py](file:///C:/Users/vitu/Documents/wordbomb/application/word_service.py)

- Update `reset_words` to handle the overlay more safely.

---

## Verification Plan

### Manual Verification
1.  **Test OCR Accuracy**:
    - Run the application and position the red/purple box over a WordBomb prompt.
    - Verify in the logs that the prompt is correctly identified (no more "ess" when it should be "zd").
2.  **Test Turn Detection**:
    - Move the box to an empty area of the screen.
    - Verify that "Watching" status remains but it doesn't try to type words (i.e., the border doesn't trigger "SUA VEZ").
3.  **Test Overlay Stability**:
    - Close the "MATCH READY" popup using the 'X' button.
    - Trigger another match. Verify that the popup reappears without crashing the app.
    - Click "Reset Used Words" in the browser. Verify no Tkinter errors in the console.
