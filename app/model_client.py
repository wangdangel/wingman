import requests, json, time
from .util import load_config

SYSTEM_PROMPT = (
    "You are Wingman, a helpful assistant for dating chats. "
    "Given a bio and recent chat text, propose 3–5 concise replies "
    "(<= 25 words, 1–2 sentences, playful, respectful). "
    "Prefer ending with a light question when natural. "
    "Do not send messages automatically."
)

def _ollama_base():
    cfg = load_config()
    base = cfg["model"]["base_url"].rstrip("/")
    # if someone left /v1 in config, strip it
    if base.endswith("/v1"):
        base = base[:-3]
    return base

def _timeout():
    cfg = load_config()
    return int(cfg["model"].get("request_timeout_seconds", 120))

def _keep_alive():
    cfg = load_config()
    return cfg["model"].get("keep_alive", "30m")

def _ollama_chat(messages):
    """Call Ollama /api/chat with retries to handle cold starts."""
    cfg = load_config()
    url = f"{_ollama_base()}/api/chat"
    payload = {
        "model": cfg["model"]["model_name"],
        "messages": messages,
        "stream": False,
        "keep_alive": _keep_alive(),
        "options": {"temperature": cfg["model"].get("temperature", 0.6)},
    }

    # Retry/backoff: cold start or model not loaded yet can 404/503/connection-refused.
    attempts = 6
    backoff = [0, 3, 6, 10, 15, 20]
    last_err = None
    for i in range(attempts):
        try:
            r = requests.post(url, json=payload, timeout=_timeout())
            # Some Ollama versions 404 when not ready; treat as retryable
            if r.status_code in (404, 409, 422, 500, 503):
                last_err = RuntimeError(f"ollama status {r.status_code}: {r.text[:200]}")
            else:
                r.raise_for_status()
                data = r.json()
                if "message" in data and isinstance(data["message"], dict):
                    content = data["message"].get("content", "")
                elif "messages" in data and data["messages"]:
                    content = data["messages"][-1].get("content", "")
                else:
                    content = ""
                return {"role": "assistant", "content": content}
        except requests.exceptions.RequestException as e:
            last_err = e
        # Back off and try again (model may still be loading)
        time.sleep(backoff[i])

    # If we got here, attempts failed
    raise RuntimeError(f"Ollama chat failed after retries: {last_err}")

def warm_model():
    """Light ping to force-load the model into memory and keep it alive."""
    messages = [
        {"role": "system", "content": "You are a helper. Reply with the single word: READY."},
        {"role": "user", "content": "Warm up."},
    ]
    resp = _ollama_chat(messages)
    return "READY" in (resp.get("content") or "").upper()

def propose_replies(history: str, bio: str = "", tone: str = "playful",
                    ask_question_default: str = "often", max_chars: int = 300, custom_request: str = ""):
    user_payload = {
        "bio": bio or "",
        "history": history or "",
        "tone": tone,
        "ask_question_default": ask_question_default,
        "max_chars": max_chars,
        "custom_request": custom_request or ""
    }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
    ]

    try:
        msg = _ollama_chat(messages)
    except Exception:
        # One more try: warm model, then retry once
        warm_model()
        msg = _ollama_chat(messages)

    content = (msg.get("content") or "").strip()
    # Try JSON array first; otherwise split lines
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return [str(x).strip() for x in data][:5]
    except Exception:
        pass
    lines = [l.strip("-• ").strip() for l in content.splitlines() if l.strip()]
    return lines[:5]
