import ctypes
from ctypes import wintypes
import yaml
from .util import load_config, save_config
import win32gui, win32con

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

def find_phone_link_hwnd():
    titles = ["Phone Link","Link to Windows","Your Phone"]
    for t in titles:
        hwnd = win32gui.FindWindow(None, t)
        if hwnd:
            return hwnd
    hwnd = win32gui.FindWindow("ApplicationFrameWindow", None)
    while hwnd:
        if any(t in win32gui.GetWindowText(hwnd) for t in titles):
            return hwnd
        hwnd = win32gui.GetWindow(hwnd, win32con.GW_HWNDNEXT)
    return None

def detect_and_update_config(config_path="config.yaml"):
    cfg = load_config(config_path)
    monitors = get_monitors()
    # try to find monitor containing Phone Link
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
    # adjust crop slightly for very high scaling
    if active and active.get("scale",1.0) > 1.5:
        # nudge chat crop inward to avoid chrome
        cfg.setdefault("targets",{}).setdefault("phone_link",{}).setdefault("chat_crop",{})
        cfg["targets"]["phone_link"]["chat_crop"] = { "left": 0.30, "top": 0.14, "right": 0.90, "bottom": 0.86 }
    save_config(cfg, config_path)
    return monitors, active
