# app/ui.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading

from .util import load_config, save_config
from .display_detect import (
    detect_and_update_config,
    enumerate_windows,
    set_selected_hwnd,
    get_selected_hwnd,
)
from .orchestrator import read_profile, read_chat, generate, paste_selected
from .logging_setup import setup_logging
from .debug_tools import save_ocr_previews
from .model_client import warm_model
from .crop_tuner import CropTuner
from .focus_calibrate import FocusCalibrator
from .ai_orchestrate import ai_type_message  # AI control (focus + type)

logger = setup_logging("./logs", "INFO")


class WingmanUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Wingman")
        self.cfg = load_config()
        if self.cfg["ui"].get("topmost", True):
            self.root.wm_attributes("-topmost", 1)

        main = ttk.Frame(root, padding=8)
        main.pack(fill="both", expand=True)

        # -------- Row 1: target/paste + utilities --------
        row1 = ttk.Frame(main)
        row1.pack(fill="x", pady=(0, 6))

        ttk.Label(row1, text="Target:").pack(side="left")
        self.target_var = tk.StringVar(value=self.cfg["target"]["default"])
        targets = ["phone_link", "browser_edge", "browser_chrome", "auto"]
        self.target_combo = ttk.Combobox(
            row1, state="readonly", values=targets, textvariable=self.target_var, width=18
        )
        self.target_combo.pack(side="left", padx=(6, 12))
        self.target_combo.bind("<<ComboboxSelected>>", lambda e: self.save_target_settings())

        ttk.Label(row1, text="Paste:").pack(side="left")
        self.paste_var = tk.StringVar(value=self.cfg["target"]["paste_mode"])
        paste_opts = ["focus_phone_link", "paste_at_cursor"]
        self.paste_combo = ttk.Combobox(
            row1, state="readonly", values=paste_opts, textvariable=self.paste_var, width=18
        )
        self.paste_combo.pack(side="left", padx=(6, 12))
        self.paste_combo.bind("<<ComboboxSelected>>", lambda e: self.save_target_settings())

        self.btn_detect = ttk.Button(row1, text="Detect Displays / DPI", command=self.on_detect)
        self.btn_detect.pack(side="right")

        self.btn_choose = ttk.Button(row1, text="Choose Window…", command=self.on_choose_window)
        self.btn_choose.pack(side="right", padx=(6, 0))

        self.btn_warm = ttk.Button(row1, text="Warm Model", command=self.on_warm)
        self.btn_warm.pack(side="right", padx=(6, 0))

        # -------- Row 2: actions --------
        row2 = ttk.Frame(main)
        row2.pack(fill="x", pady=(0, 6))

        self.btn_profile = ttk.Button(row2, text="Read Profile", command=self.on_profile)
        self.btn_profile.pack(side="left", padx=(0, 6))

        self.btn_chat = ttk.Button(row2, text="Read Chat", command=self.on_chat)
        self.btn_chat.pack(side="left", padx=(0, 6))

        self.btn_generate = ttk.Button(row2, text="Generate 3–5", command=self.on_generate)
        self.btn_generate.pack(side="left", padx=(0, 6))

        self.btn_preview = ttk.Button(row2, text="Save OCR Previews", command=self.on_preview)
        self.btn_preview.pack(side="left", padx=(0, 6))

        self.btn_setfocus = ttk.Button(row2, text="Set Focus Point", command=self.on_set_focus)
        self.btn_setfocus.pack(side="left", padx=(0, 6))

        self.btn_tuner = ttk.Button(row2, text="Crop Tuner", command=self.on_tuner)
        self.btn_tuner.pack(side="left", padx=(0, 6))

        # Right side: AI Type and manual Paste
        self.btn_ai_type = ttk.Button(row2, text="AI Type", command=self.on_ai_type)
        self.btn_ai_type.pack(side="right", padx=(6, 0))

        self.btn_paste = ttk.Button(row2, text="Paste", command=self.on_paste)
        self.btn_paste.pack(side="right")

        # -------- Row 3: custom prompt --------
        row3 = ttk.Frame(main)
        row3.pack(fill="x", pady=(0, 6))
        ttk.Label(row3, text="Custom request:").pack(side="left")
        self.custom_var = tk.StringVar()
        self.custom_entry = ttk.Entry(row3, textvariable=self.custom_var)
        self.custom_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.btn_rerun = ttk.Button(row3, text="Custom + Rerun", command=self.on_custom)
        self.btn_rerun.pack(side="left", padx=(6, 0))

        # -------- Suggestions list --------
        self.listbox = tk.Listbox(main, height=8)
        self.listbox.pack(fill="both", expand=True, pady=(6, 6))
        self.listbox.bind("<Double-Button-1>", lambda e: self.on_paste())

        # -------- Status bar --------
        self.status_var = tk.StringVar(value="Ready.")
        status = ttk.Frame(main)
        status.pack(fill="x")
        ttk.Label(status, textvariable=self.status_var, anchor="w").pack(fill="x")

        # State
        self.bio_text = ""
        self.chat_text = ""
        self.suggestions = []

    # ---------- helpers ----------
    def set_status(self, text: str):
        self.status_var.set(text)
        self.root.update_idletasks()

    def disable_ui(self):
        for w in (
            self.btn_detect,
            self.btn_choose,
            self.btn_warm,
            self.btn_profile,
            self.btn_chat,
            self.btn_generate,
            self.btn_preview,
            self.btn_setfocus,
            self.btn_tuner,
            self.btn_ai_type,
            self.btn_paste,
            self.btn_rerun,
            self.target_combo,
            self.paste_combo,
            self.custom_entry,
        ):
            try:
                w.configure(state="disabled")
            except Exception:
                pass

    def enable_ui(self):
        for w in (
            self.btn_detect,
            self.btn_choose,
            self.btn_warm,
            self.btn_profile,
            self.btn_chat,
            self.btn_generate,
            self.btn_preview,
            self.btn_setfocus,
            self.btn_tuner,
            self.btn_ai_type,
            self.btn_paste,
            self.btn_rerun,
            self.target_combo,
            self.paste_combo,
            self.custom_entry,
        ):
            try:
                w.configure(state="normal")
            except Exception:
                pass

    def save_target_settings(self):
        self.cfg["target"]["default"] = self.target_var.get()
        self.cfg["target"]["paste_mode"] = self.paste_var.get()
        save_config(self.cfg)

    # ---------- window picker ----------
    def on_choose_window(self):
        picker = WindowPicker(self.root, self.cfg)
        self.root.wait_window(picker.top)  # modal-ish

    # ---------- button handlers ----------
    def on_detect(self):
        self.disable_ui()
        self.set_status("Detecting displays / DPI...")

        def work():
            monitors, active = detect_and_update_config()
            msg = "Detected monitors:\n" + "\n".join(
                [f"- {m['width']}x{m['height']} @ {int((m['dpiX']/96)*100)}%" for m in monitors]
            )
            if active:
                msg += f"\nTarget window appears on a {active['width']}x{active['height']} monitor @ {int((active['dpiX']/96)*100)}%"
            return msg

        def done(msg, err=None):
            self.enable_ui()
            self.set_status("Ready.")
            if err:
                messagebox.showwarning("Wingman", str(err))
            else:
                messagebox.showinfo("Wingman", msg)

        threading.Thread(target=self._run_and_finish, args=(work, done), daemon=True).start()

    def on_warm(self):
        self.save_target_settings()
        self.disable_ui()
        self.set_status("Warming model (first load can take ~60–90s)...")

        def work():
            return warm_model()

        def done(ok, err=None):
            self.enable_ui()
            if err:
                self.set_status("Warm-up error.")
                messagebox.showwarning("Wingman", f"Warm-up in progress or error.\n{err}")
            else:
                self.set_status("Model warm." if ok else "Warm-up ping sent.")
                messagebox.showinfo(
                    "Wingman",
                    "Model is warm and ready." if ok else "Warm-up ping sent. It may take a few more seconds.",
                )

        threading.Thread(target=self._run_and_finish, args=(work, done), daemon=True).start()

    def on_profile(self):
        self.save_target_settings()
        self.disable_ui()
        self.set_status("Reading profile...")

        def work():
            return read_profile(self.cfg)

        def done(result, err=None):
            self.enable_ui()
            self.set_status("Ready.")
            if err:
                messagebox.showwarning("Wingman", f"Profile read error:\n{err}")
                return
            bio, _ = result
            if not (bio and str(bio).strip()):
                messagebox.showwarning(
                    "Wingman", "Couldn't read profile (make sure the profile pane is visible)."
                )
                return
            self.bio_text = str(bio).strip()
            messagebox.showinfo("Wingman", "Profile captured.")

        threading.Thread(target=self._run_and_finish, args=(work, done), daemon=True).start()
    def on_chat(self):
        self.save_target_settings()
        self.disable_ui()
        self.set_status("Reading chat...")

        def work():
            return read_chat(self.cfg)

        def done(txt, err=None):
            self.enable_ui()
            self.set_status("Ready.")
            if err:
                messagebox.showwarning("Wingman", f"Chat read error:\n{err}")
                return
            if not (txt and str(txt).strip()):
                messagebox.showwarning(
                    "Wingman", "Couldn't read chat (make sure the thread is visible)."
                )
                return
            self.chat_text = str(txt).strip()
            messagebox.showinfo("Wingman", "Chat captured.")

        threading.Thread(target=self._run_and_finish, args=(work, done), daemon=True).start()

    def on_generate(self):
        self.save_target_settings()
        if not (self.chat_text or self.bio_text):
            messagebox.showwarning("Wingman", "Read profile and chat first.")
            return
        self.disable_ui()
        self.set_status("Generating suggestions...")

        def work():
            return generate(self.cfg, self.chat_text, self.bio_text)

        def done(suggestions, err=None):
            self.enable_ui()
            if err:
                self.set_status("Error.")
                messagebox.showerror("Wingman", f"Generation failed:\n{err}")
                return
            self.suggestions = suggestions or []
            self.refresh_list()
            self.set_status(f"Ready. {len(self.suggestions)} suggestion(s).")
            if not self.suggestions:
                messagebox.showwarning("Wingman", "No suggestions returned. Try Custom + Rerun.")

        threading.Thread(target=self._run_and_finish, args=(work, done), daemon=True).start()

    def on_custom(self):
        self.save_target_settings()
        if not (self.chat_text or self.bio_text):
            messagebox.showwarning("Wingman", "Read profile and chat first.")
            return
        custom = (self.custom_var.get() or "").strip()
        self.disable_ui()
        self.set_status("Generating with custom request...")

        def work():
            return generate(self.cfg, self.chat_text, self.bio_text, custom_request=custom)

        def done(suggestions, err=None):
            self.enable_ui()
            if err:
                self.set_status("Error.")
                messagebox.showerror("Wingman", f"Generation failed:\n{err}")
                return
            self.suggestions = suggestions or []
            self.refresh_list()
            self.set_status(f"Ready. {len(self.suggestions)} suggestion(s).")

        threading.Thread(target=self._run_and_finish, args=(work, done), daemon=True).start()

    def on_preview(self):
        self.save_target_settings()
        self.disable_ui()
        self.set_status("Saving OCR previews...")

        def work():
            return save_ocr_previews()

        def done(result, err=None):
            self.enable_ui()
            self.set_status("Ready.")
            if err:
                messagebox.showwarning("Wingman", err)
                return
            c, p, _ = result
            msg = "Saved previews to ./logs\n"
            if c:
                msg += f"- Chat: {c}\n"
            if p:
                msg += f"- Profile: {p}\n"
            messagebox.showinfo("Wingman", msg + "Open them and tweak config.yaml crop if needed.")

        threading.Thread(target=self._run_and_finish, args=(work, done), daemon=True).start()

    def on_tuner(self):
        CropTuner(self.root)

    def on_set_focus(self):
        FocusCalibrator(self.root)

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
            self.set_status("Inserted text. Press Enter to send.")
            messagebox.showinfo("Wingman", "Inserted text. You can press Enter to send.")

    def on_ai_type(self):
        self.save_target_settings()
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("Wingman", "Select a suggestion first.")
            return
        text = self.listbox.get(sel[0])

        send_after = messagebox.askyesno("Wingman", "Press Enter to send after typing?")

        self.disable_ui()
        self.set_status("AI is focusing and typing...")

        def work():
            # ai_type_message returns (ok, err)
            return ai_type_message(text, send_after=send_after)

        def done(result, err=None):
            self.enable_ui()
            self.set_status("Ready.")
            if err:
                messagebox.showerror("Wingman", f"AI control error:\n{err}")
                return
            ok, e2 = result
            if not ok:
                messagebox.showerror("Wingman", f"AI control failed:\n{e2 or 'Unknown error'}")
            else:
                messagebox.showinfo(
                    "Wingman",
                    "Inserted via AI (sent)." if send_after else "Inserted via AI.",
                )

        threading.Thread(target=self._run_and_finish, args=(work, done), daemon=True).start()

    # ---------- tiny async runner ----------
    def _run_and_finish(self, work_fn, done_fn):
        result, err = None, None
        try:
            result = work_fn()
        except Exception as e:
            err = e
            logger.exception("Background task error")
        finally:
            self.root.after(0, lambda: done_fn(result, err))


