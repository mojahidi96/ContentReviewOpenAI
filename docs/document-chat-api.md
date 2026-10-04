# Document ingestion and chat contract

All routes require the internal bearer token. `tenantId` must be a trusted scope established by Node.js authorization; IDs alone never authorize access.

## Upload

`POST /internal/v1/documents` accepts multipart form data:

* `file`: `.pdf`, `.docx`, or `.xlsx`, matching MIME type and file signature.
* `tenantId`: required tenant scope.

Small files are synchronously extracted, chunked, embedded, and indexed. A 201 response with `status: ready` means chunks and vectors have been written. Failures store `status: failed` and expose a safe `errorCode` through the status route when the record was created. Scanned PDFs return `OCR_REQUIRED`.

## Status and deletion

`GET /internal/v1/documents/{document_id}?tenantId=...` returns safe metadata/status. `DELETE /internal/v1/documents/{document_id}?tenantId=...` deletes the scoped vector records and metadata. Missing or foreign-tenant documents both return `DOCUMENT_NOT_FOUND`.

## Chat

`POST /internal/v1/chat` accepts `conversationId`, `tenantId`, `documentIds`, `question`, and optional bounded `history` (`user`/`assistant` roles only). The service checks readiness and tenant ownership for every requested document, retrieves at most `RETRIEVAL_COUNT` chunks, applies the configured similarity threshold, and returns a grounded answer and traceable source metadata. Source excerpts are taken from the exact retrieved text; PDF page and spreadsheet sheet/cell range are included when present. If no evidence meets the threshold, the answer states that available documents are insufficient and sources is empty.

Errors include `DOCUMENT_NOT_FOUND` (404), `DOCUMENT_NOT_READY` (409), `UNSUPPORTED_FILE` (415), `FILE_TOO_LARGE` (413), `CORRUPT_DOCUMENT` (422), `OCR_REQUIRED` (422), `LLM_QUOTA_EXHAUSTED` (429), and provider/vector-store unavailable errors (503).
