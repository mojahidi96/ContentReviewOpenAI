# Content review contract

## `POST /internal/v1/content-reviews`

Headers: `Authorization: Bearer <INTERNAL_SERVICE_TOKEN>` and optional `X-Request-ID`.

Example:

```json
{
  "requestId": "review_123",
  "content": "The report have several mistake.",
  "categories": ["grammar", "spelling"],
  "language": "en"
}
```

Only `grammar`, `spelling`, and `profanity` are accepted. Text is bounded by `MAX_REVIEW_CONTENT_CHARS`. The response contains `requestId`, `findings`, configured `model`, and usage values. `inputTokens`/`outputTokens` are null when the SDK does not reliably provide them.

Finding offsets are zero-based UTF-16 code units with an exclusive end, matching JavaScript string indexing. The service rejects invalid ranges, mismatched `originalText`, unrequested categories, overlapping spans, and no-op suggestions. Invalid individual findings are omitted rather than passed through. `findingId` is generated server-side. This initial API returns a complete result, not streaming output; Node.js owns review persistence and browser SSE.

Common errors: `INVALID_REQUEST` (422), `UNAUTHORIZED` (401), `CONTENT_TOO_LARGE` (413), `LLM_QUOTA_EXHAUSTED` (429), `LLM_PROVIDER_UNAVAILABLE` (503), `INVALID_MODEL_OUTPUT` (502), `AI_CONCURRENCY_LIMIT` (503). Validation details identify fields without reflecting submitted values.
