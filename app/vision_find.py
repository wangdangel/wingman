# app/vision_find.py
import io, re, base64, json, ctypes, requests
from typing import Optional, Tuple
from PIL import Image
import win32gui
from .util import load_config
from .ocr_fallback import screenshot_region  # uses DX first, MSS fallback

# Make coords DPI-consistent (same as other modules)
def _set_dpi_awareness():
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        PMV2 = ctypes.c_void_p(-4)
        user32.SetProcessDpiAwarenessContext(PMV2)
        return
    except Exception:
        pass
    try:
        shcore = ctypes.WinDLL("Shcore")
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
_set_dpi_awareness()

DEFAULT_PROMPT = (
    "You are looking at a desktop app screenshot. "
    "Find the text input field where a user would type a chat message. "
    "Return ONLY a JSON object with integer pixel coordinates relative to THIS image, "
    'like: {"x": 123, "y": 456}. If unsure, pick the best guess near the bottom message box.'
)

def _pil_to_b64_jpeg(img: Image.Image, quality=85) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def _call_vlm_ollama(img_b64: str, prompt: str, model: str, base_url: str, timeout: int) -> Optional[Tuple[int,int]]:
    """
    Try OpenAI-style /v1/chat/completions first (supported by many Ollama builds),
    then fall back to /api/chat if needed.
    Expected response: JSON object in the text.
    """
    headers = {"Content-Type": "application/json"}
    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}" }},
    ]
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1,
        "max_tokens": 128,
    }
    try:
        r = requests.post(f"{base_url}/v1/chat/completions", json=payload, headers=headers, timeout=timeout)
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        return _extract_xy(text)
    except Exception:
        # Fallback to Ollama native /api/chat (multi-modal)
        try:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "images": [img_b64],
                "stream": False,
                "options": {"temperature": 0.1},
            }
            r = requests.post(f"{base_url}/api/chat", json=payload, headers=headers, timeout=timeout)
            r.raise_for_status()
            # /api/chat returns {"message":{"content": "..."}}
            data = r.json()
            text = data.get("message", {}).get("content") or data.get("response") or ""
            return _extract_xy(text)
        except Exception:
            return None

def _extract_xy(text: str) -> Optional[Tuple[int,int]]:
    # Try strict JSON first
    try:
        j = json.loads(text.strip())
        if isinstance(j, dict) and "x" in j and "y" in j:
            return int(j["x"]), int(j["y"])
    except Exception:
        pass
    # Fallback: regex { "x": N, "y": N }
    m = re.search(r'[{\[]\s*"?x"?\s*:\s*(\d+)\s*,\s*"?y"?\s*:\s*(\d+)\s*[}\]]', text, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None

def locate_message_input(hwnd: int, prompt: Optional[str] = None) -> Optional[Tuple[int,int]]:
    """
    Returns screen coordinates (x,y) to click inside the message input, or None.
    """
    cfg = load_config()
    vcfg = (cfg.get("vision", {}) or {})
    if not vcfg.get("enabled", False):
        return None

    base_url = vcfg.get("base_url", "http://localhost:11434").rstrip("/")
    model    = vcfg.get("model_name", "llava:latest")
    timeout  = int(vcfg.get("request_timeout_seconds", 45))
    prompt   = (prompt or vcfg.get("prompt") or DEFAULT_PROMPT).strip()

    # Full-window screenshot at native size (so VLM coords map 1:1)
    img = screenshot_region(hwnd, crop_pct=None)  # force_full_window in config will ensure whole window
    if img is None:
        return None

    b64 = _pil_to_b64_jpeg(img, quality=85)
    xy = _call_vlm_ollama(b64, prompt, model=model, base_url=base_url, timeout=timeout)
    if not xy:
        return None

    # Convert image-relative to screen coords: one-to-one because we passed native-size image
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    x_img, y_img = xy
    # guard rails
    w, h = img.size
    x_img = max(0, min(w-1, x_img))
    y_img = max(0, min(h-1, y_img))
    x_screen = left + x_img
    y_screen = top  + y_img
    return x_screen, y_screen
