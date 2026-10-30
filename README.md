# MedBuddy

A web-based medication-adherence and drug-interaction proof-of-concept. A patient uploads
a prescription; MedBuddy extracts medicine details, checks recognized combinations
against its curated interaction dataset, and supports confirmed reminders — with **no app
install**.

> ⚠️ **Proof-of-concept. Not a certified medical tool — not for clinical use.**
> All drug information comes from a small, curated, static dataset.

See [`docs/README.md`](docs/README.md) for the documentation index, including project
overview, architecture and methodology, backend/API reference, local setup, usage, and
troubleshooting. The faculty-oriented document and diagrams are also in [`docs/`](docs/).

---

## Architecture at a glance

- **Hybrid, on LangGraph** — a prescription photo runs a **fixed pipeline** (one Gemini vision
  call → normalize → interaction check → lookup → templated reply). Everything else
  (onboarding, questions, reminders, adherence) goes to an LLM **tool-use loop** where each
  capability is a **tool**. State changes need a YES/NO confirmation via `interrupt()`.
- **LLM: Google Gemini** via **LiteLLM**, configured **per role** (`AGENT_MODEL`,
  `VISION_MODEL`, `EXPLANATION_MODEL`). OCR is a direct **Gemini vision** call — no Tesseract.
- **Web chat is the application interface** — the React frontend talks to the FastAPI backend;
  a `FakeChannel` remains available for tests and the local CLI.
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

### Backend (PowerShell, repository root)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Set GEMINI_API_KEY in .env, then:
uvicorn medbuddy.main:app --reload --no-access-log
```

### Frontend (second PowerShell terminal)

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, usually `http://localhost:5173`. The backend
defaults to `http://localhost:8000`.

### Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

For all prerequisites, settings, and common fixes, see the [setup
guide](docs/SETUP_GUIDE.md) and [troubleshooting guide](docs/TROUBLESHOOTING.md).
Application steps are printed in the backend terminal and written to the rotating
`logs/medbuddy.log` file. Request access logs are disabled to keep polling output quiet.

---

## Status

Proof-of-concept — KIIT University 5-credit minor project. Not for clinical use.
