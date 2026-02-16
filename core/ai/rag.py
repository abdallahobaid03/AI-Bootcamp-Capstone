

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from django.conf import settings
from langchain_pinecone import PineconeVectorStore
from langchain_tavily import TavilySearch
from pinecone import Pinecone

from core.ai.main_llm import get_embeddings, get_llm
from core.ai.prompt import Prompt

logger = logging.getLogger(__name__)

PROMPT = Prompt.RAG_PROMPT


# ---------------------------
# Vector store (Pinecone)
# ---------------------------

@lru_cache(maxsize=1)
def _vs() -> PineconeVectorStore:
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index = pc.Index(settings.PINECONE_INDEX_NAME)


    return PineconeVectorStore(
        index=index,
        embedding=get_embeddings(),
        namespace=getattr(settings, "PINECONE_NAMESPACE", None),
    )


# ---------------------------
# Tavily (site-limited search)
# ---------------------------

def _site_include_scope() -> Optional[str]:
    """
    يحوّل FALLBACK_SITE_URL إلى scope مناسب لـ include_domains
    مثال: https://jreeef.memr.gov.jo/DEFAULT/AR -> jreeef.memr.gov.jo/DEFAULT/AR
    """
    raw = (getattr(settings, "FALLBACK_SITE_URL", "") or "").strip()
    if not raw:
        return None

    if "://" not in raw:
        raw = "https://" + raw

    p = urlparse(raw)
    if not p.netloc:
        return None

    path = (p.path or "").rstrip("/")
    return (p.netloc + path) if path and path != "/" else p.netloc


@lru_cache(maxsize=1)
def _tavily_tool() -> Optional[TavilySearch]:
    api_key = (getattr(settings, "TAVILY_API_KEY", "") or "").strip()
    if not api_key:
        return None

    os.environ["TAVILY_API_KEY"] = api_key

    return TavilySearch(
        max_results=int(getattr(settings, "FALLBACK_MAX_RESULTS", 4)),
        include_answer=False,
        include_raw_content="text",  
        search_depth="basic",
        limit=50,
        extract_depth="advanced",
    )


def _tavily_search_site(question: str) -> List[Dict[str, Any]]:
    tool = _tavily_tool()
    if tool is None:
        return []

    scope = _site_include_scope()
    if not scope:
        return []


    q = f"site:{scope} {question}"

    try:
        res = tool.invoke(
            {
                "query": q,
                "include_domains": [scope],
                "search_depth": "basic",
            }
        )
    except Exception:
        logger.exception("TavilySearch failed")
        return []

    if isinstance(res, dict):
        return res.get("results", []) or []
    return []


def _build_web_context(results: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for r in results:
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        content = (r.get("raw_content") or r.get("content") or "").strip()
        if not content:
            continue

        header = "\n".join([x for x in [title, url] if x])
        parts.append((header + "\n" if header else "") + content)

    text = "\n\n---\n\n".join(parts).strip()

    max_chars = int(getattr(settings, "FALLBACK_MAX_CHARS", 12000))
    if max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars]

    return text


# ---------------------------
# Answering helpers
# ---------------------------

def _answer_with_context(context: str, question: str) -> str:
    msgs = PROMPT.format_messages(context=context, question=question)
    return get_llm().invoke(msgs).content.strip()


def _fallback_answer(question: str) -> Optional[str]:
    results = _tavily_search_site(question)
    if not results:
        return None

    web_context = _build_web_context(results)
    if not web_context:
        return None

    ans = _answer_with_context(web_context, question)


    if ans.strip() == "__NO_KB__":
        return None

    return ans


# ---------------------------
# Public API
# ---------------------------

def answer_general_question(q: str) -> str:
    q = (q or "").strip()
    if not q:
        return "أهلين 🌿\nاكتب سؤالك من فضلك."

    logger.info("GENERAL_QA question=%s", q)

    top_k = int(getattr(settings, "RAG_TOP_K", 4))
    min_score = float(getattr(settings, "RAG_MIN_SCORE", 0.75))


    docs_scores: List[Tuple[Any, float]] = _vs().similarity_search_with_score(q, k=top_k)
    logger.info("RAG retrieved=%s", len(docs_scores))


    if not docs_scores:
        fb = _fallback_answer(q)
        if fb:
            return fb
        return "أهلين 🌿\nما لقيت جواب واضح هلّق. شو الموضوع بالضبط أو بأي قسم بالموقع؟"


    top_score = docs_scores[0][1]


    if top_score < min_score:
        logger.info("RAG top_score=%s below min=%s => fallback", top_score, min_score)
        fb = _fallback_answer(q)
        if fb:
            return fb

    docs = [d for d, _s in docs_scores]
    context = "\n\n".join(d.page_content for d in docs)
    answer = _answer_with_context(context, q)

    if answer.strip() == "__NO_KB__":
        fb = _fallback_answer(q)
        if fb:
            return fb
        return "أهلين 🌿\nالمعلومة مش متوفرة عندي هلّق. ممكن توضح سؤالك أكثر؟"

    return answer
