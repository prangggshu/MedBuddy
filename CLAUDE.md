# MedBuddy — Project Context for Claude Code

## What this is
MedBuddy is a WhatsApp-based medication adherence & drug-interaction assistant. A patient photographs their prescription, the system extracts the medicines, explains them in plain language, flags dangerous drug-drug interactions, and sends WhatsApp reminders to take each dose — with zero app install required.

**Type:** 5-credit college minor project (KIIT University), 1-month timeline, team of 2.
**Status:** Proof-of-concept. Not a certified medical tool — explicitly not for clinical use.

---

## Current Decisions & Status — living section (last updated 2026-09-20)

> **Portable source of truth** for decisions made during development, so the project can be resumed from any account/IDE. Where this section conflicts with older framing below, **this section wins**. Keep it updated as decisions change.

**Stage:** Scaffolding complete. Repo structure and module skeletons exist; core logic not yet implemented.
**Deadline:** 2 weeks from 2026-09-20. Prangshu starting solo; Arundhati joins in parallel once tools are unblocked.
**Priority:** Working demo + evaluation numbers + report. Nothing else.

### Architecture: FULLY AGENTIC with LangGraph — DECIDED
We are building the **fully-agentic** design using **LangGraph** as the agent framework.

- Every capability (OCR + extraction, normalization, interaction check, explanation, reminder scheduling, adherence logging, drug/interaction lookups) is exposed to the LLM as a **tool**. The LangGraph agent node decides which tools to call, and in what order.
- **No fixed pipeline** — the flow is not OCR → extract → normalize → check. The agent orchestrates freely.
- The **real design work is the tool set**: each tool's name, input/output schema, and whether it is state-changing.
- **LangGraph chosen because:** the confirmation gate (agent proposes → patient confirms → tool commits) maps cleanly onto `interrupt()`, with the Postgres checkpointer holding state between WhatsApp turns. Per-patient conversation history is free via `thread_id = whatsapp_number`.

> **Note:** `docs/MedBuddy-Project-Document.md` is the faculty proposal doc — it analyzes hybrid vs agentic and is not expected to match implementation decisions. Treat it as a design artefact, not a spec.

### Grounding guardrails — safety enforced structurally, not by pipeline order
1. The **explanation tool may only describe drugs a lookup tool actually returned**; an unmatched drug → forced disclaimer path, never free-text drug info.
2. **System-prompt hard rule:** no drug/interaction statement may exist without a tool result behind it.
3. **State-changing tools** (`schedule_reminder`, `log_adherence`) use LangGraph `interrupt()` — agent proposes → patient replies on WhatsApp → graph resumes → tool commits.

### LLM strategy — Gemini, per-role, swappable — DECIDED
- **Current provider: Google Gemini** for all roles (agent loop, vision/extraction, explanation).
- **Per-role model config via env**, so the provider can be swapped without code changes:
  - `AGENT_MODEL` — orchestration / tool-use loop; needs reliable function-calling.
  - `VISION_MODEL` — image → structured extraction (prescription photo); needs vision.
  - `EXPLANATION_MODEL` — plain-language rephrasing; can be a cheaper model.
- **LangGraph wiring:** use `init_chat_model` with provider-prefixed model strings (e.g. `google_genai/gemini-2.0-flash`). Swapping to OpenAI or Anthropic later is a config change only.
- **No Tesseract.** OCR is a direct Gemini vision call. `tools/ocr.py` should call the vision model, not Tesseract.
- **Caveat:** Gemini free-tier rate limits can be hit quickly in an agentic loop (multiple model calls per message + a vision call per photo). Add retry with exponential backoff in `medbuddy/llm/client.py`.
- **Privacy note:** prescription images are sent to Google's cloud. Use synthetic or anonymised prescriptions during development; document this as a known limitation in the report.

### Transport abstraction — DECIDED
Twilio/WhatsApp is **just a transport**. `medbuddy/channels/` has:
- `base.py` — `MessagingChannel` interface
- `fake.py` — `FakeChannel` / console channel for zero-credit local dev and tests
- `twilio.py` — Twilio adapter, wired in last

