# app/display_detect.py
import ctypes
from ctypes import wintypes
import yaml
import psutil
import win32gui, win32con, win32process, win32api

from .util import load_config, save_config

MDT_EFFECTIVE_DPI = 0  # per-monitor effective DPI
shcore = ctypes.WinDLL('Shcore')
user32 = ctypes.WinDLL('User32')

# signatures
shcore.GetDpiForMonitor.argtypes = [wintypes.HMONITOR, ctypes.c_int,
                                    ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
shcore.GetDpiForMonitor.restype  = ctypes.c_long
user32.EnumDisplayMonitors.restype = ctypes.c_bool

def get_monitors():
    monitors = []
    def cb(hMonitor, hdcMonitor, lprcMonitor, dwData):
        rc = ctypes.cast(lprcMonitor, ctypes.POINTER(wintypes.RECT)).contents
        dpiX = ctypes.c_uint(0); dpiY = ctypes.c_uint(0)
        shcore.GetDpiForMonitor(hMonitor, MDT_EFFECTIVE_DPI, ctypes.byref(dpiX), ctypes.byref(dpiY))
        scale = round(dpiX.value / 96.0, 2)
        monitors.append({
            "hmonitor": int(hMonitor),
            "left": rc.left, "top": rc.top, "right": rc.right, "bottom": rc.bottom,
            "width": rc.right - rc.left, "height": rc.bottom - rc.top,
            "dpiX": int(dpiX.value), "dpiY": int(dpiY.value), "scale": scale
        })
        return True

    MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC,
                                         ctypes.POINTER(wintypes.RECT), ctypes.c_long)
    user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(cb), 0)
    return monitors

# ---------- window enumeration / selection ----------

def _proc_name_from_hwnd(hwnd):
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        p = psutil.Process(pid)
        return p.name()
    except Exception:
        return None

def _is_window_ok(hwnd):
    if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
        return False
    if win32gui.IsIconic(hwnd):  # minimized
        return False
    # Skip tool windows
    exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    if exstyle & win32con.WS_EX_TOOLWINDOW:
        return False
    # Must have some text or a recognizable class
    title = (win32gui.GetWindowText(hwnd) or "").strip()
    cls = (win32gui.GetClassName(hwnd) or "").strip()
    return bool(title or cls)

def enumerate_windows(filter_proc_names=None):
    """
    Returns list of dicts: {hwnd, title, class, proc, rect}
    If filter_proc_names is given, only include those processes.
    """
    results = []
    def enum_cb(hwnd, _param):
        try:
            if not _is_window_ok(hwnd):
                return True
            proc = _proc_name_from_hwnd(hwnd)
            if filter_proc_names and proc not in filter_proc_names:
                return True
            title = win32gui.GetWindowText(hwnd)
            cls = win32gui.GetClassName(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            results.append({
                "hwnd": hwnd,
                "title": title,
                "class": cls,
                "proc": proc,
                "rect": rect,
            })
        except Exception:
            pass
        return True
    win32gui.EnumWindows(enum_cb, None)
    # Sort a bit: by process then by title length
    results.sort(key=lambda r: (r["proc"] or "", len(r["title"] or "")), reverse=True)
    return results

def get_selected_hwnd():
    cfg = load_config()
    sel = cfg.get("scraping", {}).get("selected_hwnd")
    if isinstance(sel, int) and win32gui.IsWindow(sel):
        return sel
    return None

def set_selected_hwnd(hwnd: int | None, config_path="config.yaml"):
    cfg = load_config(config_path)
    cfg.setdefault("scraping", {})
    if hwnd is None:
        cfg["scraping"].pop("selected_hwnd", None)
    else:
        cfg["scraping"]["selected_hwnd"] = int(hwnd)
    save_config(cfg, config_path)

def list_phone_link_windows(process_names=None):
    """Process-focused list helpful for debug (Phone Link / streaming windows)."""
    if process_names is None:
        cfg = load_config()
        process_names = cfg.get("targets", {}).get("phone_link", {}).get(
            "process_names", ["PhoneExperienceHost.exe", "YourPhone.exe"]
        )
    return enumerate_windows(filter_proc_names=process_names)

def find_phone_link_hwnd():
    """
    Returns the effective target window handle:
    1) Your selected hwnd from config (if still valid).
    2) A window owned by the Phone Link process (streaming surface often titled 'Tinder', etc).
    3) Fallback: title-based Phone Link window.
    """
    sel = get_selected_hwnd()
    if sel and _is_window_ok(sel):
        return sel

    cfg = load_config()
    proc_names = cfg.get("targets", {}).get("phone_link", {}).get(
        "process_names", ["PhoneExperienceHost.exe", "YourPhone.exe"]
    )
    wins = enumerate_windows(filter_proc_names=proc_names)
    if wins:
        # Prefer non-'Settings' titles
        for w in wins:
            t = (w["title"] or "").lower()
            if t and "settings" not in t:
                return w["hwnd"]
        return wins[0]["hwnd"]

    # Final fallback: title search
    titles = ["Phone Link","Link to Windows","Your Phone"]
    for t in titles:
        hwnd = win32gui.FindWindow(None, t)
        if hwnd and _is_window_ok(hwnd):
            return hwnd
    return None

# ---------- DPI detect writeback ----------

def detect_and_update_config(config_path="config.yaml"):
    cfg = load_config(config_path)
    monitors = get_monitors()
    hwnd = find_phone_link_hwnd()
    active = None
    if hwnd:
        MONITOR_DEFAULTTONEAREST = 2
        hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        for m in monitors:
            if m["hmonitor"] == int(hmon):
                active = m
                break
    cfg.setdefault("scraping", {})
    cfg["scraping"]["monitors"] = monitors
    cfg["scraping"]["active_monitor"] = active
    # Slight nudge for very high scaling
    if active and active.get("scale", 1.0) > 1.5:
        cfg.setdefault("targets", {}).setdefault("phone_link", {}).setdefault("chat_crop", {})
        cfg["targets"]["phone_link"]["chat_crop"] = {
            "left": 0.30, "top": 0.14, "right": 0.90, "bottom": 0.86
        }
    save_config(cfg, config_path)
    return monitors, active
