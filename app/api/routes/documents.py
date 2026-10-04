from threading import BoundedSemaphore

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.dependencies import get_document_service, get_llm_limiter, require_internal_auth
from app.errors import ServiceError
from app.schemas.document import DocumentRecord, DocumentUploadResponse
from app.services.document_service import DocumentService

router = APIRouter(
    prefix="/internal/v1/documents",
    tags=["documents"],
    dependencies=[Depends(require_internal_auth)],
)


@router.post("", response_model=DocumentUploadResponse, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Form(alias="tenantId", min_length=1, max_length=128),
    service: DocumentService = Depends(get_document_service),
    limiter: BoundedSemaphore = Depends(get_llm_limiter),
) -> DocumentUploadResponse:
    from app.config import get_settings

    max_bytes = get_settings().max_upload_bytes
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ServiceError("FILE_TOO_LARGE", "File exceeds the configured upload limit.", 413)
    if not limiter.acquire(blocking=False):
        raise ServiceError("AI_CONCURRENCY_LIMIT", "The AI service is busy; retry shortly.", 503)
    try:
        return service.ingest(file.filename or "", file.content_type or "", data, tenant_id)
    finally:
        limiter.release()


@router.get("/{document_id}", response_model=DocumentRecord)
def get_document(
    document_id: str,
    tenant_id: str = Query(alias="tenantId", min_length=1, max_length=128),
    service: DocumentService = Depends(get_document_service),
) -> DocumentRecord:
    return service.get(document_id, tenant_id)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    tenant_id: str = Query(alias="tenantId", min_length=1, max_length=128),
    service: DocumentService = Depends(get_document_service),
) -> None:
    service.delete(document_id, tenant_id)
