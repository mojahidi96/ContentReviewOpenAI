from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.dependencies import get_review_service
from app.schemas.content_review import ModelReview


class FakeProvider:
    model_name = "test-model"

    def generate_structured(self, prompt, response_schema):
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
