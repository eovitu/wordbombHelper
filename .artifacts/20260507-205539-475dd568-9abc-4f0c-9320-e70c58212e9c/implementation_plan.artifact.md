# Implementation Plan - Professional Auto-Play & UI Enhancements

This plan addresses OCR accuracy ("ess" issue), application stability (Tkinter crashes), and UI/UX improvements to provide a more professional, "invisible" helper experience.

## Problem Analysis

1.  **OCR Misreading ("ess" issue)**: The current crop is too tight (top 35%), often missing centered prompts. The helper's own border colors are being detected as game turn indicators.
2.  **UI/UX Quality**: The current overlay is bulky. The user wants an "invisible" capture area (like Letter Link mode) and professional front-end integration.
3.  **Tkinter Stability**: Thread safety issues and window destruction are causing `TclError: bad window path name`.

## Proposed Changes

### [Screen Reader]

Refine OCR to handle the specific layout: Prompt on top, "SUA VEZ" on bottom.

#### [screen_reader.py](file:///C:/Users/vitu/Documents/wordbomb/screen_reader.py)

- **Layout-Aware Cropping**:
    - Divide the captured region into a **Top Zone** (Prompt) and **Bottom Zone** (Turn Indicator).
    - **Top Zone (0-60%)**: Search for the syllable.
    - **Bottom Zone (60-100%)**: Search for "SUA VEZ" or "YOUR TURN" colors/text.
- **Border Exclusion**: Ignore the outer 10 pixels to avoid detecting the helper's own UI.
- **Improved Turn Validation**: Only trigger if "SUA VEZ" is found in the Bottom Zone.

```python
# In _capture_and_ocr
# ...
h, w = img_large.shape[:2]
# Top Zone for Prompt (60% height)
prompt_zone = img_large[0:int(h*0.6), :]
# Bottom Zone for Turn Indicator (remaining 40%)
turn_zone = img_large[int(h*0.6):h, :]
```

---

### [Overlay Manager]

Make the helper area "invisible" and fix stability issues.

#### [overlay_manager.py](file:///C:/Users/vitu/Documents/wordbomb/overlay_manager.py)

- **Ghost Mode**: Reduce border thickness to 1px or make it a very faint dashed line when active.
- **Stability Fixes**:
    - Use `protocol("WM_DELETE_WINDOW", ...)` to `withdraw()` instead of `destroy()`.
    - Wrap all UI updates in `root.after` for thread safety.
    - Check `winfo_exists()` before any operation on `Toplevel`.

---

### [Front-End]

Enhance the "Manual" and "Auto" tabs to feel more like a professional dashboard.

#### [index.html](file:///C:/Users/vitu/Documents/wordbomb/templates/index.html)

- Add a dedicated "LIVE FEED" or "SUGGESTION" area in the Manual tab that updates in real-time during Auto-Play.
- Improve the visual feedback when it's the player's turn (e.g., a glowing status orb).

#### [app.js](file:///C:/Users/vitu/Documents/wordbomb/static/js/app.js)

- Ensure `pollAutoStatus` updates the main word display prominently when a word is found.

---

## Verification Plan

### Manual Verification
1.  **Test OCR Accuracy**:
    - Position the "invisible" box over the game prompt.
    - Verify that "UPP" (from screenshot) is read correctly, even if "SUA VEZ" is present below it.
2.  **Test Turn Detection**:
    - Verify that words only appear in the front-end when "SUA VEZ" is visible in the game.
3.  **Test Stability**:
    - Stress test by toggling Auto-Play, closing result popups, and refreshing the browser. Ensure no Python/Tkinter errors occur.
4.  **UI Verification**:
    - Check if the capture box is non-intrusive and the front-end display is professional.
