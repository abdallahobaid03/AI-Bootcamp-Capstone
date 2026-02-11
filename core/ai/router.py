# core/ai/router.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

Intent = Literal["MENU", "GENERAL_QA", "CONSUMPTION", "EDIT_DATA", "COMPLAINT", "UNKNOWN"]

class RouteResult(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0, le=1)
    mapped_option: Literal["0", "1", "2", "3", "4"] = "0"
    reason: str = ""

def route_message(user_text: str) -> RouteResult:
    t = (user_text or "").strip().lower()

    if not t:
        return RouteResult(intent="MENU", confidence=0.6, mapped_option="0", reason="empty")

    # greetings -> menu
    if any(x in t for x in ["hi", "hello", "مرحبا", "اهلا", "أهلا", "السلام"]):
        return RouteResult(intent="MENU", confidence=0.8, mapped_option="0", reason="greeting")

    # menu/start
    if any(x in t for x in ["menu", "start", "قائمة", "القائمة", "خيارات"]):
        return RouteResult(intent="MENU", confidence=0.9, mapped_option="0", reason="menu request")

    # complaint
    if any(x in t for x in ["شكوى", "بلاغ", "complaint"]):
        return RouteResult(intent="COMPLAINT", confidence=0.9, mapped_option="4", reason="complaint keywords")

    # edit data
    if any(x in t for x in ["تعديل", "تحديث", "رقم", "عنوان", "phone", "address", "update"]):
        return RouteResult(intent="EDIT_DATA", confidence=0.85, mapped_option="3", reason="edit keywords")

    # consumption
    if any(x in t for x in ["استهلاك", "kwh", "consumption", "كيلو", "قراءة"]):
        return RouteResult(intent="CONSUMPTION", confidence=0.9, mapped_option="2", reason="consumption keywords")

    # default: treat as general question
    return RouteResult(intent="GENERAL_QA", confidence=0.7, mapped_option="1", reason="default to general")
