# app/main.py
import os
import tkinter as tk
from .ui import WingmanUI
from .logging_setup import setup_logging
from .util import load_config

def main():
    cfg = load_config()
    for d in (cfg['storage']['base_dir'], cfg['logging']['dir']):
        os.makedirs(d, exist_ok=True)
    setup_logging(cfg['logging']['dir'], cfg['logging'].get('level', 'INFO'))
    root = tk.Tk()
    WingmanUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
