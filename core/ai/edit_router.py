import json
from core.ai.main_llm import get_llm
from core.ai.prompt import Prompt

def extract_edit_request(message: str) -> dict:
    llm = get_llm()
    prompt = Prompt.EDIT_EXTRACT_PROMPT.replace("{message}", message)
    out = llm.invoke(prompt).content.strip()

    try:
        return json.loads(out)
    except Exception:
        return {"field": "unknown", "value": ""}
