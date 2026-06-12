import uuid

from fastapi.testclient import TestClient

from app.main import app

API_KEY = "dev-key-change-me"


def _post(client: TestClient, user_id: str, question: str):
    return client.post(
        "/ask",
        headers={"X-API-Key": API_KEY},
        json={"user_id": user_id, "question": question},
    )


def test_auth_required():
    with TestClient(app) as client:
        response = client.post("/ask", json={"user_id": "anon", "question": "hello"})

    assert response.status_code == 401


def test_agent_keeps_conversation_history():
    user_id = f"history-{uuid.uuid4().hex}"
    with TestClient(app) as client:
        first = _post(client, user_id, "My name is Alice")
        second = _post(client, user_id, "What is my name?")

    assert first.status_code == 200
    assert second.status_code == 200
    assert "Alice" in second.json()["answer"]
    assert second.json()["history_turns"] == 2


def test_rate_limit_returns_429_after_ten_requests():
    user_id = f"rate-{uuid.uuid4().hex}"
    codes = []

    with TestClient(app) as client:
        for index in range(11):
            response = _post(client, user_id, f"request {index}")
            codes.append(response.status_code)

    assert codes[:10] == [200] * 10
    assert codes[10] == 429


def test_health_and_readiness_endpoints():
    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code in {200, 503}


def test_info_metrics_and_history_endpoints():
    user_id = f"ops-{uuid.uuid4().hex}"

    with TestClient(app) as client:
        root = client.get("/")
        _post(client, user_id, "remember this")
        history = client.get(f"/history/{user_id}", headers={"X-API-Key": API_KEY})
        metrics = client.get("/metrics", headers={"X-API-Key": API_KEY})
        deleted = client.delete(f"/history/{user_id}", headers={"X-API-Key": API_KEY})
        deleted_history = client.get(f"/history/{user_id}", headers={"X-API-Key": API_KEY})

    assert root.status_code == 200
    assert root.json()["endpoints"]["ask"] == "POST /ask with X-API-Key"
    assert history.status_code == 200
    assert history.json()["count"] >= 2
    assert metrics.status_code == 200
    assert metrics.json()["rate_limit_per_minute"] == 10
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == user_id
    assert deleted_history.status_code == 200
    assert deleted_history.json()["count"] == 0
