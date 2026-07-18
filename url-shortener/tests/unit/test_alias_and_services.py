import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.core.errors import ConflictError, GoneError, NotFoundError
from app.schemas.url import CreateURLRequest
from app.services.alias import generate_code, is_valid_alias
from app.services.cache import CacheService, CachedURL
from app.services.idempotency import IdempotencyService
from app.services.shortener import ShortenerService


def test_generate_code_length() -> None:
    code = generate_code(8)
    assert len(code) == 8
    assert code.isalnum()


def test_is_valid_alias() -> None:
    assert is_valid_alias("my-link")
    assert is_valid_alias("abc")
    assert not is_valid_alias("ab")
    assert not is_valid_alias("bad alias")
    assert not is_valid_alias("has/slash")


def test_cache_ttl_capped_by_expiry() -> None:
    client = MagicMock()
    settings = Settings(cache_ttl_seconds=300)
    cache = CacheService(client, settings)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=60)

    cache.set("abc1234", "https://example.com", expires_at)

    client.setex.assert_called_once()
    args = client.setex.call_args[0]
    assert args[0] == "short:abc1234"
    assert args[1] <= 60
    payload = json.loads(args[2])
    assert payload["original_url"] == "https://example.com"


def test_cache_deletes_when_already_expired() -> None:
    client = MagicMock()
    settings = Settings(cache_ttl_seconds=300)
    cache = CacheService(client, settings)
    expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    cache.set("abc1234", "https://example.com", expires_at)

    client.delete.assert_called_once_with("short:abc1234")
    client.setex.assert_not_called()


def test_idempotency_request_hash_stable() -> None:
    a = IdempotencyService.request_hash({"url": "https://a.com", "custom_alias": None, "expires_in_seconds": 10})
    b = IdempotencyService.request_hash({"expires_in_seconds": 10, "custom_alias": None, "url": "https://a.com"})
    assert a == b


def test_idempotency_conflict_on_different_body() -> None:
    client = MagicMock()
    settings = Settings()
    service = IdempotencyService(client, settings)
    stored = {
        "request_hash": "aaa",
        "status_code": 201,
        "body": {"code": "x"},
    }
    client.get.return_value = json.dumps(stored)

    with pytest.raises(ConflictError):
        service.get_cached_response("key-1", "bbb")


def test_shortener_metadata_not_found() -> None:
    repo = MagicMock()
    repo.get_by_code.return_value = None
    cache = MagicMock()
    settings = Settings()
    service = ShortenerService(repo, cache, settings)

    with pytest.raises(NotFoundError):
        service.get_metadata("missing")


def test_shortener_expired_raises_gone() -> None:
    repo = MagicMock()
    row = MagicMock()
    row.code = "expired1"
    row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    row.original_url = "https://example.com"
    repo.get_by_code.return_value = row
    cache = MagicMock()
    cache.get.return_value = None
    settings = Settings()
    service = ShortenerService(repo, cache, settings)

    with pytest.raises(GoneError):
        service.resolve_for_redirect("expired1")


def test_shortener_cache_hit_increments_and_redirects() -> None:
    repo = MagicMock()
    repo.increment_access_count.return_value = MagicMock()
    cache = MagicMock()
    cache.get.return_value = CachedURL(
        original_url="https://example.com/cached",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    settings = Settings()
    service = ShortenerService(repo, cache, settings)

    url = service.resolve_for_redirect("hotlink")

    assert url == "https://example.com/cached"
    repo.get_by_code.assert_not_called()
    repo.increment_access_count.assert_called_once_with("hotlink")


def test_create_url_request_rejects_reserved_alias() -> None:
    with pytest.raises(ValueError):
        CreateURLRequest(url="https://example.com", custom_alias="api")
