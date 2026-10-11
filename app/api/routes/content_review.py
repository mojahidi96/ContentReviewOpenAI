from threading import BoundedSemaphore

from fastapi import APIRouter, Depends

from app.dependencies import get_llm_limiter, get_review_service, require_internal_auth
from app.errors import ServiceError
from app.config import Settings, get_settings
from app.schemas.content_review import ModelListResponse, ReviewRequest, ReviewResponse
from app.services.content_review_service import ContentReviewService

router = APIRouter(
    prefix="/internal/v1/content-reviews",
    tags=["content-review"],
    dependencies=[Depends(require_internal_auth)],
)


@router.get("/models", response_model=ModelListResponse)
def list_models(settings: Settings = Depends(get_settings)) -> ModelListResponse:
    return ModelListResponse(defaultModel=settings.gemini_model, models=settings.selectable_models)


@router.post("", response_model=ReviewResponse)
def create_review(
    payload: ReviewRequest,
    service: ContentReviewService = Depends(get_review_service),
    limiter: BoundedSemaphore = Depends(get_llm_limiter),
) -> ReviewResponse:
    if not limiter.acquire(blocking=False):
        raise ServiceError("AI_CONCURRENCY_LIMIT", "The AI service is busy; retry shortly.", 503)
    try:
        return service.review(payload)
    finally:
        limiter.release()
