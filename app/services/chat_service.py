from app.config import Settings
from app.errors import ServiceError
from app.llm.base import LLMProvider
from app.llm.prompts import document_answer_prompt
from app.schemas.chat import ChatRequest, ChatResponse, Source
from app.schemas.content_review import ModelAnswer
from app.services.document_repository import DocumentRepository
from app.embeddings.base import EmbeddingProvider
from app.vector_store.base import VectorStore


class ChatService:
    def __init__(
        self,
        settings: Settings,
        provider: LLMProvider,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
        repository: DocumentRepository,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._embeddings = embeddings
        self._vector_store = vector_store
        self._repository = repository

    def answer(self, request: ChatRequest) -> ChatResponse:
        for document_id in request.documentIds:
            record = self._repository.get(document_id, request.tenantId)
            if record is None:
                raise ServiceError("DOCUMENT_NOT_FOUND", "One or more documents were not found.", 404)
            if record.status != "ready":
                raise ServiceError("DOCUMENT_NOT_READY", "One or more documents are not ready.", 409)
        history = []
        for message in request.history:
            if message.role not in ("user", "assistant"):
                raise ServiceError("INVALID_HISTORY", "Chat history contains an unsupported role.", 422)
            history.append((message.role, message.content))
        query_vector = self._embeddings.embed_query(request.question)
        matches = self._vector_store.query(
            query_vector, request.documentIds, request.tenantId, self._settings.retrieval_count
        )
        matches = [
            item for item in matches
            if 1 - float(item["distance"]) >= self._settings.similarity_threshold
        ]
        prompt_chunks = [
            {"chunk_id": item["chunk_id"], "text": item["text"]} for item in matches
        ]
        result, _, _ = self._provider.generate_structured(
            document_answer_prompt(request.question, history, prompt_chunks), ModelAnswer
        )
        sources = [
            Source(
                documentId=item["metadata"]["document_id"],
                documentName=item["metadata"]["document_name"],
                chunkId=item["chunk_id"],
                pageNumber=item["metadata"].get("page_number"),
                sheetName=item["metadata"].get("sheet_name"),
                cellRange=item["metadata"].get("cell_range"),
                excerpt=item["text"][:500],
            )
            for item in matches
        ]
        answer = result.answer
        if not matches or result.insufficientEvidence:
            answer = answer or "The available documents do not contain enough information to answer this question."
        return ChatResponse(conversationId=request.conversationId, answer=answer, sources=sources)