Use a **mockable clock** (`medbuddy/scheduler/clock.py`) so reminder timing and 3-day-expiry can be tested without real time passing.

### Cut scope — explicitly dropped to hit the 2-week deadline
These were in the original plan and are **not being built**. Do not implement them, do not suggest them:
- **Dashboard** — `scripts/cli.py` is the demo interface. No React, no HTML dashboard.
- **Snooze** — adherence replies are `taken` and `missed` only.
- **Multi-step missed-dose escalation** — log the miss, send one nudge, stop.
- **Postgres** — SQLite for the full 2 weeks. Swap only if Render deployment forces it.
- **Any LLM provider other than Gemini** — don't add OpenAI/Anthropic/Groq paths yet.

### Evaluation — two layers
1. **Component accuracy** — each tool tested deterministically against a labelled set (`tests/test_interactions.py`, `tests/test_normalize.py`, etc.).
2. **Orchestration success** — over a test set of messages, did the agent call the right tools? (`tests/test_agent_orchestration.py`).

---

## Repo structure

```
medbuddy/
  agent/
    loop.py           # LangGraph graph definition — agent node + tool node + interrupt logic
    registry.py       # Tool registry — all tools bound here, passed to the agent
    system_prompt.py  # System prompt with grounding hard rules
  channels/
    base.py           # MessagingChannel ABC
    fake.py           # FakeChannel for local dev
    twilio.py         # Twilio WhatsApp adapter
  datasets/
    loaders.py        # Loads brand_generic.csv + interactions.csv into memory
  db/
    models.py         # SQLAlchemy ORM models
    repo.py           # DB queries / repository layer
    session.py        # DB session setup
  llm/
    client.py         # init_chat_model wrapper, retry/backoff, per-role model config
  scheduler/
    clock.py          # Mockable clock interface
  tools/
    base.py           # Tool base class / shared schema helpers
    ocr.py            # Gemini vision call → raw text (no Tesseract)
    extract.py        # LLM structured extraction → Pydantic-validated JSON
    normalize.py      # Brand → generic fuzzy match against brand_generic.csv
    interactions.py   # Drug-pair interaction check against interactions.csv
    drug_info.py      # lookup_drug_info — grounding source for explanations
    patient.py        # Patient registration / get_my_meds
    reminders.py      # schedule_reminder (state-changing, requires confirmation)
    adherence.py      # log_adherence (state-changing, requires confirmation)
  config.py           # Env vars: AGENT_MODEL, VISION_MODEL, EXPLANATION_MODEL, DB_URL, etc.
  main.py             # FastAPI app, webhook endpoint
  runtime.py          # Top-level: receive message → run agent → send reply
  schemas.py          # Shared Pydantic schemas
data/
  brand_generic.csv
  interactions.csv
  sample_prescriptions/   # empty — add synthetic/anonymised images here
scripts/
  cli.py              # CLI runner for local testing without WhatsApp
tests/
  conftest.py
  test_agent_orchestration.py
  test_interactions.py
  test_normalize.py
  test_reminders.py
docs/
  MedBuddy-Project-Document.md / .docx   # Faculty proposal — design artefact only
  diagrams/                               # Mermaid sources + rendered PNGs
```

---

## Team
- **Prangshu** — backend architecture, DB schema, interaction rule engine, scheduler/reminder logic, WhatsApp webhook integration. Secondary: testing, deployment.
- **Arundhati** — OCR + LLM extraction pipeline, drug normalization, grounded explanation generation, evaluation metrics. Secondary: dataset curation, report writing.
- Both: dataset curation (interactions + brand-generic mapping), end-to-end integration testing, report + demo prep.

---

