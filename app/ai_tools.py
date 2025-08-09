# app/ai_tools.py
import json, requests, os
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
    cfg = load_config()
    base = cfg["model"].get("base_url","http://localhost:11434").rstrip("/")
    model = model_override or cfg["model"]["model_name"]
    timeout = int(cfg["model"].get("request_timeout_seconds", 120))

    messages: List[Dict[str,Any]] = [
        {"role":"system","content": system_prompt},
        {"role":"user","content": user_prompt}
    ]

    while True:
        payload = {
          "model": model,
          "messages": messages,
          "tools": TOOLS,
          "tool_choice": "auto",
          "temperature": cfg["model"].get("temperature", 0.6),
          "max_tokens": cfg["model"].get("max_tokens", 512)
        }
        # Try OpenAI-compatible first
        try:
            r = requests.post(f"{base}/v1/chat/completions", json=payload, timeout=timeout)
            if r.status_code == 404:
                raise RuntimeError("openai path not available")
            r.raise_for_status()
            data = r.json()
            choice = data["choices"][0]
            msg = choice["message"]
        except Exception:
            # Fallback: Ollama native
            r = requests.post(f"{base}/api/chat", json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": cfg["model"].get("temperature", 0.6)}
            }, timeout=timeout)
            r.raise_for_status()
            out = r.json()
            # No native tool-calls here; just return the text
            return True, out.get("message", {}).get("content", "")

        tool_calls = msg.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                fn = tc["function"]["name"]
                args = json.loads(tc["function"].get("arguments") or "{}")
                result = _call_tool(fn, args)
                messages.append({"role":"tool", "tool_call_id": tc["id"], "name": fn, "content": json.dumps(result)})
            continue  # loop lets model react to tool results

        # No tool call -> return the assistant’s text
        return True, msg.get("content") or ""
