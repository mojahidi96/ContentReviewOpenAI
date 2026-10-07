# ContentReviewOpenAI

Private Python AI service for structured content review and tenant-scoped document RAG. It is a separate repository: it contains neither the Angular UI nor the Node.js application service. Node.js is the trusted caller and owns user authentication, authorization decisions, review persistence, job orchestration, and browser-facing SSE.

## Architecture

FastAPI exposes authenticated internal APIs. Business services depend on provider protocols, an embedding protocol, a vector-store protocol, and a small SQLite document metadata repository. Gemini is the initial provider; Chroma is the local vector store. See [docs/architecture.md](docs/architecture.md), [docs/content-review-api.md](docs/content-review-api.md), and [docs/document-chat-api.md](docs/document-chat-api.md).

## Local setup

Requires Python 3.12+, a Google AI Studio API key for real inference, and Docker for the container option.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
# Set GOOGLE_API_KEY and replace INTERNAL_SERVICE_TOKEN with a random secret of 32+ characters.
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run tests and quality checks:

```sh
pytest
ruff check .
ruff format --check .
```

The test suite uses deterministic fakes and synthetic inputs; it makes no provider or network calls. Real requests use the Google Gen AI SDK. Startup validates credentials and limits. `APP_ENV=test` permits an absent Google key for test-only application construction; endpoints that use Gemini still require an injected or configured provider.

## Configuration

See [.env.example](.env.example). Never commit `.env`, API keys, service tokens, or uploaded source files. Do not log document contents or prompts. The selected Gemini model names are configuration, not silent fallbacks. Model availability, quotas, rate limits, context windows, embedding limits, and pricing vary by account, region, and time; consult current Google AI Studio / Gemini API documentation and billing before deployment. Free-tier access is not unlimited, and changing provider, model, or usage tier can change cost.

The implementation requests JSON-schema structured output using the configured Gemini model. The SDK exposes token counts only where present; absent counts remain null. Retry behavior is bounded and rate-limit responses are not retried. `gemini-embedding-001` must be available to the project and account.

## API overview

Internal routes require `Authorization: Bearer <INTERNAL_SERVICE_TOKEN>`. Health routes are unauthenticated. No CORS origins are enabled.

* `POST /internal/v1/content-reviews` — AI review of spelling, grammar, typos, punctuation, clarity, slang, vulgarity, and deprecated or inappropriate terms.
* `POST /internal/v1/documents` — multipart `file` and `tenantId`; synchronous extraction/indexing.
* `GET /internal/v1/documents/{document_id}?tenantId=...`
* `DELETE /internal/v1/documents/{document_id}?tenantId=...`
* `POST /internal/v1/chat` — question and ready document IDs scoped to `tenantId`.
* `GET /health/live`, `GET /health/ready`

Request and response details are in the API contract documents. Review issues are located by `prefix`/`suffix` context rather than offsets, and are discarded unless their exact `original` text exists in the submitted content.

## File processing and persistence

Supported extensions are PDF, DOCX, and XLSX; legacy `.doc`/`.xls` are rejected. PDF page numbers, DOCX paragraphs/tables, and spreadsheet sheet names/headers/row ranges are retained as chunk metadata. Scanned PDFs return `OCR_REQUIRED`; OCR is intentionally not included. Excel formulas are not executed; cached values are read, and macro-enabled formats are unsupported.

Uploads are processed synchronously and bounded by upload, page, and extracted-text limits. SQLite stores statuses and tenant ownership; Chroma stores local vectors and metadata. A successful upload is `ready` only after extraction, embeddings, and vector insertion complete. Failures retain a `failed` status and safe error code for inspection/re-upload. Deletion removes vectors and metadata.

Local Chroma persistence is suitable only for development or single-instance evaluation: it is not a managed, replicated, encrypted, tenant-security boundary or backup strategy. SQLite and Chroma writes are separate operations; production should use durable managed storage and operational reconciliation. Tenant IDs must be established by Node.js after authorization and forwarded as trusted scope; possession of a document ID is not authorization.

## Docker

```sh
docker compose up --build
```

The compose setup binds the API to loopback for local use. Persistent Chroma and SQLite data are under `./data`.

## Production notes and limitations

Place this service on a private network and allow inbound traffic only from the Node.js service. Use a secret manager, rotate the service token, use TLS at the private ingress, set strict network egress, configure provider quotas/budget alerts, and monitor 429/5xx rates without logging content. Implement durable backups, retention/deletion policies, storage encryption, and tenant-scope integration tests. This initial implementation is single-process and synchronous for ingestion; scale-out, OCR, malware scanning, async jobs, richer document lifecycle recovery, and distributed rate limiting require production-specific infrastructure. Chroma and SQLite are replaceable behind interfaces.