## Core user flow
1. Patient sends "Hi" → registers name + age (one WhatsApp number = one patient, no multi-tenant auth)
2. Patient sends a photo of their prescription
3. `run_ocr` tool: Gemini vision call → raw extracted text
4. `extract_medications` tool: LLM structured extraction → drug name, dosage, frequency, duration (Pydantic-validated JSON)
5. `normalize_drug` tool: brand → generic via fuzzy match against `brand_generic.csv`
6. `check_interactions` tool: all drug pairs checked against `interactions.csv`, severity flagged (minor/moderate/major)
7. `lookup_drug_info` tool: fetches grounding data; explanation LLM call is constrained to this output only
8. Agent sends plain-language explanation + interaction warnings to patient
9. Agent proposes reminder schedule → LangGraph `interrupt()` → patient confirms → `schedule_reminder` commits
10. Patient replies "taken" / "missed" / "snooze" → `log_adherence` commits (also behind `interrupt()`)
11. If no reply within window, scheduler triggers a missed-dose nudge
12. Everything logged per patient in DB

---

## Tech stack

| Layer | Tech |
|---|---|
| Messaging | Twilio WhatsApp Sandbox API |
| Backend | FastAPI, Python |
| Agent framework | **LangGraph** |
| OCR + extraction | **Gemini vision** (single multimodal call — no Tesseract) |
| LLM layer | `init_chat_model` — currently **Google Gemini**; per-role env config (`AGENT_MODEL`, `VISION_MODEL`, `EXPLANATION_MODEL`) |
| Interaction engine | Python rule engine + `data/interactions.csv` |
| Scheduler | APScheduler + mockable clock |
| Database | PostgreSQL (SQLite for local dev); LangGraph checkpointer on same DB |
| Deployment (optional) | Docker, **Render** free tier (not Railway) |

DB tables: `patients`, `prescriptions`, `medications`, `interactions`, `reminders`, `adherence_logs`

---

## Explicitly out of scope
- No live FDA/WHO API integration — static curated dataset only
- No clinical-grade accuracy claims — proof-of-concept disclaimer throughout
- No multi-tenant auth — single patient per WhatsApp number
- No doctor-facing dashboard — patient-facing only

---

## Evaluation metrics (for the report)
- Extraction accuracy: precision & recall on drug name, dosage, frequency vs manually labelled test set
- Interaction-detection correctness: accuracy against known test-case combinations
- Reminder delivery success rate: % of scheduled reminders sent on time
- End-to-end latency: photo upload → explanation delivered

---

## Twilio Sandbox constraints
- **Sandbox only** — for testing/discovery, not production.
- **100 free WhatsApp messages** on trial; beyond that, billed at standard rates.
- **Sessions expire 3 days after joining** — test numbers must re-send `join <code>` every 3 days. Plan for this during Weeks 3–4 testing; document as a known limitation.
- **1 message per 3 seconds** rate limit — queue bursty sends rather than firing all at once.
- **Business-initiated messages outside 24h window** — only pre-approved sandbox templates allowed. Workaround: keep reminder flow inside the 24h window (natural if patients reply taken/missed daily), or repurpose the "Appointment Reminders" template placeholders.
- Sandbox uses shared number `+14155238886` — cosmetic, but document as a production-readiness gap.

---

## Notes for Claude Code
- **Architecture is LangGraph-based fully agentic** — no fixed pipeline, no hardcoded step ordering.
- **LLM layer uses `init_chat_model`** with Gemini currently. Do not hardcode Anthropic or OpenAI SDKs directly.
- **No Tesseract** — `tools/ocr.py` is a Gemini vision call.
- **Grounding is mandatory** — `tools/drug_info.py` result must gate any explanation. Never let the LLM invent drug information.
- **State-changing tools use `interrupt()`** — `schedule_reminder` and `log_adherence` must not commit without patient confirmation.
- Treat `data/brand_generic.csv` and `data/interactions.csv` as static files, not live API calls.
- `data/sample_prescriptions/` is empty — populate with synthetic or anonymised images only.
- Keep the scope disclaimer ("proof-of-concept, not for clinical use") visible in any user-facing copy.
- Favor **Render** over Railway in deployment scripts or docs.
