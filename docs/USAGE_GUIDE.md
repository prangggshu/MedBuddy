# User and Demo Usage Guide

MedBuddy is a browser-based proof-of-concept, not a clinical tool. For a demo, use
synthetic or anonymized information only.

## Start the demo

Follow the [setup guide](./SETUP_GUIDE.md), start the backend and frontend, then open
the Vite URL (usually `http://localhost:5173`).

## Sign in

1. Enter a demo phone number with 10–15 digits.
2. Select **Continue**.
3. The browser remembers the normalized number in local storage until logout.

This is not a verified login. Anyone able to use the browser/API with that number may
be treated as the same demo patient.

## Chat with MedBuddy

Type a message and press Enter or select the send button. Messages are stored by the
backend. The browser polls for new messages and shows an in-progress indicator while
the agent handles a turn.

The text agent may ask follow-up questions or use registered tools. It can support
profile registration, medication lookup, interaction queries, reminder proposals, and
adherence responses. Medication-related replies are constrained by the system prompt and
tool results; the datasets do not provide comprehensive clinical facts.

## Upload a prescription

1. Select the attachment button or drag a file into the chat.
2. Choose a JPEG, PNG, WebP, or PDF up to the configured upload size (10 MB by default).
3. Send the upload and wait for the assistant reply.

For a photo, the system extracts medicine name, dosage, frequency, and duration, tries
to normalize names, checks recognized ingredients against the local interaction data,
and returns a template response. A PDF is processed only for its first three pages.
Unknown medicines are flagged as outside the local dataset.

Check the result against the synthetic source prescription during a demo. Do not make
medication decisions from the extraction or interaction output.

## Confirm or cancel state changes

When the agent proposes to schedule a reminder or log an adherence response, it displays
a confirmation prompt. Reply **Yes** to allow the pending action or **No** to cancel it.
The application code gates the write; it should not be committed before confirmation.

## Reminder behavior

The agent can propose one or more local `HH:MM` times. After confirmation, the next
occurrence is stored using the configured fixed UTC offset (IST by default). A due
reminder appears when the browser polls `GET /api/messages`.

This prototype does not provide a continuously running scheduler, recurring daily
reminders, or guaranteed delivery while the browser is closed.

## Log adherence

The supported responses are **Taken** and **Missed**. The graph asks for confirmation
before saving the adherence log. **Snooze is not implemented.**

## Search trusted health information

Select **Search trusted health info**, enter at least two characters, and submit. The
results are retrieved from MedlinePlus and link to its pages. This search is separate
from the curated medication and interaction data and does not provide personalized
medical advice.

## Suggested demonstration sequence

1. Explain the proof-of-concept disclaimer and hybrid architecture.
2. Log in using a demo phone number.
3. Upload a prepared synthetic prescription image with clearly legible text.
4. Show extracted fields, recognized/unrecognized names, and any dataset interaction
   findings.
5. Ask for a reminder, inspect the proposed action, then demonstrate YES and/or NO.
6. Demonstrate a `taken` or `missed` response with its confirmation.
7. Open MedlinePlus health search and show a result link.
8. Close by explaining the static-data, extraction, reminder, and clinical limitations.

Do not promise an interaction warning for a pair that is absent from the dataset. A
missing match is not proof of safety.
