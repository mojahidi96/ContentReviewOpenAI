# Prompt: model selection and quota errors in the Node.js service

Copy everything below the line into the Node.js repo's coding assistant. (The service already
integrates content-review contract v2; this prompt covers only the new changes.)

---

The private Python AI service changed. Update this Node.js `ContentReviewService` to match, keeping
existing conventions (zod schemas, `LlmError` classes, Mongoose models, vitest). Do not change the
Python service.

## 1. New: choose the model per review

- `GET {AI_SERVICE_BASE_URL}/internal/v1/content-reviews/models` (same Bearer auth) →
  `{ "defaultModel": "gemini-3.6-flash", "models": ["gemini-3.6-flash", "gemini-3.8-flash"] }`.
- `POST /internal/v1/content-reviews` accepts an optional `"model": "<id>"`. Omit it for the
  default. A model not in the list → `422 MODEL_NOT_ALLOWED`. The response's `model` is the model
  actually used. Still send no other fields.

Build:
1. `PythonLlmClient.listModels()` (HTTP + mock). Send `model` from `reviewContent` when set.
2. Public `GET /api/v1/reviews/models` (auth, registered before `/:reviewId`) returning the list,
   cached ~5 min. If Python is unreachable respond `503` so the UI can fall back to the default.
3. `POST /api/v1/reviews` accepts optional `model`; reject values not in the list with
   `400 VALIDATION_FAILED` (`details[].path = "model"`). Persist it on the review (`model`, null =
   default) and pass it to the Python call in the processor. Expose `model` in review DTOs.

## 2. New: quota (429) errors carry a reason and a reset time

Python's `429 LLM_QUOTA_EXHAUSTED` now looks like:

```json
{ "error": { "code": "LLM_QUOTA_EXHAUSTED",
  "message": "The daily quota for model gemini-3.6-flash is exhausted. It resets in about 1h 58m. Try again later or choose a different model.",
  "details": { "model": "gemini-3.6-flash", "quotaScope": "daily", "retryAfterSeconds": 7105, "resetAt": "2026-10-11T05:30:00+00:00" } } }
```
plus a `Retry-After` header. `quotaScope` is `daily | minute | unknown`; every `details` field is
optional, and `message` is safe to show the author.

Build:
1. Parse `details` and `message` in the error body schema; keep them on `LlmRateLimitedError`.
   Use the Python `message` as its `publicMessage`.
2. Retry only short waits: if `retryAfterSeconds` is unknown or ≤ 300, keep the current backoff
   (honoring Retry-After). If longer (a daily quota), mark it non-retryable so the review fails
   immediately instead of burning attempts that cannot succeed.
3. When a review fails, persist user-safe `errorDetails` (`model`, `quotaScope`,
   `retryAfterSeconds`, `resetAt`) next to `errorCode`/`errorMessage`, and include `errorDetails`
   in the `review.failed` SSE event and in the review/summary DTOs.
4. Never log content or issue text; the token stays secret.

## 3. Tests (mock the HTTP layer; no real LLM calls)

Model sent in the body and omitted when unset; `listModels`; 429 daily → non-retryable with
details and message; 429 minute → retryable; unknown model → 400 and nothing stored; model reaches
the client from the processor; failed review stores `errorDetails` and emits it over SSE.

## 4. Docs

Update `docs/api-contract.md` (new endpoint, `model`, `errorDetails`, quota failures) and
`docs/python-service-contract.md`.
