# app/crop_tuner.py
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

from .util import load_config, save_config
from .display_detect import find_phone_link_hwnd
from .ocr_fallback import screenshot_region

PRESETS = {
    "Tinder • Chat (center/right)":   {"left": 0.18, "top": 0.12, "right": 0.92, "bottom": 0.88},
    "Tinder • Profile (right panel)": {"left": 0.60, "top": 0.08, "right": 0.98, "bottom": 0.92},
    "Full window":                    {"left": 0.00, "top": 0.00, "right": 1.00, "bottom": 1.00},
}

class CropTuner(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Crop Tuner")
        self.geometry("980x720")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.cfg = load_config()
        self.target_key = tk.StringVar(value="chat")  # "chat" or "profile"
        self.preset = tk.StringVar(value="Tinder • Profile (right panel)")
        self.preview_imgtk = None
        self.preview_size = (480, 720)

        # Top bar
        top = ttk.Frame(self, padding=8); top.pack(fill="x")
        ttk.Label(top, text="Target:").pack(side="left")
        ttk.Combobox(top, state="readonly", values=["chat","profile"], textvariable=self.target_key, width=10)\
            .pack(side="left", padx=(6,12))
        ttk.Label(top, text="Preset:").pack(side="left")
        self.preset_box = ttk.Combobox(top, state="readonly", values=list(PRESETS.keys()),
                                       textvariable=self.preset, width=28)
        self.preset_box.pack(side="left", padx=(6,12))
        ttk.Button(top, text="Apply preset", command=self.apply_preset).pack(side="left", padx=(0,12))
        ttk.Button(top, text="Refresh Preview", command=self.refresh_preview).pack(side="left", padx=(0,12))
        ttk.Button(top, text="Save", command=self.save_crop).pack(side="right")

        # Center: preview + sliders
        center = ttk.Frame(self, padding=8); center.pack(fill="both", expand=True)

        # Preview canvas
        left = ttk.Frame(center); left.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(left, width=self.preview_size[0], height=self.preview_size[1], bg="#222")
        self.canvas.pack(fill="both", expand=True)
        self.meta = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.meta).pack(anchor="w", pady=(6,0))

        # Sliders
        right = ttk.Frame(center); right.pack(side="right", fill="y")
        self.s_left = self._mk_slider(right, "left", 0.00, 0.95)
        self.s_top = self._mk_slider(right, "top", 0.00, 0.95)
        self.s_right = self._mk_slider(right, "right", 0.05, 1.00, init=0.98)
        self.s_bottom = self._mk_slider(right, "bottom", 0.05, 1.00, init=0.92)
        ttk.Button(right, text="Preview", command=self.refresh_preview).pack(fill="x", pady=(6,0))

        # Initialize from config
        self._load_current_crop()
        self.after(100, self.refresh_preview)

    def _mk_slider(self, parent, label, mn, mx, init=None):
        frm = ttk.Frame(parent); frm.pack(fill="x", pady=4)
        ttk.Label(frm, text=label.upper()).pack(anchor="w")
        var = tk.DoubleVar(value=init if init is not None else 0.5)
        s = ttk.Scale(frm, from_=mn, to=mx, orient="horizontal", variable=var, command=lambda _v: None)
        s.pack(fill="x")
        box = ttk.Entry(frm, width=8); box.pack(anchor="e")
        def sync_entry(*_):
            box.delete(0, tk.END); box.insert(0, f"{var.get():.3f}")
        def sync_slider(*_):
            try:
                v = float(box.get()); v = max(mn, min(mx, v)); var.set(v)
            except Exception: pass
        var.trace_add("write", lambda *_: sync_entry())
        box.bind("<Return>", lambda _e: sync_slider())
        sync_entry()
        setattr(self, f"var_{label}", var)
        return s

    def _current_crop_obj(self):
        return {
            "left":   float(self.var_left.get()),
            "top":    float(self.var_top.get()),
            "right":  float(self.var_right.get()),
            "bottom": float(self.var_bottom.get()),
        }

    def _load_current_crop(self):
        tkey = "chat_crop" if self.target_key.get() == "chat" else "profile_crop"
        cur = self.cfg.get("targets", {}).get("phone_link", {}).get(tkey, PRESETS["Full window"])
        self.var_left.set(float(cur.get("left", 0.0)))
        self.var_top.set(float(cur.get("top", 0.0)))
        self.var_right.set(float(cur.get("right", 1.0)))
        self.var_bottom.set(float(cur.get("bottom", 1.0)))

    def apply_preset(self):
        crop = PRESETS[self.preset.get()]
        self.var_left.set(crop["left"])
        self.var_top.set(crop["top"])
        self.var_right.set(crop["right"])
        self.var_bottom.set(crop["bottom"])
        self.refresh_preview()

    def refresh_preview(self):
        hwnd = find_phone_link_hwnd()
        if not hwnd:
            messagebox.showwarning("Wingman", "Target window not found. Use “Choose Window…” first.")
            return
        crop = self._current_crop_obj()
        try:
            img = screenshot_region(hwnd, crop)
        except Exception as e:
            messagebox.showwarning("Wingman", f"Capture failed: {e}")
            return

        # scale to fit canvas
        W, H = self.canvas.winfo_width() or self.preview_size[0], self.canvas.winfo_height() or self.preview_size[1]
        im2 = img.copy()
        im2.thumbnail((W, H))
        self.preview_imgtk = ImageTk.PhotoImage(im2)
        self.canvas.delete("all")
        self.canvas.create_image(W//2, H//2, image=self.preview_imgtk)
        self.meta.set(f"Crop: L{crop['left']:.3f}, T{crop['top']:.3f}, R{crop['right']:.3f}, B{crop['bottom']:.3f} | "
                      f"Preview {im2.size[0]}×{im2.size[1]} (src {img.size[0]}×{img.size[1]})")

    def save_crop(self):
        tkey = "chat_crop" if self.target_key.get() == "chat" else "profile_crop"
        self.cfg.setdefault("targets", {}).setdefault("phone_link", {})[tkey] = self._current_crop_obj()
        save_config(self.cfg)
        messagebox.showinfo("Wingman", f"Saved {tkey} to config.yaml")
