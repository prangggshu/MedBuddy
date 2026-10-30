# Local Setup Guide

These steps run MedBuddy locally on Windows using PowerShell. Use synthetic or
anonymized prescriptions only. The project is not for clinical use.

## Prerequisites

- Python 3.10 or later
- Node.js and npm
- A Gemini API key for model-powered chat and prescription extraction
- Internet access for the configured LLM provider and MedlinePlus search

## 1. Prepare the backend

Run from the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally and set `GEMINI_API_KEY`. Keep the key private: do not paste it into
chat, documentation, source files, screenshots, or commits.

The default settings use SQLite, Gemini model strings, port 8000 for the API, and a
10 MB upload limit. See `.env.example` for all configurable values.

If PowerShell blocks virtual-environment activation, either allow activation according
to your local policy or call the environment executable directly, for example:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 2. Start the backend

In the activated environment at the repository root:

```powershell
uvicorn medbuddy.main:app --reload --no-access-log
```

The API is available at `http://localhost:8000`. Check `http://localhost:8000/health`
for a basic health response. On startup, the app initializes database tables. The
application database defaults to `medbuddy.db`; LangGraph checkpoints default to the
separate `checkpoints.db`.

## 3. Start the frontend

Open a second PowerShell terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the Vite development URL shown in the terminal, usually
`http://localhost:5173`. The default frontend API base URL is
`http://localhost:8000`; it can be overridden with `frontend/.env` using
`VITE_API_URL`.

## 4. Run tests

From the repository root with the Python environment active:

```powershell
python -m pytest
```

Or run focused suites:

```powershell
python -m pytest tests\test_normalize.py tests\test_interactions.py tests\test_prescription_pipeline.py
python -m pytest tests\test_web_api.py
```

Build-check the frontend:

```powershell
Set-Location frontend
npm run build
```

## Optional: terminal CLI

The CLI is for local development and tests; the browser chat is the main demo interface.
From the repository root:

```powershell
python -m scripts.cli
```

## Stop services

Press `Ctrl+C` in each terminal running Uvicorn or Vite.

## Privacy and data warning

Prescription images are sent to the configured external LLM provider for extraction.
Use synthetic or anonymized documents only. The phone number is a demo identity, not
authentication. Do not use real patient records or treat the application as clinical
software.
