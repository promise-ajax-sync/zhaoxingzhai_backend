from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_health() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_interpret_endpoint_falls_back_without_ai_config(monkeypatch) -> None:
    monkeypatch.setenv("AI_API_KEY", "")
    monkeypatch.setenv("AI_MODEL", "")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/interpret",
            json={
                "question": {
                    "rawText": "今天应该怎么做",
                    "topic": "career",
                    "intent": "action",
                    "intentLabel": "行动建议",
                },
                "evidence": {
                    "methodId": "daily-hexagram",
                    "version": 1,
                    "calculationFacts": [],
                    "supportingEvidence": [],
                    "counterEvidence": [],
                    "limitations": [],
                    "summary": "以本卦和动爻为依据。",
                },
                "localAnswer": "先完成已有安排。",
                "methodLabel": "每日一卦",
                "answerStyle": "chat",
                "locale": "zh-CN",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "local_fallback"
    assert body["evidenceMethodId"] == "daily-hexagram"
    assert "先完成已有安排" in body["content"]
    get_settings.cache_clear()
