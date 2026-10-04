from threading import BoundedSemaphore

from fastapi import APIRouter, Depends

from app.dependencies import get_chat_service, get_llm_limiter, require_internal_auth
from app.errors import ServiceError
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(
    prefix="/internal/v1/chat",
    tags=["chat"],
    dependencies=[Depends(require_internal_auth)],
)


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
    limiter: BoundedSemaphore = Depends(get_llm_limiter),
) -> ChatResponse:
    if not limiter.acquire(blocking=False):
        raise ServiceError("AI_CONCURRENCY_LIMIT", "The AI service is busy; retry shortly.", 503)
    try:
        return service.answer(payload)
    finally:
        limiter.release()
