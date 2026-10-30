# Backend Documentation and API Reference

## Backend overview

The backend is a FastAPI application served with Uvicorn. It provides web-chat endpoints,
validates and stores uploads, runs agent/prescription processing in a background task,
persists application records with SQLAlchemy, and reads the curated CSV datasets.

The backend is intended for local demonstration. The phone number identifies a patient
but does not authenticate the caller. Do not expose this service to the public internet
or use real patient information.

## Modules

| Module | Responsibility |
|---|---|
| `medbuddy/main.py` | Create FastAPI app, configure CORS, initialize database, expose `/health` |
| `medbuddy/api_web.py` | Login, messages, typing state, media, health search, and due-reminder dispatch |
| `medbuddy/agent/loop.py` | LangGraph entry routing, text-agent/tool loop, confirmation interrupts, checkpoints |
| `medbuddy/agent/prescription.py` | Fixed prescription image pipeline and grounded template reply |
| `medbuddy/agent/registry.py` | Map tool names to tool implementations |
| `medbuddy/tools/` | OCR, extraction, normalization, interaction lookup, patient, reminders, adherence |
| `medbuddy/llm/client.py` | Role-specific LiteLLM requests and configured fallbacks/retries |
| `medbuddy/datasets/loaders.py` | Load CSVs and expose normalized names and pair lookups |
| `medbuddy/db/` | SQLAlchemy engine, models, and repository helpers |
| `medbuddy/media.py` | Upload signature checks, safe display names, PDF page rendering |
| `medbuddy/health_search.py` | MedlinePlus health-topic search and in-memory result cache |

## Database

The app creates tables at startup using SQLAlchemy metadata. SQLite is the default.

| Table | Stored information |
|---|---|
| `patients` | Phone identity, optional name and age |
| `prescriptions` | Patient, optional raw extracted text/image reference, creation time |
| `medications` | Extracted name, generic, dosage, frequency, duration, match status |
| `interactions` | Interaction audit model; the current prescription path does not persist each finding here |
| `reminders` | Patient, next scheduled UTC time, and status |
| `adherence_logs` | Patient, response (`taken` or `missed`), and time |
| `chat_messages` | Inbound/outbound text, media metadata, timestamp, and status |

LangGraph state is checkpointed separately from the application database. The default
checkpoint path is `./checkpoints.db`.

## Data loading

`brand_generic.csv` and `interactions.csv` are loaded into memory and cached for the
process. Restart the backend after changing either file to ensure it reloads them.

Interaction lookup uses unordered pairs of lowercased drug names. It returns only
matching rows. A missing pair means that the dataset has no entry; it does not mean the
combination is safe.

## HTTP API

The browser frontend uses the following endpoints. Unless stated otherwise, successful
responses use HTTP 200.

### `GET /health`

Health check.

Example response:

```json
{
  "status": "ok",
  "service": "medbuddy",
  "note": "proof-of-concept, not for clinical use"
}
```

### `POST /api/login`

Creates or retrieves the patient row for a phone number. This is identity initialization,
not password- or OTP-based authentication.

Request:

```json
{"phone": "+91 98765 43210"}
```

Response:

```json
{"phone": "+919876543210", "is_new": true}
```

The backend strips non-digits and requires 10–15 digits. Invalid numbers return 422.

### `POST /api/messages`

Accepts `multipart/form-data`:

| Field | Required | Meaning |
|---|---|---|
| `phone` | Yes | Patient phone identity |
| `text` | No | Message text |
| `file` | No | JPEG, PNG, WebP, or PDF attachment |

At least one of text or file must be supplied. The response is the saved inbound message;
agent processing is queued as a FastAPI background task and its reply is retrieved by
polling `GET /api/messages`.

Common validation responses:

- 422 — neither message nor usable PDF input supplied, or malformed request.
- 413 — upload exceeds `MAX_UPLOAD_MB`.
- 415 — unsupported media or content signature does not match the declared format.

PDF files are rendered as PNG images for up to the first three pages. The API sends a
chat notice if more pages were skipped.

### `GET /api/messages`

Query parameters:

| Parameter | Required | Default | Meaning |
|---|---|---|---|
| `phone` | Yes | — | Patient phone identity |
| `after_id` | No | `0` | Return messages whose database ID is greater than this value |

Returns an array of chat-message objects ordered by ID. `created_at` is serialized as
UTC with a `Z` suffix; the browser formats it in the local system timezone.

The request also checks for due reminders for this patient, marks them sent, and adds
reminder chat messages. The lightweight dispatcher runs when the browser polls; it is
not an independent background scheduler.

Message object fields:

```json
{
  "id": 12,
  "phone": "+919876543210",
  "direction": "out",
  "text": "Example reply",
  "media_url": null,
  "media_type": null,
  "media_name": null,
  "media_size": null,
  "created_at": "2026-10-30T06:00:00Z",
  "status": "sent"
}
```

### `GET /api/typing`

Query parameter: `phone` (required).

Returns the current in-memory processing indicator:

```json
{"typing": true}
```

This is process-local state, not a durable job-status system.

### `GET /api/health-search`

Query parameter: `q`, between 2 and 160 characters.

Returns up to five MedlinePlus health-topic results:

```json
{
  "query": "asthma",
  "source": "MedlinePlus",
  "results": [
    {"title": "Example topic", "summary": "Summary...", "url": "https://medlineplus.gov/..."}
  ]
}
```

Returns 422 for an invalid query and 503 if MedlinePlus cannot be reached. Results are
general health information, not individualized medical advice.

### `GET /api/media/{message_id}`

Returns the original uploaded media for an inbound chat-message ID when the stored file
still exists under the configured upload directory. Returns 404 otherwise.

## File upload and media security

Accepted formats are JPEG, PNG, WebP, and PDF. The backend checks both MIME/signature
and size, sanitizes the display filename, stores uploads below `data/uploads/`, and
restricts media retrieval to paths under that directory. The configured default size
limit is 10 MB.

## Reminder and adherence behavior

- Times are supplied as `HH:MM` in the configured fixed UTC offset (default UTC+05:30).
- The tool stores the next matching occurrence in UTC.
- A graph interrupt asks the patient to confirm before writing.
- Message polling dispatches due reminders.
- The current implementation does not repeat reminders every day automatically.
- Adherence logs accept `taken` and `missed`; snooze is not supported.

## Logging and tests

Application logs are written to the backend terminal and rotating `logs/medbuddy.log`.
Run the focused API tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py
```

Run all tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest
```
