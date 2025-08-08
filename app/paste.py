\
import os, subprocess, shlex
from .util import load_config

def paste_text(text: str, mode: str = None, window_title: str = "Phone Link"):
    cfg = load_config()
    ahk_exe = cfg.get("ahk",{}).get("exe_path") or r"C:\Program Files\AutoHotkey\AutoHotkey.exe"
    script = os.path.join(os.path.dirname(__file__), "paste_ahk.ahk")
    # write reply.txt next to the script
    with open(os.path.join(os.path.dirname(__file__), "reply.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    if not mode:
        mode = cfg.get("target",{}).get("paste_mode","focus_phone_link")
    mode_arg = "focus" if mode == "focus_phone_link" else "nofocus"
    args = [ahk_exe, script, mode_arg, window_title]
    try:
        subprocess.Popen(args, shell=False)
        return True, None
    except Exception as e:
        return False, str(e)
