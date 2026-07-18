import json
from dataclasses import dataclass
from datetime import datetime, timezone

import redis

from app.config import Settings


@dataclass(frozen=True)
class CachedURL:
    original_url: str
    expires_at: datetime | None


class CacheService:
    def __init__(self, client: redis.Redis, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def _key(self, code: str) -> str:
        return f"short:{code}"

    def get(self, code: str) -> CachedURL | None:
        raw = self._client.get(self._key(code))
        if not raw:
            return None
        data = json.loads(raw)
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])
        return CachedURL(original_url=data["original_url"], expires_at=expires_at)

    def set(self, code: str, original_url: str, expires_at: datetime | None) -> None:
        now = datetime.now(timezone.utc)
        ttl = self._settings.cache_ttl_seconds
        if expires_at is not None:
            # Ensure timezone-aware comparison
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            remaining = int((expires_at - now).total_seconds())
            if remaining <= 0:
                self.delete(code)
                return
            ttl = min(ttl, remaining)

        payload = {
            "original_url": original_url,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }
        self._client.setex(self._key(code), ttl, json.dumps(payload))

    def delete(self, code: str) -> None:
        self._client.delete(self._key(code))
