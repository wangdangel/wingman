import os, logging
from .util import load_config
from . import uia_scraper
from .ocr_fallback import ocr_window_region
from .display_detect import find_phone_link_hwnd
from .model_client import propose_replies
from .memory import DB
from .profile_store import ensure_person_folder, save_profile, save_chat_history
from .paste import paste_text

log = logging.getLogger("wingman")

def read_profile(cfg):
    # Try UIA first
    bio = uia_scraper.read_profile_text()
    screenshot = None
    hwnd = find_phone_link_hwnd()
    if (not bio or len(bio) < 10) and cfg['scraping'].get('ocr_fallback', True) and hwnd:
        crop = cfg['targets']['phone_link']['profile_crop']
        text, pil = ocr_window_region(hwnd, crop, lang=cfg['scraping'].get('ocr_lang','eng'))
        bio = bio or text
        screenshot = pil
    return bio, screenshot

def read_chat(cfg):
    txt = uia_scraper.read_chat_text()
    hwnd = find_phone_link_hwnd()
    if (not txt or len(txt) < 10) and cfg['scraping'].get('ocr_fallback', True) and hwnd:
        crop = cfg['targets']['phone_link']['chat_crop']
        text, _ = ocr_window_region(hwnd, crop, lang=cfg['scraping'].get('ocr_lang','eng'))
        txt = txt or text
    return txt

def ensure_db(cfg):
    return DB(cfg['storage']['sqlite_path'])

def generate(cfg, history, bio, tone="playful", ask_question_default=None, max_chars=None, custom_request=""):
    ask = ask_question_default or cfg['ui'].get('ask_question_default','often')
    mx = max_chars or cfg['ui'].get('max_reply_chars', 300)
    return propose_replies(history=history or "", bio=bio or "", tone=tone, ask_question_default=ask, max_chars=mx, custom_request=custom_request)

def persist_everything(cfg, name_guess, bio, bio_png, chat_text, suggestions):
    db = ensure_db(cfg)
    people_dir = cfg['storage']['people_dir']
    folder = ensure_person_folder(people_dir, name_guess or "unknown")
    match_id = db.upsert_match(name=name_guess or "unknown", source="phone_link", folder=folder)
    png_path = None
    if bio_png is not None:
        png_path = save_profile(folder, bio_text=bio, traits=None, screenshot_img=bio_png)
    else:
        save_profile(folder, bio_text=bio, traits=None, screenshot_img=None)
    if chat_text:
        save_chat_history(folder, chat_text)
    db.save_profile(match_id, bio or "", traits_json=None, screenshot_path=png_path)
    db.save_chat(match_id, chat_text or "", summary=None)
    db.save_suggestions(match_id, prompt="", suggestions=[{"text": s} for s in suggestions])
    return match_id, folder

def paste_selected(cfg, text, paste_mode=None):
    ok, err = paste_text(text, mode=paste_mode, window_title="Phone Link")
    if not ok:
        log.error("Paste failed: %s", err)
    return ok, err
