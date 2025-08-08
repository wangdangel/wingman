# app/orchestrator.py
import os
import time
import logging

from . import uia_scraper
from .util import load_config
from .ocr_fallback import ocr_window_region
from .display_detect import find_phone_link_hwnd
from .model_client import propose_replies
from .memory import DB
from .profile_store import ensure_person_folder, save_profile, save_chat_history
from .paste import paste_text

log = logging.getLogger("wingman")

# Simple global throttle for paste operations (seconds)
_last_paste_ts = 0.0


def ensure_db(cfg) -> DB:
    """Open (and initialize) the SQLite DB."""
    return DB(cfg["storage"]["sqlite_path"])


def read_profile(cfg):
    """
    Read the profile text from Phone Link.
    1) Try UI Automation (thread-safe inside uia_scraper).
    2) If empty/short, fall back to OCR over the configured profile crop.
    Returns: (bio_text:str|None, screenshot_img:PIL.Image|None)
    """
    bio = None
    screenshot = None

    # Try UIA, but never crash if COM/UIA is cranky
    try:
        bio = uia_scraper.read_profile_text()
    except Exception as e:
        log.warning("UIA read_profile_text failed, will try OCR: %s", e)

    # OCR fallback
    hwnd = find_phone_link_hwnd()
    if (not bio or len(bio) < 10) and cfg["scraping"].get("ocr_fallback", True) and hwnd:
        crop = cfg["targets"]["phone_link"]["profile_crop"]
        try:
            text, pil = ocr_window_region(
                hwnd, crop, lang=cfg["scraping"].get("ocr_lang", "eng")
            )
            bio = bio or text
            screenshot = pil
        except Exception as e:
            log.error("OCR read_profile failed: %s", e)

    return bio, screenshot


def read_chat(cfg):
    """
    Read the chat thread text from Phone Link.
    1) Try UIA.
    2) If empty/short, fall back to OCR over the configured chat crop.
    Returns: chat_text:str|None
    """
    txt = None

    try:
        txt = uia_scraper.read_chat_text()
    except Exception as e:
        log.warning("UIA read_chat_text failed, will try OCR: %s", e)

    hwnd = find_phone_link_hwnd()
    if (not txt or len(txt) < 10) and cfg["scraping"].get("ocr_fallback", True) and hwnd:
        crop = cfg["targets"]["phone_link"]["chat_crop"]
        try:
            text, _ = ocr_window_region(
                hwnd, crop, lang=cfg["scraping"].get("ocr_lang", "eng")
            )
            txt = txt or text
        except Exception as e:
            log.error("OCR read_chat failed: %s", e)

    return txt


def generate(
    cfg,
    history: str,
    bio: str,
    tone: str = "playful",
    ask_question_default: str | None = None,
    max_chars: int | None = None,
    custom_request: str = "",
):
    """
    Ask the local Ollama model to propose 3–5 replies.
    Raises on hard failures so the UI can show an error dialog.
    """
    ask = ask_question_default or cfg["ui"].get("ask_question_default", "often")
    mx = max_chars or cfg["ui"].get("max_reply_chars", 300)
    return propose_replies(
        history=history or "",
        bio=bio or "",
        tone=tone,
        ask_question_default=ask,
        max_chars=mx,
        custom_request=custom_request or "",
    )


def persist_everything(cfg, name_guess, bio, bio_png, chat_text, suggestions):
    """
    Create/update a person folder, store profile/chat artifacts, and record in SQLite.
    Returns: (match_id:int, folder:str)
    """
    db = ensure_db(cfg)
    people_dir = cfg["storage"]["people_dir"]
    folder = ensure_person_folder(people_dir, name_guess or "unknown")
    match_id = db.upsert_match(
        name=name_guess or "unknown", source="phone_link", folder=folder
    )

    png_path = None
    try:
        if bio_png is not None:
            png_path = save_profile(folder, bio_text=bio, traits=None, screenshot_img=bio_png)
        else:
            save_profile(folder, bio_text=bio, traits=None, screenshot_img=None)
    except Exception as e:
        log.warning("Failed saving profile artifacts: %s", e)

    try:
        if chat_text:
            save_chat_history(folder, chat_text)
    except Exception as e:
        log.warning("Failed saving chat history: %s", e)

    # DB inserts
    try:
        db.save_profile(match_id, bio or "", traits_json=None, screenshot_path=png_path)
    except Exception as e:
        log.warning("DB save_profile failed: %s", e)

    try:
        db.save_chat(match_id, chat_text or "", summary=None)
    except Exception as e:
        log.warning("DB save_chat failed: %s", e)

    try:
        db.save_suggestions(
            match_id,
            prompt="",
            suggestions=[{"text": s} for s in (suggestions or [])],
        )
    except Exception as e:
        log.warning("DB save_suggestions failed: %s", e)

    return match_id, folder


def paste_selected(cfg, text: str, paste_mode: str | None = None):
    """
    Paste a selected suggestion via AutoHotkey.
    Honors a simple global throttle (behavior.throttle_seconds_per_chat).
    Returns: (ok:bool, err:str|None)
    """
    global _last_paste_ts
    throttle = int(cfg.get("behavior", {}).get("throttle_seconds_per_chat", 0)) or 0
    now = time.time()
    if throttle > 0 and (now - _last_paste_ts) < throttle:
        remain = int(throttle - (now - _last_paste_ts))
        return False, f"Throttled. Try again in {max(remain, 1)}s."

    ok, err = paste_text(text, mode=paste_mode, window_title="Phone Link")
    if ok:
        _last_paste_ts = time.time()
    return ok, err
