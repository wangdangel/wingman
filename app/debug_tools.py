import os
from .display_detect import find_phone_link_hwnd
from .ocr_fallback import ocr_window_region
from .util import load_config

def save_ocr_previews():
    cfg = load_config()
    hwnd = find_phone_link_hwnd()
    if not hwnd:
        return None, None, "Phone Link window not found"

    chat_crop = cfg['targets']['phone_link']['chat_crop']
    profile_crop = cfg['targets']['phone_link']['profile_crop']
    lang = cfg['scraping'].get('ocr_lang', 'eng')

    chat_text, chat_img = ocr_window_region(hwnd, chat_crop, lang=lang)
    prof_text, prof_img = ocr_window_region(hwnd, profile_crop, lang=lang)

    os.makedirs("./logs", exist_ok=True)
    chat_path = "./logs/ocr_chat_preview.png"
    prof_path = "./logs/ocr_profile_preview.png"
    if chat_img: chat_img.save(chat_path)
    if prof_img: prof_img.save(prof_path)

    return chat_path if chat_img else None, prof_path if prof_img else None, None
