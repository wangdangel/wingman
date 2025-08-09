# app/desktop_control.py
from typing import Optional, Dict, Any
import time
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

def focus_window(title_regex: str = "Tinder|Phone Link|Your Phone",
                 timeout: float = 3.0) -> Dict[str, Any]:
    """Focus a window by regex on title using UIA (works with UWP/Phone Link)."""
    try:
        desk = Desktop(backend="uia")
        win = desk.window(title_re=title_regex)
        win.set_focus()
        time.sleep(0.15)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def type_text(text: str, per_char_delay: float = 0.0) -> Dict[str, Any]:
    """Type text as keystrokes. Assumes caret already set where you want it."""
    try:
        if per_char_delay > 0:
            for ch in text.replace("\r\n","\n"):
                if ch == "\n":
                    send_keys("{ENTER}")
                else:
                    send_keys(ch, with_spaces=True, pause=per_char_delay)
        else:
            # Single shot; send_keys handles unicode + emojis well with UIA
            for line in text.splitlines():
                send_keys(line, with_spaces=True)
                send_keys("{ENTER}")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def press_enter(times: int = 1):
    try:
        for _ in range(max(1,times)):
            send_keys("{ENTER}")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
