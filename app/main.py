from .ui import run
from .logging_setup import setup_logging
from .util import load_config
import os

def main():
    # Ensure data/logs dirs exist
    cfg = load_config()
    for d in (cfg['storage']['base_dir'], cfg['logging']['dir']):
        os.makedirs(d, exist_ok=True)
    run()

if __name__ == "__main__":
    main()
