import tkinter as tk
from tkinter import ttk, messagebox
import threading, time, os
from .util import load_config, save_config
from .display_detect import detect_and_update_config
from .orchestrator import read_profile, read_chat, generate, persist_everything, paste_selected
from .logging_setup import setup_logging

logger = setup_logging("./logs", "INFO")

class WingmanUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Wingman")
        self.cfg = load_config()
        if self.cfg['ui'].get('topmost', True):
            self.root.wm_attributes("-topmost", 1)

        main = ttk.Frame(root, padding=8); main.pack(fill="both", expand=True)
        # Target & paste mode
        row1 = ttk.Frame(main); row1.pack(fill="x", pady=(0,6))
        ttk.Label(row1, text="Target:").pack(side="left")
        self.target_var = tk.StringVar(value=self.cfg['target']['default'])
        targets = [("Phone Link","phone_link"),("Browser (Edge)","browser_edge"),
                   ("Browser (Chrome)","browser_chrome"),("Auto-detect","auto")]
        self.target_combo = ttk.Combobox(row1, state="readonly",
                                         values=[t[1] for t in targets], textvariable=self.target_var, width=18)
        self.target_combo.pack(side="left", padx=(6,12))

        ttk.Label(row1, text="Paste:").pack(side="left")
        self.paste_var = tk.StringVar(value=self.cfg['target']['paste_mode'])
        paste_opts = [("Focus Phone Link","focus_phone_link"),("Paste at cursor","paste_at_cursor")]
        self.paste_combo = ttk.Combobox(row1, state="readonly",
                                        values=[p[1] for p in paste_opts], textvariable=self.paste_var, width=18)
        self.paste_combo.pack(side="left", padx=(6,12))

        self.btn_detect = ttk.Button(row1, text="Detect Displays / DPI", command=self.on_detect)
        self.btn_detect.pack(side="right")

        # Profile & chat
        row2 = ttk.Frame(main); row2.pack(fill="x", pady=(0,6))
        self.btn_profile = ttk.Button(row2, text="Read Profile", command=self.on_profile)
        self.btn_profile.pack(side="left", padx=(0,6))
        self.btn_chat = ttk.Button(row2, text="Read Chat", command=self.on_chat)
        self.btn_chat.pack(side="left", padx=(0,6))
        self.btn_generate = ttk.Button(row2, text="Generate 3–5", command=self.on_generate)
        self.btn_generate.pack(side="left", padx=(0,6))
        self.btn_paste = ttk.Button(row2, text="Paste", command=self.on_paste)
        self.btn_paste.pack(side="right")

        # Custom request
        row3 = ttk.Frame(main); row3.pack(fill="x", pady=(0,6))
        ttk.Label(row3, text="Custom request:").pack(side="left")
        self.custom_var = tk.StringVar()
        self.custom_entry = ttk.Entry(row3, textvariable=self.custom_var); self.custom_entry.pack(side="left", fill="x", expand=True, padx=(6,0))
        self.btn_rerun = ttk.Button(row3, text="Custom + Rerun", command=self.on_custom)
        self.btn_rerun.pack(side="left", padx=(6,0))

        # Suggestions list
        self.listbox = tk.Listbox(main, height=8); self.listbox.pack(fill="both", expand=True, pady=(6,6))

        # State
        self.bio_text = ""
        self.chat_text = ""
        self.suggestions = []

    def save_target_settings(self):
        self.cfg['target']['default'] = self.target_var.get()
        self.cfg['target']['paste_mode'] = self.paste_var.get()
        save_config(self.cfg)

    def on_detect(self):
        monitors, active = detect_and_update_config()
        msg = "Detected monitors:\n" + "\n".join([f"- {m['width']}x{m['height']} @ {int((m['dpiX']/96)*100)}%" for m in monitors])
        if active:
            msg += f"\nPhone Link is on a {active['width']}x{active['height']} monitor @ {int((active['dpiX']/96)*100)}%"
        messagebox.showinfo("Wingman", msg)

    def on_profile(self):
        self.save_target_settings()
        bio, img = read_profile(self.cfg)
        if not (bio and bio.strip()):
            messagebox.showwarning("Wingman", "Couldn't read profile (try ensuring it's visible).")
            return
        self.bio_text = bio.strip()
        messagebox.showinfo("Wingman", "Profile captured.")

    def on_chat(self):
        self.save_target_settings()
        txt = read_chat(self.cfg)
        if not (txt and txt.strip()):
            messagebox.showwarning("Wingman", "Couldn't read chat (make sure the thread is visible).")
            return
        self.chat_text = txt.strip()
        messagebox.showinfo("Wingman", "Chat captured.")

    def on_generate(self):
        self.save_target_settings()
        if not (self.chat_text or self.bio_text):
            messagebox.showwarning("Wingman", "Read profile and chat first.")
            return
        self.suggestions = generate(self.cfg, self.chat_text, self.bio_text)
        self.refresh_list()

    def on_custom(self):
        self.save_target_settings()
        if not (self.chat_text or self.bio_text):
            messagebox.showwarning("Wingman", "Read profile and chat first.")
            return
        custom = self.custom_var.get().strip()
        self.suggestions = generate(self.cfg, self.chat_text, self.bio_text, custom_request=custom)
        self.refresh_list()

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for s in self.suggestions:
            self.listbox.insert(tk.END, s)

    def on_paste(self):
        self.save_target_settings()
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("Wingman", "Select a suggestion first.")
            return
        text = self.listbox.get(sel[0])
        ok, err = paste_selected(self.cfg, text, paste_mode=self.paste_var.get())
        if not ok:
            messagebox.showerror("Wingman", f"Paste failed: {err}")
        else:
            messagebox.showinfo("Wingman", "Pasted. You can press Enter to send.")

def run():
    root = tk.Tk()
    WingmanUI(root)
    root.mainloop()
