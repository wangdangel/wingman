# app/ai_orchestrate.py
from __future__ import annotations
from typing import Tuple
import json

from .util import load_config
from .ai_tools import run_chat_with_tools  # uses OpenAI-style tool calls to our py tools
from .desktop_control import focus_window, type_text, press_enter

_DEFAULT_TITLE_RE = r"Tinder|Phone Link|Your Phone"

SYSTEM_PROMPT = """You are a desktop operator. You have tools:
- focus_window(title_regex?)
- type_text(text, per_char_delay?)
- press_enter(times?)

When asked to send a message:
1) Call focus_window first (use the provided title_regex if any).
2) Then call type_text with the exact text.
3) If asked to "send", call press_enter once after typing.
Do not chit-chat. Prefer tool calls over plain text.
"""

def ai_type_message(message_text: str, send_after: bool = False, title_regex: str | None = None) -> Tuple[bool, str | None]:
    """
    Ask the model to orchestrate focus + type (+ optional Enter) using tools.
    Fallbacks to direct local calls if tools aren't supported.
    Returns: (ok, err)
    """
    cfg = load_config()
    effective_title_regex = title_regex or cfg.get("tools", {}).get("title_regex") or _DEFAULT_TITLE_RE
    per_char = float(cfg.get("input", {}).get("type_per_char_delay_ms", 2)) / 1000.0

    # Build a clear user prompt the model can act on with tools:
    ask = {
        "action": "send_message",
        "title_regex": effective_title_regex,
        "text": message_text,
        "send_after": bool(send_after),
        "per_char_delay": per_char,
    }
    user_prompt = (
        "Use your tools to deliver this exactly:\n"
        + json.dumps(ask, ensure_ascii=False)
    )

    # Try tool-enabled chat first
    ok, out = run_chat_with_tools(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model_override=None,  # uses config model
    )
    if ok:
        return True, None

    # Fallback (no tools on this endpoint, or model refused): do it ourselves.
    try:
        r1 = focus_window(title_regex=effective_title_regex)
        if not r1.get("ok"):
            return False, f"focus_window failed: {r1.get('error')}"
        r2 = type_text(message_text, per_char_delay=per_char)
        if not r2.get("ok"):
            return False, f"type_text failed: {r2.get('error')}"
        if send_after:
            r3 = press_enter(1)
            if not r3.get("ok"):
                return False, f"press_enter failed: {r3.get('error')}"
        return True, None
    except Exception as e:
        return False, str(e)
