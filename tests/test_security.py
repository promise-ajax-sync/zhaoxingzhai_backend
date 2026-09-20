import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import ApiProtectionMiddleware, InMemoryRateLimiter


def protected_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.add_middleware(ApiProtectionMiddleware, settings=settings)

    @app.post("/api/v1/interpret")
    async def interpret() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_request_id_is_generated_and_client_value_can_be_preserved() -> None:
    app = protected_app(Settings(app_rate_limit_requests=10))
    with TestClient(app) as client:
        generated = client.post("/api/v1/interpret", json={})
        preserved = client.post(
            "/api/v1/interpret",
            json={},
            headers={"X-Request-ID": "client-request-123"},
        )

    assert generated.headers["X-Request-ID"]
    assert preserved.headers["X-Request-ID"] == "client-request-123"


def test_interpret_endpoint_is_rate_limited() -> None:
    app = protected_app(
        Settings(app_rate_limit_requests=2, app_rate_limit_window_seconds=60)
    )
    with TestClient(app) as client:
        assert client.post("/api/v1/interpret", json={}).status_code == 200
        assert client.post("/api/v1/interpret", json={}).status_code == 200
        limited = client.post("/api/v1/interpret", json={})

    assert limited.status_code == 429
    assert limited.json()["detail"] == "请求过于频繁，请稍后再试"
    assert limited.headers["Retry-After"]
    assert limited.headers["X-Request-ID"] == limited.json()["requestId"]


def test_oversized_request_is_rejected_before_handler() -> None:
    app = protected_app(Settings(app_max_request_bytes=1024))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/interpret",
            content=b"x" * 1025,
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json()["detail"] == "请求内容过大"


def test_request_log_does_not_include_body_or_credentials(caplog) -> None:
    app = protected_app(Settings(app_rate_limit_requests=10))
    caplog.set_level(logging.INFO, logger="zhaoxingzhai.request")
    secret = "sk-do-not-log"
    private_question = "这是不应进入日志的私人问题"
    with TestClient(app) as client:
        client.post(
            "/api/v1/interpret?debug=private-query",
            json={"question": private_question},
            headers={"Authorization": f"Bearer {secret}"},
        )

    logs = caplog.text
    assert "request_complete" in logs
    assert secret not in logs
    assert private_question not in logs
    assert "private-query" not in logs


def test_rate_limiter_releases_entries_after_window() -> None:
    limiter = InMemoryRateLimiter(limit=1, window_seconds=10)
    assert limiter.allow("client", now=1)[0] is True
    assert limiter.allow("client", now=2)[0] is False
    assert limiter.allow("client", now=11)[0] is True
