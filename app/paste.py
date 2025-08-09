# app/paste.py
from typing import Optional, Tuple
import os, subprocess, shutil, time, ctypes
import win32gui, win32con, win32api, win32process
from .util import load_config
from .display_detect import get_selected_hwnd

# ---------- Optional AHK script (v2) ----------
_AHK_SCRIPT_NAME = "paste_ahk.ahk"
_AHK_V2_SCRIPT = r"""#Requires AutoHotkey v2.0
SetTitleMatchMode("RegEx")
mode      := A_Args.Length >= 1 ? A_Args[1] : "focus" ; focus|nofocus
target    := A_Args.Length >= 2 ? A_Args[2] : ""       ; "hwnd:12345" or title
replyPath := A_Args.Length >= 3 ? A_Args[3] : ""
strategy  := A_Args.Length >= 4 ? A_Args[4] : "type"   ; "type"|"paste"|"auto"

text := ""
if FileExist(replyPath) {
    text := FileRead(replyPath, "UTF-8")
}

if (mode = "focus") {
    if (SubStr(target,1,5) = "hwnd:") {
        hwnd := Integer(SubStr(target,6))
        ahkId := "ahk_id " . Format("0x{:X}", hwnd)
        WinActivate(ahkId)
        WinWaitActive(ahkId,, 2)
    } else if (target != "") {
        WinActivate(target)
        WinWaitActive(target,, 2)
    }
}

SendSleep(5)
if (strategy = "paste") {
    cb := ClipboardAll()
    try {
        Clipboard := ""
        Clipboard := text
        ClipWait(2)
        Send("^v")
    } finally {
        Sleep(100)
        Clipboard := cb
    }
} else if (strategy = "type") {
    SendText(text)  ; types literally, good for Phone Link
} else {
    ; auto: try paste, then (after a short delay) type as fallback
    cb := ClipboardAll()
    try {
        Clipboard := ""
        Clipboard := text
        ClipWait(1)
        Send("^v")
        Sleep(150)
        ; optional: comment the next line if paste works for you
        ; SendText(text)
    } finally {
        Sleep(100)
        Clipboard := cb
    }
}
"""

def _find_ahk_exe(cfg) -> Optional[str]:
    p = (cfg.get("ahk", {}) or {}).get("exe_path")
    if p and os.path.isfile(p): return p
    candidates = [
        r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe",
        r"C:\Program Files\AutoHotkey\v2\AutoHotkey.exe",
        r"C:\Program Files\AutoHotkey\AutoHotkey64.exe",
        r"C:\Program Files\AutoHotkey\AutoHotkey.exe",
    ]
    for c in candidates:
        if os.path.isfile(c): return c
    return shutil.which("AutoHotkey.exe") or shutil.which("AutoHotkey64.exe")

def _ensure_ahk_script(script_path: str):
    if not os.path.isfile(script_path):
        os.makedirs(os.path.dirname(script_path), exist_ok=True)
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(_AHK_V2_SCRIPT)

# ---------- Win32 typing fallback (UNICODE keystrokes) ----------
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

def _send_unicode_char(ch: str, up: bool=False):
    code = ord(ch)
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
    ki = KEYBDINPUT(0, code, flags, 0, None)
    inp = INPUT(INPUT_KEYBOARD, ki)
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def _type_text_unicode(s: str):
    # normalize newlines
    s = s.replace("\r\n", "\n")
    for ch in s:
        if ch == "\n":
            # Enter is not unicode—send virtual key press/release
            win32api.keybd_event(0x0D, 0, 0, 0)                    # VK_RETURN down
            win32api.keybd_event(0x0D, 0, KEYEVENTF_KEYUP, 0)      # VK_RETURN up
        else:
            _send_unicode_char(ch, up=False)
            _send_unicode_char(ch, up=True)
        time.sleep(0.0015)  # tiny pacing so Phone Link doesn’t drop characters

def _focus_hwnd(hwnd: int) -> bool:
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        cur = win32gui.GetForegroundWindow()
        tid1 = win32api.GetCurrentThreadId()
        tid2 = win32process.GetWindowThreadProcessId(cur)[0] if cur else 0
        ctypes.windll.user32.AttachThreadInput(tid1, tid2, True)
        win32gui.SetForegroundWindow(hwnd)
        win32gui.SetActiveWindow(hwnd)
        ctypes.windll.user32.AttachThreadInput(tid1, tid2, False)
        time.sleep(0.06)
        return True
    except Exception:
        return False

# ---------- public API ----------
def paste_text(text: str,
               mode: Optional[str] = None,
               window_title: str = "Phone Link",
               hwnd: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    mode: 'focus_phone_link' | 'paste_at_cursor' | None
    Uses AHK if available; else Win32 Unicode typing.
    """
    cfg = load_config()
    resolved_mode = mode or cfg.get("target", {}).get("paste_mode", "focus_phone_link")
    strategy = (cfg.get("ahk", {}) or {}).get("paste_strategy", "type")  # default to typing

    # Focus the target window if requested
    if resolved_mode == "focus_phone_link":
        h = hwnd or get_selected_hwnd()
        if h:
            _focus_hwnd(h)

    # Prefer AHK if present
    ahk_exe = _find_ahk_exe(cfg)
    if ahk_exe:
        script = os.path.join(os.path.dirname(__file__), _AHK_SCRIPT_NAME)
        _ensure_ahk_script(script)
        tmpdir = os.path.join(os.path.dirname(__file__), "_tmp"); os.makedirs(tmpdir, exist_ok=True)
        reply_path = os.path.join(tmpdir, "reply.txt")
        with open(reply_path, "w", encoding="utf-8") as f:
            f.write(text)
        target_arg = f"hwnd:{hwnd or get_selected_hwnd()}" if (hwnd or get_selected_hwnd()) else window_title
        mode_arg = "focus" if resolved_mode == "focus_phone_link" else "nofocus"
        strat_arg = strategy  # "type" recommended for Phone Link
        try:
            subprocess.Popen([ahk_exe, script, mode_arg, target_arg, reply_path, strat_arg], shell=False)
            return True, None
        except Exception:
            # Fall through to Win32 typing if AHK launch fails
            pass

    # Win32 fallback: type it
    try:
        _type_text_unicode(text)
        return True, None
    except Exception as e:
        return False, str(e)
