# app/dx_capture.py
import re
from typing import Iterable, List, Optional, Tuple

import numpy as np
import win32api
import win32gui
from PIL import Image

from .util import load_config, save_config

try:
    import dxcam
except Exception:
    dxcam = None  # handled in caller


def _enum_monitor_rects() -> List[Tuple[int, int, int, int]]:
    """Return monitor rects in the order EnumDisplayMonitors gives."""
    rects: List[Tuple[int, int, int, int]] = []

    def _cb(hmon, hdc, lprc, data):
        info = win32api.GetMonitorInfo(hmon)
        rects.append(tuple(info["Monitor"]))
        return True

    win32api.EnumDisplayMonitors(None, None, _cb, None)
    return rects


def _monitor_index_from_hwnd(hwnd: int) -> int:
    """Best-effort: map HWND's monitor to an index within EnumDisplayMonitors order."""
    hmon = win32api.MonitorFromWindow(hwnd, 2)  # NEAREST
    want = tuple(win32api.GetMonitorInfo(hmon)["Monitor"])
    rects = _enum_monitor_rects()
    for i, r in enumerate(rects):
        if r == want:
            return i
    return 0


def _to_rel(region_abs: Tuple[int, int, int, int], mon_rect: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    ax1, ay1, ax2, ay2 = region_abs
    mx1, my1, mx2, my2 = mon_rect
    return max(0, ax1 - mx1), max(0, ay1 - my1), max(0, ax2 - mx1), max(0, ay2 - my1)


def _is_black(img: Image.Image, thresh_mean: float = 6.0) -> bool:
    arr = np.asarray(img)
    return float(arr.mean()) < thresh_mean


def _grab_dx(output_idx: int, rel_region: Tuple[int, int, int, int]) -> Optional[Image.Image]:
    if dxcam is None:
        return None
    cam = dxcam.create(output_idx=output_idx, max_buffer_len=8)
    frame = cam.grab(region=rel_region)  # ndarray BGR (H,W,3)
    if frame is None:
        return None
    frame = frame[..., ::-1]  # BGR -> RGB
    return Image.fromarray(frame)


def grab_window_region(hwnd: int, region_abs: Tuple[int, int, int, int]) -> Image.Image:
    """
    Capture a rectangular region of the selected window using DirectX.
    - Tries config override first (scraping.capture.output_index_override)
    - Then tries our guessed index from the window's monitor
    - Then (if enabled) probes all outputs until it finds a non-black image
    Returns a PIL RGB Image or raises RuntimeError.
    """
    cfg = load_config()
    cap_cfg = cfg.get("scraping", {}).get("capture", {})
    try_all = bool(cap_cfg.get("try_all_outputs", True))
    override = cap_cfg.get("output_index_override")
    rects = _enum_monitor_rects()
    n = max(1, len(rects))

    # Build candidate (output_idx, rect_index) pairs
    candidates: list[tuple[int, int]] = []

    # Override first (use same rect index if plausible, else try all rects)
    if isinstance(override, int) and 0 <= override < n:
        # Prefer pairing override with same index rect if it exists
        candidates.append((override, min(override, n - 1)))
        if try_all:
            for ri in range(n):
                if ri != min(override, n - 1):
                    candidates.append((override, ri))

    # Guess from HWND's monitor
    guess = _monitor_index_from_hwnd(hwnd)
    candidates.append((min(guess, n - 1), min(guess, n - 1)))

    # Then try parallel indices
    for i in range(n):
        if (i, i) not in candidates:
            candidates.append((i, i))

    # Finally, if allowed, brute-force all idx/rect combos
    if try_all:
        for oi in range(n):
            for ri in range(n):
                pair = (oi, ri)
                if pair not in candidates:
                    candidates.append(pair)

    # Try candidates in order
    for oi, ri in candidates:
        rel = _to_rel(region_abs, rects[ri])
        img = _grab_dx(oi, rel)
        if img is None:
            continue
        if not _is_black(img):
            # Persist last working output index (quality-of-life)
            try:
                cfg.setdefault("scraping", {}).setdefault("capture", {})["last_working_output_index"] = oi
                save_config(cfg)
            except Exception:
                pass
            return img

    raise RuntimeError("dxcam failed to capture a non-black image from any output")
