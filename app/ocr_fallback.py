# app/ocr_fallback.py
import os
import ctypes
from ctypes import wintypes
import win32gui, win32con, win32api
from mss import mss
from PIL import Image
import pytesseract
from .util import load_config

# ---------- DPI awareness (so GetWindowRect matches screen pixels) ----------
def _set_dpi_awareness():
    try:
        # Try per-monitor v2 (Windows 10+)
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)  # (HANDLE)-4
        user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        return
    except Exception:
        pass
    try:
        # Fallback: Shcore (Windows 8.1+)
        shcore = ctypes.WinDLL("Shcore")
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        # 2 = PROCESS_PER_MONITOR_DPI_AWARE
        shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        # Last resort
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

_set_dpi_awareness()

# ---------- Helpers ----------
def _get_window_rect(hwnd):
    # Physical pixels (with DPI awareness set above)
    x1, y1, x2, y2 = win32gui.GetWindowRect(hwnd)
    return x1, y1, x2, y2

def _get_monitor_rect_from_hwnd(hwnd):
    MONITOR_DEFAULTTONEAREST = 2
    hmon = win32api.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = win32api.GetMonitorInfo(hmon)
    # 'Monitor' key gives full monitor area (left, top, right, bottom)
    return info['Monitor']

def _intersect(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    left, top = max(ax1, bx1), max(ay1, by1)
    right, bottom = min(ax2, bx2), min(ay2, by2)
    if right <= left or bottom <= top:
        return None
    return (left, top, right, bottom)

def _safe_region_from_pct(hwnd, crop_pct):
    # Calculate region from the WINDOW rect, then clamp to that monitor
    wx1, wy1, wx2, wy2 = _get_window_rect(hwnd)
    ww, wh = wx2 - wx1, wy2 - wy1
    left   = int(wx1 + crop_pct['left']   * ww)
    top    = int(wy1 + crop_pct['top']    * wh)
    right  = int(wx1 + crop_pct['right']  * ww)
    bottom = int(wy1 + crop_pct['bottom'] * wh)

    # Clamp to monitor bounds to avoid off-screen issues on mixed DPI
    mx1, my1, mx2, my2 = _get_monitor_rect_from_hwnd(hwnd)
    region = _intersect((left, top, right, bottom), (mx1, my1, mx2, my2))
    return region  # (left, top, right, bottom) or None

def _ensure_tesseract_cmd():
    try:
        cfg = load_config()
        tpath = cfg.get("scraping", {}).get("tesseract_path")
        if tpath and os.path.exists(tpath):
            pytesseract.pytesseract.tesseract_cmd = tpath
    except Exception:
        pass

# ---------- Main capture API ----------
def screenshot_region(hwnd, crop_pct):
    region = _safe_region_from_pct(hwnd, crop_pct)
    if not region:
        # as a fallback, capture the whole window bounds
        region = _get_window_rect(hwnd)
    left, top, right, bottom = region
    width, height = max(1, right - left), max(1, bottom - top)

    with mss() as sct:
        # mss expects absolute virtual-screen coords; negatives are OK on multi-monitor
        raw = sct.grab({"left": left, "top": top, "width": width, "height": height})
        pil = Image.frombytes("RGB", raw.size, raw.rgb)
    return pil

def ocr_text(pil_image, lang="eng"):
    _ensure_tesseract_cmd()
    return pytesseract.image_to_string(pil_image, lang=lang)

def ocr_window_region(hwnd, crop_pct, lang="eng"):
    pil = screenshot_region(hwnd, crop_pct)
    text = ocr_text(pil, lang=lang)
    return text, pil
