import hashlib
import json
import time
from typing import Any

import redis

from app.config import Settings
from app.core.errors import ConflictError


class IdempotencyService:
    def __init__(self, client: redis.Redis, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def _result_key(self, key: str) -> str:
        return f"idempotency:{key}"

    def _lock_key(self, key: str) -> str:
        return f"idempotency:lock:{key}"

    @staticmethod
    def request_hash(payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get_cached_response(self, key: str, request_hash: str) -> dict[str, Any] | None:
        raw = self._client.get(self._result_key(key))
        if not raw:
            return None
        stored = json.loads(raw)
        if stored["request_hash"] != request_hash:
            raise ConflictError("Idempotency-Key reused with a different request body")
        return {
            "status_code": stored["status_code"],
            "body": stored["body"],
        }

    def acquire_lock(self, key: str) -> bool:
        return bool(
            self._client.set(
                self._lock_key(key),
                "1",
                nx=True,
                ex=max(int(self._settings.idempotency_lock_wait_seconds) + 5, 10),
            )
        )

    def release_lock(self, key: str) -> None:
        self._client.delete(self._lock_key(key))

    def wait_for_result(self, key: str, request_hash: str) -> dict[str, Any] | None:
        deadline = time.monotonic() + self._settings.idempotency_lock_wait_seconds
        while time.monotonic() < deadline:
            cached = self.get_cached_response(key, request_hash)
            if cached is not None:
                return cached
            time.sleep(0.05)
        return None

    def store_response(self, key: str, request_hash: str, status_code: int, body: dict[str, Any]) -> None:
        payload = {
            "request_hash": request_hash,
            "status_code": status_code,
            "body": body,
        }
        self._client.setex(
            self._result_key(key),
            self._settings.idempotency_ttl_seconds,
            json.dumps(payload, default=str),
        )
