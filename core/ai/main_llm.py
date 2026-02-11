from functools import lru_cache
from django.conf import settings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

import os

os.environ.setdefault("LANGSMITH_TRACING", "true")
os.environ.setdefault("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
os.environ.setdefault("LANGSMITH_API_KEY", settings.LANGSMITH_API_KEY)
os.environ.setdefault("LANGSMITH_PROJECT", settings.LANGSMITH_PROJECT)


@lru_cache(maxsize=2)
def get_llm():
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=settings.OPENAI_DEFAULT_TEMPERATURE,
        max_retries=int(getattr(settings, "OPENAI_MAX_RETRIES", 3)),
        api_key=settings.OPENAI_API_KEY,
        max_tokens=500,
    )

@lru_cache(maxsize=2)
def get_embeddings():
    return OpenAIEmbeddings(model=settings.OPENAI_EMBEDDING_MODEL,api_key=settings.OPENAI_API_KEY)
