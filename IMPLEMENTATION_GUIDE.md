# Implementation Guide — WhatsApp Renewable-Energy Support Agent (AI Bootcamp Capstone)

This document explains what was built in the repository and how the main pieces work together.

## 1) What the project does (high-level)

The system is a **WhatsApp customer-support assistant** for a renewable energy company. It can:
- Answer general FAQ/policy questions using a **RAG pipeline** (Pinecone + OpenAI).
- Answer customer **consumption questions** using a **tool-using agent** that must fetch real values from the database.
- Allow users to **edit profile data** (phone/address) via LLM-based extraction.
- Accept and log **complaints**, then notify staff by email.
- Handle **voice notes** by transcribing them before processing.

---

## 2) Core building blocks

### A) Data Models (Database)
**Files:** `core/models/*.py`

1. **Customer** (`core/models/customer.py`)
   - Stores the user’s identity and billing-meter verification fields.
   - Key fields: `user_key` (Twilio From number), `first_name`, `meter_last4`, `phone`, `address`.

2. **ConsumptionRecord** (`core/models/customer.py`)
   - Stores consumption readings per customer.
   - Key fields: `customer`, `kwh`, `saving_percent`, `period_label`.

3. **Complaint** (`core/models/customer.py`)
   - Stores customer complaints.
   - Key fields: `customer`, `text`, `status`.

4. **ConversationSession** (`core/models/session.py`)
   - Persists the conversation “state machine” state.
   - Key fields: `state`, `pending_intent`, verification fields, `verified_until`.

5. **ChatMessage** (`core/models/message.py`)
   - Stores conversation logs.
   - Key fields: `session`, `direction`, `message_type` (text/voice), `text`.

---

### B) WhatsApp Webhook + State Machine
**File:** `core/views.py`

**Endpoint:** `POST /api/whatsapp/webhook/`

The webhook accepts Twilio WhatsApp requests (form-data) and drives a **state machine** that keeps the conversation structured.

**Main states (examples):**
- `WAIT_MENU` → choose an option (or auto-route)
- `GENERAL_QA` → answer via RAG
- `VERIFY_NAME` / `VERIFY_LAST4` → identity verification for sensitive actions
- `CONSUMPTION_QA` → answer via agent + tools
- `EDIT_CHOOSE` / `EDIT_PHONE` / `EDIT_ADDRESS` → update profile
- `COMPLAINT_TEXT` → record complaint and email staff

**Key behavior:**
- Sensitive actions (consumption, edits, complaints) require short-lived verification (`verified_until`, ~14 minutes).
- Twilio requests get a **TwiML XML** response; non-Twilio requests get JSON.

---

### C) RAG (Retrieval-Augmented Generation) for General Questions
**Files:**
- `core/ai/rag.py`
- `core/ai/prompt.py` (RAG prompt)
- `core/management/commands/ingest_kb.py`

**Flow:**
1. Knowledge base files live in `knowledge_base/` (`.md`, `.txt`, `.pdf`).
2. `python manage.py ingest_kb` loads files, chunks them, generates embeddings, and upserts them into Pinecone.
3. At runtime, `answer_general_question()` performs similarity search (Top-K) and asks the LLM to answer **only from retrieved context**.

---

### D) Agentic Consumption Q&A (Tools + LLM)
**Files:**
- `core/ai/consumption_agent.py`
- `core/ai/consumption_tools.py`
- `core/ai/prompt.py` (agent rules)

**Idea:** consumption questions must use **real values** (no guessing). So the assistant uses a **tool-using agent** with DB-backed tools:

Tools:
- `get_consumption_history(user_key, limit)`
- `compare_last_two_months(user_key)`
- `average_last_n_months(user_key, n)`

The agent decides which tool(s) to call, reads JSON results, then replies in Arabic with a short answer.

---

### E) Edit Profile Routing (LLM Extraction)
**File:** `core/ai/edit_router.py`

If the user writes something like “update my phone to 079…” or “change my address…”, the system uses an LLM prompt to return **strict JSON**:

```json
{ "field": "phone" | "address" | "unknown", "value": "..." }
```

Then `core/views.py` applies the update to the `Customer` record.

---

### F) Voice Notes (Speech-to-Text)
**File:** `core/ai/stt.py`

If Twilio indicates audio media (`MediaContentType0` starts with `audio/`), the system:
1. Downloads the Twilio-hosted media using Twilio credentials.
2. Transcribes it using OpenAI Whisper (`OPENAI_STT_MODEL`, default `whisper-1`).
3. Routes the resulting text through the normal conversation flow.

---

### G) Complaints → Email Notification
**Files:**
- `core/ai/complaint_email.py`
- `core/ai/gmail_sender.py`
- `core/ai/prompt.py` (EMAIL_PROMPT)

When a complaint is created:
1. It’s stored in the database (`Complaint`).
2. The LLM generates a short **Arabic HTML** email body using only the provided fields.
3. The email is sent to `RECEIVED_EMAIL` via the Gmail API send tool.

---

## 3) Configuration (Environment Variables)

**Template:** `.env.example`

Main groups:
- **Database:** `DATABASE_HOST/PORT/USER/PASSWORD/NAME/SCHEMA`
- **OpenAI:** `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_STT_MODEL`
- **Pinecone (RAG):** `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `RAG_TOP_K`
- **Twilio:** `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
- **Email:** `RECEIVED_EMAIL`, `GMAIL_TOKEN_FILE`, `GMAIL_CREDENTIALS_FILE`
- **Observability (optional):** `LANGSMITH_*`

---

## 4) Running the project (local)

1. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
2. Create `.env` from `.env.example` and fill in values.
3. Apply migrations
   ```bash
   python manage.py migrate
   ```
4. Ingest your knowledge base (optional but recommended)
   ```bash
   python manage.py ingest_kb --reset
   ```
5. Run server
   ```bash
   python manage.py runserver
   ```
6. Expose your local server (e.g., via ngrok) and configure Twilio WhatsApp webhook URL to:
   ```
   https://<your-domain>/api/whatsapp/webhook/
   ```

---

## 5) Notes / quick improvements (optional)

- Add **Twilio request signature validation** (currently the code only detects Twilio via the header).
- Register models in `core/admin.py` to manage customers/complaints/consumption from Django Admin.
- In `core/management/commands/ingest_kb.py`, the logger references `reset` (undefined) — it should log `opts["reset"]`.

---

## Quick Reference — “Where is what?”

- Webhook + state machine: `core/views.py`
- RAG answering: `core/ai/rag.py`
- KB ingest: `core/management/commands/ingest_kb.py`
- Consumption agent + tools: `core/ai/consumption_agent.py`, `core/ai/consumption_tools.py`
- Voice transcription: `core/ai/stt.py`
- Complaints email: `core/ai/complaint_email.py`, `core/ai/gmail_sender.py`
