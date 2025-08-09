# app/paste.py
from typing import Optional, Tuple
import time, ctypes
import win32gui, win32con, win32api, win32process
from .util import load_config
from .display_detect import get_selected_hwnd, enumerate_windows
from .vision_find import locate_message_input  # <-- NEW

# --- Win32 typing primitives ---
PUL = ctypes.POINTER(ctypes.c_ulong)
KEYEVENTF_KEYUP    = 0x0002
KEYEVENTF_UNICODE  = 0x0004
INPUT_KEYBOARD     = 1

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]
class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ki", KEYBDINPUT)]

SendInput = ctypes.windll.user32.SendInput

def _sleep_ms(ms: int):
    if ms and ms > 0:
        time.sleep(ms/1000.0)

def _send_unicode_char(ch: str, up: bool=False):
    code = ord(ch)
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
    ki = KEYBDINPUT(0, code, flags, 0, None)
    inp = INPUT(INPUT_KEYBOARD, ki)
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def _type_text_unicode(s: str, per_char_delay_ms: int = 2):
    s = s.replace("\r\n", "\n")
    for ch in s:
        if ch == "\n":
            win32api.keybd_event(0x0D, 0, 0, 0)
            win32api.keybd_event(0x0D, 0, KEYEVENTF_KEYUP, 0)
        else:
            _send_unicode_char(ch, up=False)
            _send_unicode_char(ch, up=True)
        _sleep_ms(per_char_delay_ms)

def _bring_to_foreground(hwnd: int, settle_ms: int, use_alt_trick: bool = True):
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        if use_alt_trick and win32gui.GetForegroundWindow() != hwnd:
            VK_MENU = 0x12
            win32api.keybd_event(VK_MENU, 0, 0, 0)
            try:
                win32gui.SetForegroundWindow(hwnd)
            finally:
                win32api.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        if win32gui.GetForegroundWindow() != hwnd:
            cur = win32gui.GetForegroundWindow()
            tid1 = win32api.GetCurrentThreadId()
            tid2 = win32process.GetWindowThreadProcessId(cur)[0] if cur else 0
            ctypes.windll.user32.AttachThreadInput(tid1, tid2, True)
            try:
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetActiveWindow(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            finally:
                ctypes.windll.user32.AttachThreadInput(tid1, tid2, False)
    except Exception:
        pass
    _sleep_ms(settle_ms)

def _resolve_target_hwnd(cfg) -> Optional[int]:
    h = get_selected_hwnd()
    if h and win32gui.IsWindow(h):
        return h
    names = (cfg.get("targets", {}).get("phone_link", {}).get("process_names")
             or ["PhoneExperienceHost.exe","YourPhone.exe","YourPhoneAppProxy.exe"])
    wins = enumerate_windows(filter_proc_names=names)
    for w in wins:
        title = (w.get("title") or "").lower()
        if "settings" in title:
            continue
        return int(w["hwnd"])
    return None

def _click_abs(x: int, y: int, clicks: int = 1, between_click_ms: int = 80):
    win32api.SetCursorPos((x, y))
    for _ in range(max(1, clicks)):
        win32api.mouse_event(0x0002, 0, 0, 0, 0)  # down
        _sleep_ms(10)
        win32api.mouse_event(0x0004, 0, 0, 0, 0)  # up
        _sleep_ms(between_click_ms)

def paste_text(text: str,
               mode: Optional[str] = None,
               window_title: str = "Phone Link",
               hwnd: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    1) Bring the Phone Link window to front
    2) If vision is enabled, ask VLM to find the message box and click it
    3) Type the text (Unicode keystrokes)
    """
    cfg = load_config()
    icfg = (cfg.get("input", {}) or {})
    focus_settle_ms     = int(icfg.get("focus_settle_ms", 300))
    wait_before_type_ms = int(icfg.get("wait_ms_before_type", 120))
    per_char_delay_ms   = int(icfg.get("type_per_char_delay_ms", 2))
    use_alt_trick       = bool(icfg.get("focus_alt_trick", True))

    target_hwnd = hwnd or _resolve_target_hwnd(cfg)
    if target_hwnd:
        _bring_to_foreground(target_hwnd, settle_ms=focus_settle_ms, use_alt_trick=use_alt_trick)

        # Vision-assisted focus (optional)
        vcfg = (cfg.get("vision", {}) or {})
        if vcfg.get("enabled", False):
            try:
                xy = locate_message_input(target_hwnd, prompt=vcfg.get("prompt"))
                if xy:
                    x, y = xy
                    clicks = int(vcfg.get("clicks", 1))
                    between = int(vcfg.get("between_click_ms", 80))
                    _click_abs(x, y, clicks=clicks, between_click_ms=between)
                    _sleep_ms(int(vcfg.get("wait_ms_after_click", 350)))
            except Exception:
                pass

    _sleep_ms(wait_before_type_ms)

    try:
        _type_text_unicode(text, per_char_delay_ms=per_char_delay_ms)
        return True, None
    except Exception as e:
        return False, str(e)
