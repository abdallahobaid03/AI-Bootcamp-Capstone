from functools import lru_cache
from langchain.agents import create_agent

from core.ai.main_llm import get_llm
from core.ai.prompt import Prompt
from core.ai.consumption_tools import (
    get_consumption_history,
    compare_last_two_months,
    average_last_n_months,
)

@lru_cache(maxsize=1)
def _get_agent():
    llm = get_llm()
    tools = [get_consumption_history, compare_last_two_months, average_last_n_months]
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=Prompt.CONSUMPTION_AGENT_SYSTEM
    )

def answer_consumption_agentic(user_key: str, message: str) -> str:
    agent = _get_agent()
    result = agent.invoke({
        "messages": [
            {"role": "user", "content": f"User key: {user_key}\nQuestion: {message}"}
        ]
    })
    return (result["messages"][-1].content or "").strip()
