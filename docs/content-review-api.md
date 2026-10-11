# Content review contract

## `POST /internal/v1/content-reviews`

Headers: `Authorization: Bearer <INTERNAL_SERVICE_TOKEN>` and optional `X-Request-ID`.

Request:

```json
{
  "requestId": "review_123",
  "content": "Please recieve the document and add it to the whitelist.",
  "language": "en"
}
```

`language` is optional (default `en`). `model` is optional: one of the ids returned by `GET /internal/v1/content-reviews/models` (default model if omitted); anything else is `422 MODEL_NOT_ALLOWED`. The allowed list is `ALLOWED_GEMINI_MODELS` plus `GEMINI_MODEL`. Text is bounded by `MAX_REVIEW_CONTENT_CHARS`.

Response:

```json
{
  "requestId": "review_123",
  "issues": [
    {
      "id": "issue-3f9a1c2b7d10",
      "issueType": "spelling",
      "severity": "low",
      "original": "recieve",
      "improved": "receive",
      "suggestion": "Correct the spelling mistake.",
      "location": { "prefix": "Please ", "suffix": " the document and add it" }
    }
  ],
  "model": "gemini-...",
  "usage": { "inputTokens": null, "outputTokens": null }
}
```

`issueType` is one of `spelling`, `grammar`, `typo`, `punctuation`, `clarity`, `slang`, `vulgarity`, `deprecated_term`, `inappropriate_language`. `severity` is `low`, `medium` or `high` (defaults to `medium` if the model omits it). `id` is generated server-side. Issues are ordered by position in the content.

The LLM is prompted with the full review rubric and returns issues as JSON. The service then validates them: an issue is dropped if `original` does not occur in the content, if `improved` equals `original`, or if `original` occurs several times and `prefix`/`suffix` do not identify one occurrence. Invalid individual issues are omitted rather than passed through. `inputTokens`/`outputTokens` are null when the SDK does not report them. The API returns a complete result, not streaming output.

Common errors: `INVALID_REQUEST` (422), `MODEL_NOT_ALLOWED` (422), `UNAUTHORIZED` (401), `CONTENT_TOO_LARGE` (413), `LLM_QUOTA_EXHAUSTED` (429), `LLM_PROVIDER_UNAVAILABLE` (503), `INVALID_MODEL_OUTPUT` (502), `AI_CONCURRENCY_LIMIT` (503).

`GET /internal/v1/content-reviews/models` (same auth) returns `{ "defaultModel": "...", "models": ["..."] }`.

When the provider quota is exhausted the response is `429 LLM_QUOTA_EXHAUSTED` with a `Retry-After` header, a ready-to-display `message` and structured details:

```json
{
  "error": {
    "code": "LLM_QUOTA_EXHAUSTED",
    "message": "The daily quota for model gemini-3.6-flash is exhausted. It resets in about 1h 58m. Try again later or choose a different model.",
    "requestId": null,
    "details": { "model": "gemini-3.6-flash", "quotaScope": "daily", "retryAfterSeconds": 7105, "resetAt": "2026-10-11T05:30:00+00:00" }
  }
}
```

`quotaScope` is `daily`, `minute` or `unknown`. 429s are not retried by this service.

**Deprecated terms.** Company-specific deprecated terms live in `resources/deprecated_terms.xlsx` (first sheet; columns `Deprecated Term` and `Replacement Term`, one pair per row). They are matched deterministically (case-insensitive, whole words, optional plural `s`, multi-word terms, longest first), returned as `deprecated_term` issues with the replacement in `improved`, and they replace any overlapping issue from the model. Edit the file and save; changes are picked up on the next review without a restart. Set `DEPRECATED_TERMS_FILE` to use another path.

**Acronyms.** The model flags the first occurrence of each undefined acronym or abbreviation (ASAP, FOMO, ...) as a `clarity` issue whose `improved` spells it out, e.g. `as soon as possible (ASAP)`.

**Breaking change:** the `categories` request field and the `findings`/offset response shape were removed.
