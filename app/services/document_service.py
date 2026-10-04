import logging
import os
import re
from pathlib import PurePath
from uuid import uuid4

from app.config import Settings
from app.document_loaders.base import ExtractionError
from app.document_loaders.dispatch import ALLOWED_TYPES, extract_document, validate_signature
from app.embeddings.base import EmbeddingProvider
from app.errors import ProviderUnavailable, ServiceError
from app.schemas.document import DocumentRecord, DocumentUploadResponse
from app.services.chunking import split_documents
from app.services.document_repository import DocumentRepository
from app.vector_store.base import VectorStore

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(
        self,
        settings: Settings,
        repository: DocumentRepository,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._embeddings = embeddings
        self._vector_store = vector_store

    def ingest(
        self, filename: str, media_type: str, data: bytes, tenant_id: str
    ) -> DocumentUploadResponse:
        extension = PurePath(filename or "").suffix.lower()
        if extension not in ALLOWED_TYPES or media_type not in ALLOWED_TYPES[extension]:
            raise ServiceError("UNSUPPORTED_FILE", "Only valid PDF, DOCX, and XLSX files are supported.", 415)
        if not data or len(data) > self._settings.max_upload_bytes:
            raise ServiceError("FILE_TOO_LARGE", "File is empty or exceeds the configured upload limit.", 413)
        validate_signature(extension, data)
        safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", os.path.basename(filename))[:255] or "document"
        document_id = f"doc_{uuid4().hex}"
        record = self._repository.create(document_id, tenant_id, safe_name, media_type, len(data))
        self._repository.update_status(document_id, tenant_id, "processing")
        try:
            extracted = extract_document(extension, data, self._settings.max_document_pages)
            total_chars = sum(len(document.text) for document in extracted)
            if total_chars > self._settings.max_extracted_chars:
                raise ExtractionError("DOCUMENT_TOO_LARGE", "Extracted content exceeds the configured limit.")
            chunks = split_documents(extracted, self._settings.max_chunk_size, self._settings.chunk_overlap)
            if not chunks:
                raise ExtractionError("EMPTY_DOCUMENT", "Document contains no usable text.")
            vectors = self._embeddings.embed_documents([chunk.text for chunk in chunks])
            if len(vectors) != len(chunks):
                raise ProviderUnavailable()
            ids = [f"{document_id}_{index:06d}" for index in range(len(chunks))]
            metadatas = [
                {
                    **chunk.metadata,
                    "document_id": document_id,
                    "document_name": safe_name,
                    "tenant_id": tenant_id,
                }
                for chunk in chunks
            ]
            self._vector_store.add_chunks(ids, [chunk.text for chunk in chunks], vectors, metadatas)
            self._repository.update_status(document_id, tenant_id, "ready", len(chunks))
            return DocumentUploadResponse(
                documentId=document_id,
                status="ready",
                documentName=safe_name,
                mediaType=media_type,
                sizeBytes=len(data),
                chunkCount=len(chunks),
            )
        except Exception as exc:
            code = exc.code if isinstance(exc, ExtractionError) else (
                exc.code if isinstance(exc, ServiceError) else "INGESTION_FAILED"
            )
            self._repository.update_status(document_id, tenant_id, "failed", error_code=code)
            raise

    def get(self, document_id: str, tenant_id: str) -> DocumentRecord:
        record = self._repository.get(document_id, tenant_id)
        if not record:
            raise ServiceError("DOCUMENT_NOT_FOUND", "Document was not found.", 404)
        return record

    def delete(self, document_id: str, tenant_id: str) -> None:
        record = self._repository.get(document_id, tenant_id)
        if not record:
            raise ServiceError("DOCUMENT_NOT_FOUND", "Document was not found.", 404)
        self._vector_store.delete_document(document_id, tenant_id)
        self._repository.delete(document_id, tenant_id)
