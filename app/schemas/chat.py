from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    content: Annotated[str, StringConstraints(min_length=1, max_length=4000)]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversationId: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    tenantId: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    documentIds: Annotated[list[str], Field(min_length=1, max_length=20)]
    question: Annotated[str, StringConstraints(min_length=1, max_length=8000)]
    history: Annotated[list[ChatMessage], Field(max_length=20)] = []


class Source(BaseModel):
    documentId: str
    documentName: str
    chunkId: str
    pageNumber: int | None = None
    sheetName: str | None = None
    cellRange: str | None = None
    excerpt: str


class ChatResponse(BaseModel):
    conversationId: str
    answer: str
    sources: list[Source]
