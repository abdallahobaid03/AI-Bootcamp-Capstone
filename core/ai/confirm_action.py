import json
import re
from core.ai.main_llm import get_llm
from core.ai.prompt import Prompt



def _extract_json(text: str) -> str:
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return m.group(0) if m else ""

def classify_confirmation(preview: str, user_message: str) -> str:
    llm = get_llm()
    prompt = (Prompt.CLASSIFICATION_PROMPT
          .replace("{preview}", preview)
          .replace("{user_message}", user_message))
    out = llm.invoke(prompt).content
    raw = _extract_json(out)

    try:
        data = json.loads(raw)
        decision = (data.get("decision") or "").strip().lower()
        if decision in {"approve", "deny", "unclear"}:
            return decision
    except Exception:
        pass

    return "unclear"
