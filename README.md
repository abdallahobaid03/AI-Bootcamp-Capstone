# Pulse — WhatsApp Renewable‑Energy Support Agent

A WhatsApp customer-support assistant for a renewable energy company in Jordan.

It supports:
- **General questions (FAQ/policies)** via **RAG** (Pinecone vector search + OpenAI).
- **Consumption questions** via a **tool‑using agent** that reads from the database (no guessing).
- **Profile edits** (phone/address) using LLM-based JSON extraction.
- **Complaints** that are saved in the DB and **emailed to staff** via Gmail API.
- **Voice notes**: downloads WhatsApp audio from Twilio and transcribes it with OpenAI Whisper.

> Note: the bot replies in **Arabic (Jordanian dialect)** by default (see `core/ai/prompt.py`). Docs in this repo are in English.

---

## Key Features

- **RAG Knowledge Base**
  - Put docs in `knowledge_base/` (`.txt`, `.md`, `.pdf`).
  - Run an ingest command to chunk + embed + upload to Pinecone.
  - Runtime answers are generated **only from retrieved context**.

- **Agentic Consumption Q&A (Tools + LLM)**
  - Uses DB-backed tools:
    - `get_consumption_history(user_key, limit)`
    - `compare_last_two_months(user_key)`
    - `average_last_n_months(user_key, n)`
  - The agent decides which tool(s) to call and summarizes results.

- **Conversation State Machine**
  - A simple menu + routing flow inside the WhatsApp webhook.
  - Sensitive actions require short-lived identity verification (first name + last 4 digits of meter).

---

## Architecture (high level)

WhatsApp user → **Twilio Webhook** → **Django API** (`/api/whatsapp/webhook/`) →
- **RAG pipeline** (Pinecone + OpenAI) for general questions
- **Tool‑using consumption agent** for consumption questions
- **DB updates** for profile edits
- **DB + Gmail send** for complaints
- **Whisper transcription** for voice messages

Data is stored in **PostgreSQL** via Django models.

---

## Repository Guide

- Code map: `PROJECT_STRUCTURE.md`
- Implementation details: `IMPLEMENTATION_GUIDE.md`

Main entry points:
- WhatsApp webhook + conversation logic: `core/views.py`
- RAG answering: `core/ai/rag.py`
- KB ingest command: `core/management/commands/ingest_kb.py`
- Consumption agent + tools: `core/ai/consumption_agent.py`, `core/ai/consumption_tools.py`

---

## Requirements

- **Python 3.10** (see `.python-version`)
- **PostgreSQL** database
- Accounts/keys:
  - **OpenAI** API key
  - **Pinecone** API key + index
  - **Twilio** (WhatsApp sandbox or approved WhatsApp sender)
  - **Gmail API credentials** (OAuth) if you want complaint emailing

---

## Setup (Local)

### 1) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # (Windows: .venv\\Scripts\\activate)

pip install -r requirements.txt
```

### 2) Configure environment variables

Copy the template and fill the values:

```bash
cp .env.example .env
```

Minimum required for most features:
- PostgreSQL: `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_NAME`, `DATABASE_SCHEMA`
- OpenAI: `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_DEFAULT_TEMPERATURE`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_STT_MODEL`
- Pinecone: `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `RAG_TOP_K`
- Twilio: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`

For complaint emails:
- `RECEIVED_EMAIL`, `GMAIL_TOKEN_FILE`, `GMAIL_CREDENTIALS_FILE`

### 3) Run migrations

```bash
python manage.py migrate
```

### 4) Ingest the knowledge base (recommended)

Put your FAQ/policy files in `knowledge_base/`, then run:

```bash
python manage.py ingest_kb --reset
```

Quick test:

```bash
python manage.py ask_kb "شو ساعات الدوام؟"
```

### 5) Run the server

```bash
python manage.py runserver
```

---

## Twilio WhatsApp Webhook Setup

1. Expose your local server (example using ngrok):

```bash
ngrok http 8000
```

2. In Twilio WhatsApp settings, set the webhook to:

- **POST** `https://<your-ngrok-domain>/api/whatsapp/webhook/`

Twilio sends form-data fields like `From`, `Body`, plus media fields for voice notes.

---

## Testing Without Twilio (Local JSON)

If you send a normal (non-Twilio) request, the API returns JSON:

```bash
curl -X POST http://127.0.0.1:8000/api/whatsapp/webhook/ \
  -H "Content-Type: application/json" \
  -d '{"From":"whatsapp:+962790000000","Body":"menu"}'
```

You should get:

```json
{"reply": "..."}
```

---

## Demo Data (Recommended)

Consumption answers require a `Customer` and some `ConsumptionRecord` rows.

Example seed (Django shell):

```bash
python manage.py shell
```

```python
from core.models import Customer, ConsumptionRecord

user_key = "whatsapp:+962790000000"

c, _ = Customer.objects.get_or_create(
    user_key=user_key,
    defaults={
        "first_name": "Ahmad",
        "meter_last4": "1234",
        "phone": "+962790000000",
        "address": "Amman",
    },
)

ConsumptionRecord.objects.get_or_create(customer=c, period_label="2025-12", defaults={"kwh": 320, "saving_percent": 12})
ConsumptionRecord.objects.get_or_create(customer=c, period_label="2026-01", defaults={"kwh": 280, "saving_percent": 15})
```

Now you can test consumption questions after verifying name + last4.

---

## Customization

- **Change bot language/tone:** edit prompts in `core/ai/prompt.py`.
- **Add more tools for the agent:** extend `core/ai/consumption_tools.py` and include them in `core/ai/consumption_agent.py`.
- **Add admin dashboards:** register models in `core/admin.py`.

---

## Known Notes

- Twilio request signature validation is not enforced (the code detects Twilio by header). Add validation before production.
- `ingest_kb.py` has a small logging bug (`reset` variable in a logger line). If you see an error, replace `reset` with `opts["reset"]`.

---

## Documentation

- `PROJECT_STRUCTURE.md` — file/folder map
- `IMPLEMENTATION_GUIDE.md` — system design + workflows

