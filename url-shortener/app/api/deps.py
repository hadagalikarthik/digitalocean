from collections.abc import Generator

import redis
from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.repositories.url_repository import URLRepository
from app.services.cache import CacheService
from app.services.idempotency import IdempotencyService
from app.services.shortener import ShortenerService

_redis_client: redis.Redis | None = None


def get_redis(settings: Settings = Depends(get_settings)) -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def get_cache(
    client: redis.Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> CacheService:
    return CacheService(client, settings)


def get_idempotency(
    client: redis.Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> IdempotencyService:
    return IdempotencyService(client, settings)


def get_shortener_service(
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> Generator[ShortenerService, None, None]:
    yield ShortenerService(URLRepository(db), cache, settings)
