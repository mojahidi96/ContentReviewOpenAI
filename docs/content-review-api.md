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

`language` is optional (default `en`). Text is bounded by `MAX_REVIEW_CONTENT_CHARS`.

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

Common errors: `INVALID_REQUEST` (422), `UNAUTHORIZED` (401), `CONTENT_TOO_LARGE` (413), `LLM_QUOTA_EXHAUSTED` (429), `LLM_PROVIDER_UNAVAILABLE` (503), `INVALID_MODEL_OUTPUT` (502), `AI_CONCURRENCY_LIMIT` (503).

**Breaking change:** the `categories` request field and the `findings`/offset response shape were removed.