class WindowPicker:
    def __init__(self, parent, cfg):
        self.cfg = cfg
        self.top = tk.Toplevel(parent)
        self.top.title("Choose Window")
        self.top.geometry("860x420")
        self.top.transient(parent)
        self.top.grab_set()

        bar = ttk.Frame(self.top)
        bar.pack(fill="x", padx=8, pady=6)

        self.show_all = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            bar, text="Show all processes", variable=self.show_all, command=self.refresh
        ).pack(side="left")

        ttk.Button(bar, text="Refresh", command=self.refresh).pack(side="left", padx=(6, 0))

        sel = get_selected_hwnd()
        self.sel_label = ttk.Label(bar, text=f"Saved HWND: {sel if sel else 'None'}")
        self.sel_label.pack(side="right")

        cols = ("proc", "title", "class", "hwnd", "rect")
        self.tree = ttk.Treeview(self.top, columns=cols, show="headings")
        for c, w in zip(cols, (150, 320, 160, 110, 100)):
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        btns = ttk.Frame(self.top)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btns, text="Use Selected", command=self.use_selected).pack(side="right")
        ttk.Button(btns, text="Clear Saved", command=self.clear_saved).pack(
            side="right", padx=(0, 6)
        )
        ttk.Button(btns, text="Cancel", command=self.top.destroy).pack(side="right", padx=(0, 6))

        self.refresh()

    def _filter_proc_names(self):
        names = []
        pn = (
            self.cfg.get("targets", {})
            .get("phone_link", {})
            .get("process_names", ["PhoneExperienceHost.exe", "YourPhone.exe", "YourPhoneAppProxy.exe"])
        )
        names.extend(pn)
        be = self.cfg.get("targets", {}).get("browser_edge", {}).get("process_name", "msedge.exe")
        bc = self.cfg.get("targets", {}).get("browser_chrome", {}).get("process_name", "chrome.exe")
        names.extend([be, bc])
        # unique while preserving order
        seen, out = set(), []
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)
        return out

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        filter_names = None if self.show_all.get() else self._filter_proc_names()
        wins = enumerate_windows(filter_proc_names=filter_names)
        for w in wins:
            self.tree.insert(
                "",
                "end",
                values=(w["proc"], w["title"], w["class"], str(w["hwnd"]), str(w["rect"])),
            )

    def use_selected(self):
        item = self.tree.focus()
        if not item:
            messagebox.showwarning("Wingman", "Select a window first.")
            return
        vals = self.tree.item(item, "values")
        try:
            hwnd = int(vals[3])
        except Exception:
            messagebox.showwarning("Wingman", "Invalid selection.")
            return
        set_selected_hwnd(hwnd)
        self.sel_label.config(text=f"Saved HWND: {hwnd}")
        messagebox.showinfo("Wingman", f"Saved selection.\nHWND = {hwnd}")
        self.top.destroy()

    def clear_saved(self):
        set_selected_hwnd(None)
        self.sel_label.config(text="Saved HWND: None")
        messagebox.showinfo("Wingman", "Cleared saved window.")


def run():
    root = tk.Tk()
    WingmanUI(root)
    root.mainloop()
