# Troubleshooting

## Backend or frontend will not start

- Confirm the terminal is at the repository root for Python commands and in `frontend`
  for npm commands.
- Activate the project environment or use `.\.venv\Scripts\python.exe`.
- Install Python dependencies with `pip install -r requirements.txt`.
- Install frontend dependencies with `npm install` from `frontend`.
- Check that ports 8000 and 5173 are not already occupied.
- For import errors, ensure commands are run from the repository root.

## Frontend says MedBuddy is unreachable

- Verify Uvicorn is running and `http://localhost:8000/health` responds.
- Check `frontend/.env` if `VITE_API_URL` points to a different API address.
- Confirm backend `CORS_ORIGINS` includes the frontend origin (default
  `http://localhost:5173`).
- Inspect the backend terminal and `logs/medbuddy.log`.

## Prescription reply says the service is busy

That reply is used when the vision-model request fails. The actual provider error is
recorded by the backend; the friendly reply alone does not identify the cause.

1. Read the backend terminal around the upload time or inspect the latest lines in
   `logs/medbuddy.log`.
2. Check that `GEMINI_API_KEY` is configured and belongs to a project with Gemini API
   access and available quota.
3. A `429 RESOURCE_EXHAUSTED` response means the provider quota/rate limit was reached.
   Check the provider dashboard or wait until the stated reset time.
4. Stop and restart Uvicorn after changing `.env`; settings and API keys are loaded by
   the running process.
5. If an environment variable `GEMINI_API_KEY` is already set in the backend terminal,
   it can take precedence over the `.env` value. Clear it in that terminal before
   restarting if it is stale:

   ```powershell
   Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
   uvicorn medbuddy.main:app --reload --no-access-log
   ```

6. If a LiteLLM import traceback ends with `ModuleNotFoundError: No module named
   'mcp'`, install the missing package in the active project environment and restart:

   ```powershell
   python -m pip install mcp
   ```

   If this recurs in a clean environment, verify compatible LiteLLM dependencies and
   update the project's dependency declarations rather than relying on a one-off
   environment install.

Do not paste API keys or full environment files into logs, screenshots, or support
messages.

## Chat responds with a generic fallback

- Inspect the traceback above `step=agent_turn_failed` in the backend logs.
- Verify the configured `AGENT_MODEL` supports tool calling and that the provider key
  has quota.
- Check whether a paused reminder/adherence confirmation is waiting for a YES or NO
  reply.
- Keep the API process running while a background turn is executing.

## Upload is rejected

- Use JPEG, PNG, WebP, or PDF.
- Make sure the actual file content matches its extension; the backend checks file
  signatures.
- Check the configured size limit (`MAX_UPLOAD_MB`; default 10).
- For a PDF, use a valid non-empty document. Only the first three pages are processed.

## Prescription appears unreadable or medicines are missing

- Use a sharp, well-lit synthetic/anonymized image with the entire prescription visible.
- Verify the relevant medicine names and fields manually against the original.
- The vision model may omit unclear text; the app is not a substitute for professional
  verification.

## A drug or interaction is not found

- The local CSVs are finite curated datasets. Check exact generic ingredient names,
  combination products, and spelling.
- An unmatched drug is deliberately not described from model knowledge.
- Absence of an interaction entry means only “not found in this dataset,” not “safe.”
- Restart the backend after modifying a CSV because the loaded datasets are cached for
  the process.

## Reminder does not arrive

- Reminder delivery occurs during browser message polling; keep the browser chat open.
- The reminder stores the next occurrence for its requested time and uses
  `TZ_OFFSET_MINUTES` (330 minutes by default).
- This project does not run a persistent scheduler and does not create daily recurring
  reminders.

## Chat timestamps appear wrong

The API returns UTC timestamps with a `Z` suffix and the browser displays them in the
computer's local timezone. Verify the computer's date/time/timezone settings, restart the
backend if running old code, and hard-refresh the browser (`Ctrl+F5`).

## Bold text shows asterisks

The frontend formatter handles common asterisk markup. Hard-refresh the browser after a
frontend update. If stars still appear, inspect the exact model reply and adjust the
formatter for that output shape.

## Run focused tests

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_web_api.py
.\.venv\Scripts\python.exe -m pytest tests\test_normalize.py tests\test_interactions.py tests\test_prescription_pipeline.py
```
