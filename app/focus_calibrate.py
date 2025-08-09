# app/focus_calibrate.py
import time, ctypes
import win32api, win32gui
from tkinter import Toplevel, ttk, StringVar, messagebox
from .util import load_config, save_config
from .display_detect import get_selected_hwnd, enumerate_windows

# --- DPI awareness (make coords consistent on mixed DPI) ---
def _set_dpi_awareness():
    try:
        # Per Monitor V2 if available
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        PMV2 = ctypes.c_void_p(-4)
        user32.SetProcessDpiAwarenessContext(PMV2)
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

VK_LBUTTON = 0x01
GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState

def _wait_for_left_click(timeout=12):
    start = time.time()
    was_down = bool(GetAsyncKeyState(VK_LBUTTON) & 0x8000)
    while time.time() - start < timeout:
        down = bool(GetAsyncKeyState(VK_LBUTTON) & 0x8000)
        if down and not was_down:
            return win32api.GetCursorPos()
        was_down = down
        time.sleep(0.01)
    return None

def _resolve_hwnd():
    h = get_selected_hwnd()
    if h and win32gui.IsWindow(h):
        return h
    names = ["PhoneExperienceHost.exe","YourPhone.exe","YourPhoneAppProxy.exe"]
    wins = enumerate_windows(filter_proc_names=names)
    for w in wins:
        return int(w["hwnd"])
    return None

class FocusCalibrator(Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Set Focus Point")
        self.geometry("520x180")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.msg = StringVar(value="1) Open the chat.\n2) Click START, then click inside the message box.\n   (You have ~12 seconds.)")
        ttk.Label(self, textvariable=self.msg, justify="left").pack(padx=12, pady=(12,8), anchor="w")
        bar = ttk.Frame(self); bar.pack(fill="x", padx=12, pady=(0,12))
        ttk.Button(bar, text="Start", command=self.on_start).pack(side="left")
        ttk.Button(bar, text="Close", command=self.destroy).pack(side="right")

    def on_start(self):
        hwnd = _resolve_hwnd()
        if not hwnd:
            messagebox.showwarning("Wingman", "No target window found. Choose Window… first.")
            return
        self.msg.set("Waiting for your click in the message box…")
        self.update_idletasks()
        pt = _wait_for_left_click()
        if not pt:
            self.msg.set("Timed out. Try again."); return

        sx, sy = pt  # screen coords of your click
        # Convert to CLIENT coords and normalize by client size
        # Client rect is (0,0,w,h); we need client size, and screen position of client origin
        cx0, cy0, cx1, cy1 = (0,0,0,0)
        # pywin32: GetClientRect returns (left, top, right, bottom) relative to client (0,0,w,h)
        rc = win32gui.GetClientRect(hwnd)  # (0,0,w,h)
        cw, ch = rc[2], rc[3]
        ox, oy = win32gui.ClientToScreen(hwnd, (0,0))  # client origin in screen coords

        # If click not in client, warn (you might have clicked the title bar)
        if not (ox <= sx <= ox+cw and oy <= sy <= oy+ch):
            messagebox.showwarning("Wingman", "Your click wasn’t inside the CONTENT area. Try again a bit higher.")
            return

        x_pct = round((sx - ox)/max(1, cw), 4)
        y_pct = round((sy - oy)/max(1, ch), 4)

        cfg = load_config()
        fc = cfg.setdefault("input", {}).setdefault("focus_click", {})
        fc["relative_to"] = "client"
        fc["x_pct"] = x_pct
        fc["y_pct"] = y_pct
        # Optional nudges default to 0 (px)
        fc.setdefault("x_offset_px", 0)
        fc.setdefault("y_offset_px", 0)
        from .util import save_config as _save
        _save(cfg)

        self.msg.set(f"Saved (client-relative): x={x_pct:.3f}, y={y_pct:.3f}. Close this window.")
        messagebox.showinfo("Wingman", f"Saved focus point (client):\nX {x_pct:.3f}, Y {y_pct:.3f}")