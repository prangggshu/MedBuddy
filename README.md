# MedBuddy

A WhatsApp-based medication adherence & drug-interaction assistant. A patient photographs
their prescription; MedBuddy extracts the medicines, explains them in plain language, flags
dangerous drug–drug interactions, and sends dose reminders — with **no app install**.

> ⚠️ **Proof-of-concept. Not a certified medical tool — not for clinical use.**
> All drug information comes from a small, curated, static dataset.

See [`CLAUDE.md`](CLAUDE.md) for the full project context and design decisions, and
[`docs/`](docs/) for the faculty design document + architecture diagrams.

---

## Architecture at a glance

- **Hybrid, on LangGraph** — a prescription photo runs a **fixed pipeline** (one Gemini vision
  call → normalize → interaction check → lookup → templated reply). Everything else
  (onboarding, questions, reminders, adherence) goes to an LLM **tool-use loop** where each
  capability is a **tool**. State changes need a YES/NO confirmation via `interrupt()`.
- **LLM: Google Gemini** via **LiteLLM**, configured **per role** (`AGENT_MODEL`,
  `VISION_MODEL`, `EXPLANATION_MODEL`). OCR is a direct **Gemini vision** call — no Tesseract.
- **Transport is abstracted** — a `MessagingChannel` interface with a `FakeChannel` lets the
  whole system run **end-to-end with zero Twilio credits**. Twilio is one adapter, added last.
- **Grounding is structural** — the LLM never invents drug facts: it may only describe drugs a
  lookup tool returned; unmatched drugs hit a disclaimer path.

```
medbuddy/   config · main · schemas · llm/ · agent/ · tools/ · channels/ · db/ · datasets/ · scheduler/
data/       static curated datasets (brand_generic.csv, interactions.csv) + sample images
scripts/    cli.py — drive the agent locally (zero credits)
tests/      component tests + agent-orchestration test
docs/       faculty design document + diagrams
```

---

## Quickstart

```bash
# 1. Install deps
pip install -r requirements.txt

# 2. Configure
cp .env.example .env      # then set GEMINI_API_KEY

# 3. Run the agent locally with NO Twilio — talk to it in your terminal
python -m scripts.cli

# 4. Run the API server (for the Twilio webhook, later)
uvicorn medbuddy.main:app --reload

# 5. Tests
pytest
```

Keep `CHANNEL=fake` during development — it costs nothing and needs no Twilio setup. Switch to
`CHANNEL=twilio` only when wiring the real WhatsApp sandbox in Week 3.

---

## Status

Proof-of-concept — KIIT University 5-credit minor project. Not for clinical use.
