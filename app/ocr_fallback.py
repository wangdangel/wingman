# app/ocr_fallback.py
import os
import ctypes
from ctypes import wintypes
import win32gui
from mss import mss
from PIL import Image
import pytesseract

from .util import load_config
from .dx_capture import grab_window_region

# ---------- Make the process DPI-aware (so rects are real pixels) ----------
def _set_dpi_awareness():
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
        user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        return
    except Exception:
        pass
    try:
        shcore = ctypes.WinDLL("Shcore")
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

_set_dpi_awareness()

def _ensure_tesseract_cmd():
    try:
        cfg = load_config()
        tpath = cfg.get("scraping", {}).get("tesseract_path")
        if tpath and os.path.exists(tpath):
            pytesseract.pytesseract.tesseract_cmd = tpath
    except Exception:
        pass

def _window_rect(hwnd):
    x1, y1, x2, y2 = win32gui.GetWindowRect(hwnd)
    return x1, y1, x2, y2

def _region_abs_from_cfg(hwnd, crop_pct):
    """
    Decide what to capture:
    - If scraping.capture.force_full_window is true OR crop_pct is None,
      return the full window rect.
    - Otherwise compute the % crop.
    """
    cfg = load_config()
    cap = cfg.get("scraping", {}).get("capture", {})
    if cap.get("force_full_window", False) or crop_pct is None:
        return _window_rect(hwnd)

    # allow a sentinel "full" dict too (left=0,top=0,right=1,bottom=1)
    if isinstance(crop_pct, dict):
        if (
            abs(crop_pct.get("left", 0.0) - 0.0) < 1e-6
            and abs(crop_pct.get("top", 0.0) - 0.0) < 1e-6
            and abs(crop_pct.get("right", 1.0) - 1.0) < 1e-6
            and abs(crop_pct.get("bottom", 1.0) - 1.0) < 1e-6
        ):
            return _window_rect(hwnd)

    # percentage crop relative to the window
    x1, y1, x2, y2 = _window_rect(hwnd)
    w, h = max(1, x2 - x1), max(1, y2 - y1)
    left   = int(x1 + crop_pct["left"]   * w)
    top    = int(y1 + crop_pct["top"]    * h)
    right  = int(x1 + crop_pct["right"]  * w)
    bottom = int(y1 + crop_pct["bottom"] * h)
    return (left, top, right, bottom)

def screenshot_region(hwnd, crop_pct):
    """
    Capture a region (or full window) using DirectX (dxcam) first,
    with MSS as a fallback.
    """
    region_abs = _region_abs_from_cfg(hwnd, crop_pct)

    # Try DX (handles UWP/streamed surfaces)
    try:
        return grab_window_region(hwnd, region_abs)
    except Exception:
        # Fallback to GDI screen grab; may be black on some surfaces
        left, top, right, bottom = region_abs
        with mss() as sct:
            raw = sct.grab({
                "left": left,
                "top": top,
                "width": max(1, right - left),
                "height": max(1, bottom - top),
            })
            return Image.frombytes("RGB", raw.size, raw.rgb)

def ocr_text(pil_image, lang="eng"):
    _ensure_tesseract_cmd()
    return pytesseract.image_to_string(pil_image, lang=lang)

def ocr_window_region(hwnd, crop_pct, lang="eng"):
    img = screenshot_region(hwnd, crop_pct)
    text = ocr_text(img, lang=lang)
    return text, img
