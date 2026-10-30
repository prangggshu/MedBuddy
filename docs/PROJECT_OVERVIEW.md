# MedBuddy Project Overview

## Project summary

MedBuddy is a browser-based medication-adherence and drug-interaction assistant
prototype. A patient can enter a phone number, chat with the assistant, upload a
prescription image or PDF, review extracted medicines and dataset-backed interaction
findings, request reminders, and report a dose as taken or missed. The frontend is a
React web chat; the backend is a FastAPI application.

> **Academic proof-of-concept only. Not a certified medical device and not for clinical
> use.** Prescription extraction can be wrong, the datasets are incomplete, and results
> must not replace advice from a qualified healthcare professional.

## Problem and motivation

Patients may find prescription names and instructions difficult to interpret, and people
taking multiple medicines may benefit from being reminded to ask a professional about
possible interactions. MedBuddy explores whether an accessible chat interface can
combine prescription reading, static interaction lookup, reminders, and adherence
logging in one demonstration application.

This prototype does not establish that it improves adherence or detects interactions
comprehensively. Those claims require appropriate evaluation and clinical validation.

## Objectives

- Extract medicine name, dosage, frequency, and duration from a prescription image.
- Resolve known brand names against a curated brand-to-generic CSV.
- Compare recognized generic ingredients pairwise against a static interaction CSV.
- Keep medicine and interaction statements grounded in the results supplied by the
  application tools and datasets.
- Support patient profile registration, reminder proposals, and taken/missed logging in
  chat with explicit confirmation before state changes.
- Provide a separate MedlinePlus health-topic search in the web interface.

## Implemented functionality

### Browser chat

- Phone-number entry to identify a demo patient; it is not secure authentication.
- Text messages and JPEG, PNG, WebP, or PDF attachments.
- Upload progress, image preview, chat history polling, typing state, and retry UI.
- Health-topic search backed by MedlinePlus.

### Prescription processing

An uploaded image follows a fixed pipeline: vision-model extraction, schema validation,
name normalization, interaction lookup, and a response rendered from the results.
Unmatched names are identified as outside the local dataset. PDFs are rendered as images
for up to their first three pages.

### Chat tools

The text agent can use tools for OCR, medication extraction, normalization, interaction
checks, grounded drug lookup, profile registration, medication-list retrieval, reminder
scheduling, and adherence logging.

### Reminders and adherence

Scheduling and adherence writes pause for a patient confirmation. The reminder feature
stores the next occurrence for each supplied time. Due reminders are dispatched during
browser message polling; there is no continuously running scheduler or implemented
daily recurrence. Adherence responses are `taken` and `missed`; snooze and missed-dose
escalation are not implemented.

## Technology

| Layer | Current implementation |
|---|---|
| Frontend | React, TypeScript, Vite |
| Web API | FastAPI, Uvicorn |
| Agent orchestration | LangGraph |
| LLM integration | LiteLLM; Gemini is the configured default |
| Data validation | Pydantic |
| Database | SQLAlchemy; SQLite by default |
| Name matching | RapidFuzz |
| Prescription images | Vision-capable LLM; no Tesseract in the automatic photo path |
| Reference data | `data/brand_generic.csv` and `data/interactions.csv` |

At the time this documentation was prepared, the brand/generic file contains 500
mappings and the interaction file contains 560 unique pairs. The interaction file
includes 503 DDInter 2.0 risk-level entries matched to names in the project’s medicine
mapping data. The additions identify severity only and use a neutral consultation
message; they do not carry pair-specific mechanisms or management advice.

## Evaluation approach

Tests in the repository cover core normalization, interaction lookup, prescription
pipeline behavior, reminder calculations, API behavior, and agent orchestration. Tests
verify software behavior; they are not clinical validation.

For a report, measurable evaluation can include:

- medication-name and field extraction accuracy against a manually labelled synthetic
  or anonymized prescription set;
- expected interaction-pair and severity lookup results against labelled test cases;
- due-reminder dispatch behavior under controlled time;
- upload-to-reply latency, with model and network conditions recorded.

Report numerical results only after running the stated evaluation on a documented test
set. Do not infer clinical effectiveness from unit-test pass rates.

## Scope and limitations

- Small static datasets do not represent all medicines or all interactions.
- A missing interaction match means “not found in this dataset,” not “safe.”
- Extracted medicine details may be wrong or incomplete.
- Drug lookup intentionally does not provide comprehensive indications, adverse effects,
  contraindications, or personalized treatment advice.
- Prescription images are sent to the configured external LLM provider; use only
  synthetic or anonymized examples for demonstrations and testing.
- The phone number is an identity key, not a verified account or security boundary.
- The health-topic search is distinct from the medication interaction dataset.
- No clinical validation, regulatory certification, clinician dashboard, WhatsApp
  transport, Tesseract OCR, or production reminder service is implemented.

## Report-ready short description

> MedBuddy is a browser-based medication-assistance proof-of-concept built with React,
> FastAPI, and LangGraph. Prescription images follow a fixed workflow that extracts
> medication details with a vision model, normalizes recognized names against a curated
> mapping file, checks recognized ingredients against a static interaction dataset, and
> returns a grounded template. Text chat uses an LLM tool-use loop for profile, medicine,
> reminder, and adherence tasks. Reminder and adherence writes require patient
> confirmation. The system is not clinically validated and is not for clinical use.
