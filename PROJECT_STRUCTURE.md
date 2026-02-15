# Project Structure — AI Bootcamp Capstone (WhatsApp Support Agent)

This document describes the folder layout of the repository and what each part is responsible for.

## Top-level layout

```
AI-Bootcamp-Capstone-try-to-make-it-agentic/
├── .env.example
├── .gitignore
├── .python-version
├── README.md
├── manage.py
├── main.py
├── pyproject.toml
├── requirements.txt
├── uv.lock
├── knowledge_base/
├── checking codes/
├── config/
└── core/
```

## Key folders

### `config/` — Django project configuration
Holds the Django “project” settings and global routing.

- `config/settings.py` — environment-driven configuration (Postgres, OpenAI, Pinecone, Twilio, Gmail, logging).
- `config/urls.py` — main URL router (`/admin/` + `/api/`).
- `config/asgi.py` / `config/wsgi.py` — deployment entrypoints.

### `core/` — Main Django app
Everything related to the WhatsApp assistant lives here.

- `core/views.py` — Twilio WhatsApp webhook endpoint + conversation state machine.
- `core/urls.py` — API routes for the app (currently the WhatsApp webhook).
- `core/models/` — database models (customers, sessions, chat logs, complaints, consumption).
- `core/migrations/` — Django migrations.
- `core/ai/` — AI and automation modules:
  - `main_llm.py` — OpenAI Chat model + embeddings configuration.
  - `prompt.py` — system prompts + templates (RAG, edit extraction, complaint email, consumption agent rules).
  - `rag.py` — Pinecone-based retrieval + LLM answer generation for general FAQs.
  - `consumption_agent.py` — tool-using agent for consumption Q&A.
  - `consumption_tools.py` — DB-backed tools (history, compare last two months, average N months).
  - `edit_router.py` — extracts profile-edit requests (phone/address) into JSON.
  - `stt.py` — voice message detection + Twilio media download + Whisper transcription.
  - `complaint_email.py` — formats complaint emails (LLM) and sends them.
  - `gmail_sender.py` — Gmail API sending via LangChain community tool.
- `core/management/commands/` — CLI commands:
  - `ingest_kb.py` — ingest files from `knowledge_base/` into Pinecone.
  - `ask_kb.py` — quick test command to query the RAG pipeline.

### `knowledge_base/` — RAG source documents
Put your company FAQ / policy content here (supported: `.txt`, `.md`, `.pdf`).
These files are chunked and embedded, then stored in Pinecone via `python manage.py ingest_kb`.

### `checking codes/` — Scratch / experiments
Small scripts used during development (e.g., Pinecone connectivity checks). Not required for production.

## How to navigate the code quickly

- **Webhook + conversation logic:** `core/views.py`
- **General questions (RAG):** `core/ai/rag.py` + `core/management/commands/ingest_kb.py`
- **Consumption questions (agent + tools):** `core/ai/consumption_agent.py` + `core/ai/consumption_tools.py`
- **Voice messages:** `core/ai/stt.py`
- **Complaints → email:** `core/ai/complaint_email.py` + `core/ai/gmail_sender.py`
- **Environment variables template:** `.env.example`
