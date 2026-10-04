from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated


DocumentStatus = Literal["uploaded", "processing", "ready", "failed"]


class DocumentRecord(BaseModel):
    documentId: str
    tenantId: str
    documentName: str
    status: DocumentStatus
    mediaType: str
    sizeBytes: int
    chunkCount: int = 0
    errorCode: str | None = None
    createdAt: str


class DocumentUploadResponse(BaseModel):
    documentId: str
    status: DocumentStatus
    documentName: str
    mediaType: str
    sizeBytes: int
    chunkCount: int


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenantId: Annotated[str, StringConstraints(min_length=1, max_length=128)]
