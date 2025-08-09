from typing import Optional, Dict, Any
import re, time, ctypes
import win32gui, win32con, win32api, win32process

from .display_detect import enumerate_windows, get_selected_hwnd

# ---- Win32 primitives ----
PUL = ctypes.POINTER(ctypes.c_ulong)
KEYEVENTF_KEYUP   = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD    = 1

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

def _sleep(ms: int): 
    if ms and ms > 0: time.sleep(ms/1000.0)

def _send_unicode_char(ch: str, up: bool=False):
    code = ord(ch)
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
    ki = KEYBDINPUT(0, code, flags, 0, None)
    inp = INPUT(INPUT_KEYBOARD, ki)
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def _type_text_unicode(text: str, per_char_delay: float = 0.002):
    text = text.replace("\r\n", "\n")
    for ch in text:
        if ch == "\n":
            win32api.keybd_event(0x0D, 0, 0, 0)               # Enter down
            win32api.keybd_event(0x0D, 0, KEYEVENTF_KEYUP, 0) # Enter up
        else:
            _send_unicode_char(ch, up=False)
            _send_unicode_char(ch, up=True)
        if per_char_delay > 0:
            time.sleep(per_char_delay)

def _bring_to_foreground(hwnd: int, settle_ms: int = 250) -> bool:
    ok = False
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        if win32gui.GetForegroundWindow() != hwnd:
            # ALT trick
            VK_MENU = 0x12
            win32api.keybd_event(VK_MENU, 0, 0, 0)
            try:
                win32gui.SetForegroundWindow(hwnd)
            finally:
                win32api.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        if win32gui.GetForegroundWindow() != hwnd:
            # AttachThreadInput fallback
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
        ok = (win32gui.GetForegroundWindow() == hwnd)
    except Exception:
        ok = False
    _sleep(settle_ms)
    return ok

def _find_hwnd_by_title_regex(title_regex: str) -> Optional[int]:
    # Prefer saved window if present
    saved = get_selected_hwnd()
    if saved and win32gui.IsWindow(saved):
        return saved
    try:
        rx = re.compile(title_regex, re.I)
    except re.error:
        rx = re.compile(r"Tinder|Phone Link|Your Phone", re.I)
    wins = enumerate_windows()
    for w in wins:
        if rx.search(w.get("title", "") or ""):
            return int(w["hwnd"])
    return None

# ---- Public API (tool surface) ----
def focus_window(title_regex: str = r"Tinder|Phone Link|Your Phone",
                 timeout: float = 3.0) -> Dict[str, Any]:
    hwnd = _find_hwnd_by_title_regex(title_regex)
    if not hwnd:
        return {"ok": False, "error": f"No window matching /{title_regex}/ found"}
    ok = _bring_to_foreground(hwnd, settle_ms=int(timeout*250))
    return {"ok": ok, "error": None if ok else "Failed to focus window"}

def type_text(text: str, per_char_delay: float = 0.002) -> Dict[str, Any]:
    try:
        _type_text_unicode(text, per_char_delay=per_char_delay)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def press_enter(times: int = 1) -> Dict[str, Any]:
    try:
        for _ in range(max(1, times)):
            win32api.keybd_event(0x0D, 0, 0, 0)
            win32api.keybd_event(0x0D, 0, KEYEVENTF_KEYUP, 0)
            _sleep(60)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}