# MedBuddy — Complete Project Brief

## 1. What the project is

MedBuddy is a browser-based medication adherence and drug-interaction assistant for patients. A patient can upload a prescription, and the system:

- extracts the medicines
- explains them in plain language
- identifies dangerous drug-drug interactions
- tracks reminders
- logs adherence
- answers basic trusted health questions

It is designed as a patient-facing web chat demo, not as a clinical medical tool.

> Proof-of-concept only. Not for clinical use.

## 2. Project status and scope

This is a KIIT university minor project, built as a working proof-of-concept in a short timeline. The emphasis is on a working demo and evaluation, not a production medical product.

The project intentionally keeps the scope narrow:

- no real clinical certification
- no live FDA/WHO integration
- no hospital dashboard
- no multi-tenant auth
- no production-grade medical safety claims

## 3. Architecture overview

The architecture is hybrid and built on LangGraph.

- Prescription photos use a fixed deterministic pipeline.
- General chat and tool use go through an LLM-driven agent loop.
- Safety-critical state changes require confirmation before data is saved.

This is not a fully agentic system. It is hybrid by design.

### 3.1 Hybrid architecture decision

The project routes messages as follows:

- If the patient sends a photo, it goes to a fixed prescription pipeline.
- If the patient sends normal text, it goes to the agent/tool loop.

This avoids an expensive and unsafe fully-agentic prescription workflow, which would require many LLM calls and increase the chance of ungrounded or unsafe medical claims.

The relevant implementation is in:

- [medbuddy/agent/loop.py](../medbuddy/agent/loop.py)
- [medbuddy/agent/prescription.py](../medbuddy/agent/prescription.py)

## 4. Core technical stack

### Frontend

- React
- Vite
- TypeScript
- Tailwind

Main frontend file:

- [frontend/src/App.tsx](../frontend/src/App.tsx)

### Backend

- Python
- FastAPI
- SQLAlchemy
- SQLite for demo/local development
- LangGraph

Main backend files:

- [medbuddy/main.py](../medbuddy/main.py)
- [medbuddy/api_web.py](../medbuddy/api_web.py)
- [medbuddy/runtime.py](../medbuddy/runtime.py)

### LLM layer

- LiteLLM wrapper
- Google Gemini as the current provider
- configurable per role: agent, vision, explanation

Relevant files:

- [medbuddy/llm/client.py](../medbuddy/llm/client.py)
- [medbuddy/config.py](../medbuddy/config.py)

### Data and persistence

- SQLite database
- curated static CSV datasets

Relevant files:

- [medbuddy/db/models.py](../medbuddy/db/models.py)
- [data/brand_generic.csv](../data/brand_generic.csv)
- [data/interactions.csv](../data/interactions.csv)

## 5. The main user flow

1. Patient opens the browser chat.
2. Patient logs in with a phone number.
3. Patient sends a prescription photo or types medications.
4. If photo:
   - extract medication names
   - normalize brand names to generics
   - check interactions
   - retrieve grounded drug info
   - show a medical explanation template
5. If text:
   - the agent may choose the relevant tool or tools
   - it can ask for profile data, reminder schedule, adherence status, etc.
6. If the patient wants reminders, the app proposes a reminder schedule and asks for confirmation.
7. The patient confirms or cancels.
8. If the patient replies with “taken” or “missed”, adherence is logged after confirmation.

## 6. What features are implemented

### 6.1 Prescription upload in browser chat

The browser chat is the primary app interface. Patients can send:

- text messages
- images
- PDF files

The frontend has upload validation, preview, and message status behavior.

Relevant file:

- [frontend/src/App.tsx](../frontend/src/App.tsx)

### 6.2 Patient registration and profile

One phone number is treated as one patient identity.

The system stores:

- patient phone number
- name
- age

Relevant file:

- [medbuddy/tools/patient.py](../medbuddy/tools/patient.py)

### 6.3 OCR and prescription reading

