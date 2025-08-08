# Placeholder for future OpenAI tool definitions.
# For now we keep simple generation via model_client.propose_replies
TOOLS = [
    {
      "type":"function",
      "function":{
        "name":"summarize_chat",
        "description":"Summarize chat history and extract key hooks.",
        "parameters":{"type":"object","properties":{"history":{"type":"string"}},"required":["history"]}
      }
    },
    {
      "type":"function",
      "function":{
        "name":"propose_replies",
        "description":"Generate 3-5 short, respectful, playful replies.",
        "parameters":{"type":"object","properties":{
          "history":{"type":"string"},
          "bio":{"type":"string"},
          "tone":{"type":"string"},
          "ask_question_default":{"type":"string"},
          "max_chars":{"type":"integer"},
          "custom_request":{"type":"string"}
        },"required":["history"]}
      }
    }
]
