# Architecture and trust boundaries

`ContentReviewUI` calls only the Node.js `ContentReviewService`. Node.js authenticates callers, authorizes documents and tenants, and calls this service through a private HTTP path. This repository has no browser authentication, MongoDB app-user model, CORS policy, or SSE implementation.

FastAPI routes validate contracts and delegate to separate content-review, ingestion, and chat services. LLM and embedding protocols isolate Gemini SDK use. `DocumentRepository` stores tenant-scoped status metadata in SQLite. `VectorStore` abstracts Chroma. Upload bytes are processed in memory and are not retained as original files.

All internal API endpoints require the configured bearer token; live and readiness checks are intentionally unauthenticated. Document upload and chat require tenant scope, and metadata lookups/deletes require the same scope. Node.js must derive this scope only after authorization. Vector metadata filters tenant and selected document IDs; IDs are not authorization credentials by themselves.

Content review output is validated against selected categories and exact UTF-16 source ranges. Document content/history are untrusted data in prompts. No tools or code execution are available to model calls. Errors use a stable `{error:{code,message,requestId}}` envelope without internal exception detail.

Local Chroma + SQLite are single-instance development stores, not a production authorization boundary or distributed database. Replace through the interfaces for managed vector storage and durable metadata as needed. The stores are not transactionally coupled; production should add reconciliation and tested backup/retention operations.