The app uses a vision-capable LLM to read prescription images. It does not use Tesseract.

Relevant file:

- [medbuddy/tools/ocr.py](../medbuddy/tools/ocr.py)

### 6.4 Medication extraction

The app reads the image or typed text and extracts structured values:

- medication name
- dosage
- frequency
- duration

The extracted data is saved to the database.

Relevant file:

- [medbuddy/tools/extract.py](../medbuddy/tools/extract.py)

### 6.5 Normalization to generic names

Prescription names may be brand names or generic names. The normalization tool tries to map them to a generic reference using a static curated dataset.

Relevant file:

- [medbuddy/tools/normalize.py](../medbuddy/tools/normalize.py)

### 6.6 Interaction detection

The system checks pairwise combinations among medicines in the prescription and returns matching interactions from the curated interaction dataset.

Relevant file:

- [medbuddy/tools/interactions.py](../medbuddy/tools/interactions.py)

### 6.7 Grounded explanation and safety gate

The safest rule in this project is that the model cannot invent drug facts. The grounding tool only returns facts that are in the static dataset.

- known drug -> safe to explain with grounded facts
- unknown drug -> must tell the patient it is not in the dataset and advise consulting a pharmacist or doctor

Relevant file:

- [medbuddy/tools/drug_info.py](../medbuddy/tools/drug_info.py)

### 6.8 Reminder scheduling

Patients can ask for daily reminders. This is a state-changing action and is guarded by a confirmation step.

Relevant file:

- [medbuddy/tools/reminders.py](../medbuddy/tools/reminders.py)

### 6.9 Adherence logging

When the patient says they took or missed a dose, the app logs that status after confirmation.

Relevant file:

- [medbuddy/tools/adherence.py](../medbuddy/tools/adherence.py)

### 6.10 Health information search

The app includes a trusted-health-search feature using MedlinePlus.

Relevant file:

- [medbuddy/api_web.py](../medbuddy/api_web.py)

### 6.11 Chat history and persistence

Messages and patient records are stored in the app database.

Relevant file:

- [medbuddy/db/models.py](../medbuddy/db/models.py)

## 7. Tool registry: agent capabilities

The agent is provided a tool registry with these functions:

- run_ocr
- extract_medications
- normalize_drug
- check_interactions
- lookup_drug_info
- schedule_reminder
- log_adherence
- register_patient
- get_my_meds

Relevant file:

- [medbuddy/tools/__init__.py](../medbuddy/tools/__init__.py)

## 8. The photo pipeline in detail

This is the most important technical feature in the project.

When the patient sends a prescription image, the system follows a fixed pipeline:

1. vision extraction of medications
2. normalization of names to generics
3. interaction checks among medications
4. drug lookup for grounding
5. template-based final response
6. optional rephrase step for warmer tone

This exact workflow is implemented in:

- [medbuddy/agent/prescription.py](../medbuddy/agent/prescription.py)

The design choice is intentional: it minimizes model calls and keeps the prescription response deterministic and grounded.

## 9. The general agent loop in detail

For normal text-based interactions, the system uses LangGraph state transitions.

The loop:

- receives the chat state
- sends conversation history to the LLM
- reads tool calls from the model
- executes matching tools
- persists tool results
- loops again until the agent is ready to reply

The logic is in:

- [medbuddy/agent/loop.py](../medbuddy/agent/loop.py)

Features include:

- tool routing
- message conversion
- checkpointing
- resume/interrupt behavior for state-changing actions

## 10. State-changing actions and confirmation gate

This project is explicit about not letting the agent mutate data without permission.

The following tools are state-changing:

- schedule_reminder
- log_adherence

The agent uses `interrupt()` and asks the patient to confirm before committing to the change.

This is a key safety design and one of the most important parts of the project.

Relevant files:

