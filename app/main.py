import logging
from contextlib import asynccontextmanager
from threading import BoundedSemaphore

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import chat, content_review, documents, health
from app.config import get_settings
from app.errors import ServiceError


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    application.state.llm_limiter = BoundedSemaphore(settings.max_concurrent_llm_requests)
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="ContentReviewOpenAI", version="1.0.0", lifespan=lifespan)
    application.include_router(health.router)
    application.include_router(content_review.router)
    application.include_router(documents.router)
    application.include_router(chat.router)

    @application.middleware("http")
    async def enforce_body_limit(request: Request, call_next):
        from app.config import get_settings

        content_length = request.headers.get("content-length")
        if content_length:
            max_body = get_settings().max_upload_bytes + 1024 * 1024
            if content_length.isdigit() and int(content_length) > max_body:
                return JSONResponse(
                    status_code=413,
                    content={"error": {"code": "REQUEST_TOO_LARGE", "message": "Request body exceeds the configured limit.", "requestId": request.headers.get("x-request-id")}},
                )
        return await call_next(request)

    @application.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError):
        request_id = request.headers.get("x-request-id")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "requestId": request_id}},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request data is invalid.",
                    "requestId": request.headers.get("x-request-id"),
                    "details": [
                        {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
                        for error in exc.errors()
                    ],
                }
            },
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logging.getLogger(__name__).exception("Unhandled request failure")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "The request could not be completed.", "requestId": request.headers.get("x-request-id")}},
        )

    return application


app = create_app()
