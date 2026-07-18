from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.url import ShortURL


def test_create_and_redirect(client: TestClient) -> None:
    create = client.post("/api/v1/urls", json={"url": "https://example.com/long/path"})
    assert create.status_code == 201
    body = create.json()
    assert body["code"]
    assert body["short_url"].endswith(f"/{body['code']}")
    assert body["access_count"] == 0

    redirect = client.get(f"/{body['code']}", follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://example.com/long/path"

    meta = client.get(f"/api/v1/urls/{body['code']}")
    assert meta.status_code == 200
    assert meta.json()["access_count"] == 1


def test_custom_alias_conflict(client: TestClient) -> None:
    first = client.post(
        "/api/v1/urls",
        json={"url": "https://example.com/one", "custom_alias": "my-link"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/urls",
        json={"url": "https://example.com/two", "custom_alias": "my-link"},
    )
    assert second.status_code == 409


def test_unknown_code_returns_404(client: TestClient) -> None:
    response = client.get("/no-such-code", follow_redirects=False)
    assert response.status_code == 404


def test_expired_code_returns_410(client: TestClient, db_session: Session) -> None:
    row = ShortURL(
        code="expired1",
        original_url="https://example.com/gone",
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        access_count=0,
        is_custom=True,
    )
    db_session.add(row)
    db_session.commit()

    redirect = client.get("/expired1", follow_redirects=False)
    assert redirect.status_code == 410

    meta = client.get("/api/v1/urls/expired1")
    assert meta.status_code == 410


def test_idempotency_key_replay(client: TestClient) -> None:
    headers = {"Idempotency-Key": "req-123"}
    payload = {"url": "https://example.com/idempotent"}

    first = client.post("/api/v1/urls", json=payload, headers=headers)
    assert first.status_code == 201
    first_body = first.json()

    second = client.post("/api/v1/urls", json=payload, headers=headers)
    assert second.status_code == 200
    assert second.json()["code"] == first_body["code"]


def test_idempotency_key_conflict_on_different_body(client: TestClient) -> None:
    headers = {"Idempotency-Key": "req-456"}
    first = client.post(
        "/api/v1/urls",
        json={"url": "https://example.com/a"},
        headers=headers,
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/urls",
        json={"url": "https://example.com/b"},
        headers=headers,
    )
    assert second.status_code == 409


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