- [medbuddy/agent/loop.py](../medbuddy/agent/loop.py)
- [medbuddy/tools/reminders.py](../medbuddy/tools/reminders.py)
- [medbuddy/tools/adherence.py](../medbuddy/tools/adherence.py)

## 11. Grounding guardrails

The project makes strong statements about grounding and safety.

Hard rules in the system prompt include:

- Never state a medicine fact without tool support.
- Only report interactions returned by tool results.
- Do not say a combination is safe unless it was checked and found to be absent from the dataset.
- Confirm before changing saved state.
- Never invent medications.

Relevant file:

- [medbuddy/agent/system_prompt.py](../medbuddy/agent/system_prompt.py)

This is not just a soft preference; it is enforced structurally by the tool architecture and the fixed pipeline.

## 12. Data files and static knowledge sources

The project relies on static curated datasets rather than live medical APIs.

### Brand/generic mapping

- [data/brand_generic.csv](../data/brand_generic.csv)

### Interaction list

- [data/interactions.csv](../data/interactions.csv)

This means the app does not claim to be medically complete or always current. It is a local, curated proof-of-concept dataset.

## 13. Database model

The app uses a medicine-tracking database with several tables:

- patients
- prescriptions
- medications
- interactions
- reminders
- adherence_logs
- chat_messages

Relevant file:

- [medbuddy/db/models.py](../medbuddy/db/models.py)

## 14. Why this is hybrid, not fully agentic

This project is intentionally hybrid.

### Hybrid design

- Photo flow = fixed pipeline
- Normal chat flow = LLM agent + tools

### Fully agentic would mean

- all tasks handled by a free-form agent loop
- less deterministic safety control
- more tool calls
- more risk of unsupported claims

### Here, the project chooses

- ground-truth dataset checks
- fixed pipeline for prescription photos
- explicit confirmation gates
- structured response generation

This is the clearest way to describe the app’s design.

## 15. Demo-worthy features summary

If you need a short list for tomorrow’s demo, here it is:

- prescription upload from browser chat
- automatic medication extraction
- drug normalization and cross-checking
- interaction warnings with severity levels
- grounded medicine information with disclaimers
- reminder scheduling with confirmation
- adherence logging
- trusted health search
- patient-specific storage and chat history

## 16. What to say in the demo

A good demo explanation is:

> MedBuddy is a patient-facing medication companion. A patient uploads a prescription, the app extracts the medicines, checks for interactions, and explains them in plain language. The system is designed as a hybrid LangGraph app: photo analysis follows a fixed, deterministic pipeline, while normal chat uses a tool-using LLM. The project is deliberately proof-of-concept and safety-grounded, not a clinical product.

## 17. Quick reference files

- [README.md](../README.md)
- [medbuddy/agent/loop.py](../medbuddy/agent/loop.py)
- [medbuddy/agent/prescription.py](../medbuddy/agent/prescription.py)
- [medbuddy/agent/system_prompt.py](../medbuddy/agent/system_prompt.py)
- [medbuddy/tools/extract.py](../medbuddy/tools/extract.py)
- [medbuddy/tools/normalize.py](../medbuddy/tools/normalize.py)
- [medbuddy/tools/interactions.py](../medbuddy/tools/interactions.py)
- [medbuddy/tools/drug_info.py](../medbuddy/tools/drug_info.py)
- [medbuddy/tools/reminders.py](../medbuddy/tools/reminders.py)
- [medbuddy/tools/adherence.py](../medbuddy/tools/adherence.py)
- [medbuddy/api_web.py](../medbuddy/api_web.py)
- [frontend/src/App.tsx](../frontend/src/App.tsx)
- [medbuddy/db/models.py](../medbuddy/db/models.py)

## 18. Final takeaway

MedBuddy is a focused proof-of-concept medication assistant built around a hybrid LangGraph design. It combines a strict photo-processing pipeline with a tool-driven conversational agent, with strong grounding and safety rules baked into the system. The result is a demo-ready app that feels useful, explainable, and structured around patient safety.
