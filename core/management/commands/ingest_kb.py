import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

from pinecone import Pinecone
try:
    from pinecone.exceptions import NotFoundException
except Exception:
    from pinecone.exceptions.exceptions import NotFoundException
import logging
logger = logging.getLogger(__name__)


SUPPORTED_EXTS = {".txt", ".md", ".pdf"}


class Command(BaseCommand):
    help = "Ingest files from knowledge_base/ into Pinecone (LangChain)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all vectors in the namespace (or default namespace) before ingest",
        )

    def handle(self, *args, **opts):
        
        # ---- Validate settings ----
        if not getattr(settings, "OPENAI_API_KEY", ""):
            self.stdout.write(self.style.ERROR("Missing OPENAI_API_KEY in settings/.env"))
            return

        if not getattr(settings, "PINECONE_API_KEY", ""):
            self.stdout.write(self.style.ERROR("Missing PINECONE_API_KEY in settings/.env"))
            return

        index_name = getattr(settings, "PINECONE_INDEX_NAME", "")
        if not index_name:
            self.stdout.write(self.style.ERROR("Missing PINECONE_INDEX_NAME in settings/.env"))
            return

        kb_dir = Path(getattr(settings, "RAG_KB_DIR", settings.BASE_DIR / "knowledge_base")).resolve()
        if not kb_dir.exists():
            self.stdout.write(self.style.ERROR(f"Missing folder: {kb_dir}"))
            return

        namespace = getattr(settings, "PINECONE_NAMESPACE", None) or None  # '' -> None
        topk = int(getattr(settings, "RAG_TOP_K", 4))
        
        # ---- Pinecone client + index ----
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        index = pc.Index(index_name)

        # ---- Optional reset ----
        if opts["reset"]:
            try:
                if namespace:
                    index.delete(delete_all=True, namespace=namespace)
                else:
                    index.delete(delete_all=True)  # default namespace
                self.stdout.write(self.style.WARNING(
                    f"Reset done for index={index_name} namespace='{namespace or ''}'"
                ))
            except NotFoundException:
                self.stdout.write(self.style.WARNING("Namespace not found — skipping reset (index empty)"))
        logger.info("ingest_kb start reset=%s index=%s ns=%s", reset, index_name, namespace)

        # ---- Load docs ----
        docs = []
        for p in kb_dir.rglob("*"):
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            if ext not in SUPPORTED_EXTS:
                continue

            try:
                if ext in {".txt", ".md"}:
                    docs += TextLoader(str(p), encoding="utf-8").load()
                elif ext == ".pdf":
                    docs += PyPDFLoader(str(p)).load()
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Skip file (load error): {p.name}"))
                continue

        if not docs:
            self.stdout.write(self.style.ERROR(f"No supported files found in: {kb_dir} (txt/md/pdf)"))
            return

        # ---- Chunking (هنا المكان الصح) ----
        splitter = CharacterTextSplitter(chunk_size=700, chunk_overlap=80)
        chunks = splitter.split_documents(docs)
        logger.info("ingest_kb chunks=%s", len(chunks))

        # ---- Embeddings ----
        emb_model = getattr(settings, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        emb = OpenAIEmbeddings(model=emb_model, api_key=settings.OPENAI_API_KEY)

        # ---- VectorStore (بدون الاعتماد على env var) ----
        vs = PineconeVectorStore(index=index, embedding=emb, namespace=namespace)

        # ---- Upsert ----
        vs.add_documents(chunks)

        self.stdout.write(self.style.SUCCESS(
            f"Ingested {len(chunks)} chunks ✅ into index={index_name} namespace='{namespace or ''}' (RAG_TOP_K={topk})"
        ))
        logger.info("ingest_kb done ✅ upserted=%s", len(chunks))

