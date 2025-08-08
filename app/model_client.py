import requests, json
from .util import load_config

def openai_chat(messages, tools=None):
    cfg = load_config()
    base = cfg['model']['base_url'].rstrip('/')
    model = cfg['model']['model_name']
    headers = {}
    if cfg['model'].get('bearer_token'):
        headers['Authorization'] = f"Bearer {cfg['model']['bearer_token']}"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": cfg['model'].get('temperature', 0.6),
        "max_tokens": cfg['model'].get('max_tokens', 512),
    }
    if cfg['model'].get('use_tools') and tools:
        payload['tools'] = tools
    r = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    msg = data['choices'][0]['message']
    return msg

SYSTEM_PROMPT = (
    "You are Wingman, a helpful assistant for dating chats. "
    "Given a bio and recent chat text, propose 3–5 concise replies "
    "(<= 25 words, 1–2 sentences, playful, respectful). "
    "Prefer ending with a light question when natural. "
    "Do not send messages automatically."
)

def propose_replies(history:str, bio:str="", tone:str="playful", ask_question_default="often", max_chars:int=300, custom_request:str=""):
    user_payload = {
        "bio": bio,
        "history": history,
        "tone": tone,
        "ask_question_default": ask_question_default,
        "max_chars": max_chars,
        "custom_request": custom_request
    }
    messages = [
        {"role":"system", "content": SYSTEM_PROMPT},
        {"role":"user", "content": json.dumps(user_payload, ensure_ascii=False)}
    ]
    msg = openai_chat(messages)
    content = (msg.get("content") or "").strip()
    # Try to parse as JSON list; if not, split lines
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return [str(x).strip() for x in data][:5]
    except Exception:
        pass
    lines = [l.strip("-• ").strip() for l in content.splitlines() if l.strip()]
    return lines[:5]
