from functools import lru_cache
from threading import BoundedSemaphore

from fastapi import Depends, Header, Request

from app.config import Settings, get_settings
from app.embeddings.gemini_embeddings import GeminiEmbeddings
from app.llm.gemini_provider import GeminiProvider
from app.services.chat_service import ChatService
from app.services.content_review_service import ContentReviewService
from app.services.deprecated_terms import DeprecatedTerms
from app.services.document_repository import DocumentRepository
from app.services.document_service import DocumentService
from app.vector_store.chroma_store import ChromaStore


@lru_cache
def get_provider() -> GeminiProvider:
    return GeminiProvider(get_settings())


@lru_cache
def get_embeddings() -> GeminiEmbeddings:
    return GeminiEmbeddings(get_settings())


@lru_cache
def get_vector_store() -> ChromaStore:
    settings = get_settings()
    return ChromaStore(settings.vector_store_path)


@lru_cache
def get_repository() -> DocumentRepository:
    return DocumentRepository(get_settings().metadata_db_path)


@lru_cache
def get_deprecated_terms() -> DeprecatedTerms:
    return DeprecatedTerms(get_settings().deprecated_terms_file)


def get_review_service(request: Request) -> ContentReviewService:
    settings = get_settings()
    return ContentReviewService(
        deprecated_terms=get_deprecated_terms(),
        provider=get_provider(),
        max_chars=settings.max_review_content_chars,
        allowed_models=settings.selectable_models,
    )


def get_document_service() -> DocumentService:
    return DocumentService(get_settings(), get_repository(), get_embeddings(), get_vector_store())


def get_chat_service() -> ChatService:
    return ChatService(
        get_settings(), get_provider(), get_embeddings(), get_vector_store(), get_repository()
    )


def require_internal_auth(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    import hmac

    expected = f"Bearer {settings.internal_service_token.get_secret_value()}"
    if authorization is None or not hmac.compare_digest(authorization, expected):
        from app.errors import ServiceError

        raise ServiceError("UNAUTHORIZED", "Valid service credentials are required.", 401)


def get_llm_limiter(request: Request) -> BoundedSemaphore:
    return request.app.state.llm_limiter
