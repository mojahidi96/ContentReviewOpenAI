from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.dependencies import get_review_service
from app.schemas.content_review import ModelReview


class FakeProvider:
    model_name = "test-model"

    def generate_structured(self, prompt, response_schema, model=None):
        return ModelReview(issues=[]), None, None


def fake_review_service():
    from app.services.content_review_service import ContentReviewService

    return ContentReviewService(FakeProvider(), 1000)


def test_health_and_internal_auth():
    app.dependency_overrides[get_review_service] = fake_review_service
    client = TestClient(app).__enter__()
    assert client.get("/health/live").json() == {"status": "live"}
    denied = client.post("/internal/v1/content-reviews", json={
        "requestId": "r", "content": "Text"
    })
    assert denied.status_code == 401
    allowed = client.post(
        "/internal/v1/content-reviews",
        headers={"Authorization": f"Bearer {get_settings().internal_service_token.get_secret_value()}"},
        json={"requestId": "r", "content": "Text"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["issues"] == []
    app.dependency_overrides.clear()


def test_models_endpoint_and_quota_error_shape():
    from app.errors import ProviderRateLimited

    class Limited:
        model_name = "test-model"

        def generate_structured(self, prompt, response_schema, model=None):
            raise ProviderRateLimited(model=model or "m", retry_after_seconds=90, quota_scope="minute")

    from app.services.content_review_service import ContentReviewService

    app.dependency_overrides[get_review_service] = lambda: ContentReviewService(Limited(), 1000, ["m"])
    headers = {"Authorization": f"Bearer {get_settings().internal_service_token.get_secret_value()}"}
    with TestClient(app) as client:
        models = client.get("/internal/v1/content-reviews/models", headers=headers).json()
        assert models["defaultModel"] in models["models"]
        limited = client.post(
            "/internal/v1/content-reviews", headers=headers, json={"requestId": "r", "content": "Text", "model": "m"}
        )
        assert limited.status_code == 429
        assert limited.headers["retry-after"] == "90"
        error = limited.json()["error"]
        assert error["code"] == "LLM_QUOTA_EXHAUSTED"
        assert error["details"]["retryAfterSeconds"] == 90
        assert "1m" in error["message"]
        bad = client.post(
            "/internal/v1/content-reviews", headers=headers, json={"requestId": "r", "content": "Text", "model": "zzz"}
        )
        assert bad.status_code == 422 and bad.json()["error"]["code"] == "MODEL_NOT_ALLOWED"
    app.dependency_overrides.clear()
