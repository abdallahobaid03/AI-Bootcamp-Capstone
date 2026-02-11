from functools import lru_cache
from django.conf import settings
from langchain_core.prompts import ChatPromptTemplate
from langchain_pinecone import PineconeVectorStore
from core.ai.main_llm import get_llm, get_embeddings
from pinecone import Pinecone
from core.ai.prompt import Prompt

PROMPT = Prompt.RAG_PROMPT

@lru_cache(maxsize=1)
def _vs():
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index = pc.Index(settings.PINECONE_INDEX_NAME)
    return PineconeVectorStore(index=index, embedding=get_embeddings())

def answer_general_question(q: str) -> str:
    q = (q or "").strip()
    if not q:
        return "اكتب سؤالك من فضلك."

    docs = _vs().similarity_search(q, k=int(settings.RAG_TOP_K))
    if not docs:
        return "ما لقيت جواب ضمن المعرفة الحالية. ممكن توضح سؤالك أكثر؟"

    context = "\n\n".join(d.page_content for d in docs)
    msgs = PROMPT.format_messages(context=context, question=q)
    answer = get_llm().invoke(msgs).content.strip()

    # مصادر مختصرة
    sources = []
    for d in docs:
        src = d.metadata.get("source") or d.metadata.get("file_path") or ""
        if src:
            sources.append(src.split("\\")[-1].split("/")[-1])

    sources = list(dict.fromkeys(sources))[:3]
    if sources:
        answer += "\n\nالمصادر: " + "، ".join(sources)

    return answer
