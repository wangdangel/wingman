import json, requests
from typing import List, Dict, Any, Tuple, Optional
from .util import load_config
from .desktop_control import focus_window, type_text, press_enter

TOOLS = [
    {
      "type":"function",
      "function":{
        "name":"focus_window",
        "description":"Focus the messaging window before typing",
        "parameters":{
          "type":"object",
          "properties":{"title_regex":{"type":"string"}},
          "required":[]
        }
      }
    },
    {
      "type":"function",
      "function":{
        "name":"type_text",
        "description":"Type text at the current caret",
        "parameters":{
          "type":"object",
          "properties":{
            "text":{"type":"string"},
            "per_char_delay":{"type":"number","description":"seconds delay per char, e.g. 0.002"}
          },
          "required":["text"]
        }
      }
    },
    {
      "type":"function",
      "function":{
        "name":"press_enter",
        "description":"Press Enter n times",
        "parameters":{
          "type":"object",
          "properties":{"times":{"type":"integer","minimum":1}},
          "required":[]
        }
      }
    }
]

def _call_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "focus_window":
        return focus_window(**args)
    if name == "type_text":
        return type_text(**args)
    if name == "press_enter":
        return press_enter(**args)
    return {"ok": False, "error": f"Unknown tool {name}"}

def run_chat_with_tools(system_prompt: str, user_prompt: str, model_override: Optional[str]=None) -> Tuple[bool, str]:
    """
    Returns (did_tools_run, assistant_text).
    did_tools_run==True means at least one tool was invoked successfully.
    """
    cfg = load_config()
    base = cfg["model"].get("base_url","http://localhost:11434").rstrip("/")
    model = model_override or cfg["model"]["model_name"]
    timeout = int(cfg["model"].get("request_timeout_seconds", 120))

    messages: List[Dict[str,Any]] = [
        {"role":"system","content": system_prompt},
        {"role":"user","content": user_prompt}
    ]
    did_tools = False

    while True:
        payload = {
          "model": model,
          "messages": messages,
          "tools": TOOLS,
          "tool_choice": "auto",
          "temperature": cfg["model"].get("temperature", 0.2),
          "max_tokens": cfg["model"].get("max_tokens", 256)
        }
        # Try OpenAI-compatible
        try:
            r = requests.post(f"{base}/v1/chat/completions", json=payload, timeout=timeout)
            if r.status_code == 404:
                raise RuntimeError("openai path not available")
            r.raise_for_status()
            data = r.json()
            choice = data["choices"][0]
            msg = choice["message"]
        except Exception:
            # No tools path. Fall back to plain chat; no desktop actions performed.
            try:
                r2 = requests.post(f"{base}/api/chat", json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": cfg["model"].get("temperature", 0.2)}
                }, timeout=timeout)
                r2.raise_for_status()
                out = r2.json()
                return False, out.get("message", {}).get("content", "") or out.get("response", "") or ""
            except Exception:
                return False, ""

        tool_calls = msg.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                fn = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"].get("arguments") or "{}")
                except Exception:
                    args = {}
                result = _call_tool(fn, args)
                did_tools = True or did_tools
                messages.append({
                    "role":"tool",
                    "tool_call_id": tc.get("id") or "",
                    "name": fn,
                    "content": json.dumps(result)
                })
            # Loop again so model can react to results
            continue

        # No further tool calls; return.
        return did_tools, (msg.get("content") or "")