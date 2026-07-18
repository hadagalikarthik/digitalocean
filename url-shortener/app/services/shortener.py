from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.core.errors import ConflictError, GoneError, NotFoundError
from app.models.url import ShortURL
from app.repositories.url_repository import URLRepository
from app.schemas.url import CreateURLRequest, URLResponse
from app.services.alias import generate_code
from app.services.cache import CacheService


class ShortenerService:
    MAX_CODE_RETRIES = 5

    def __init__(
        self,
        repository: URLRepository,
        cache: CacheService,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._cache = cache
        self._settings = settings

    def create(self, payload: CreateURLRequest) -> tuple[URLResponse, bool]:
        """Create a short URL. Returns (response, created) where created is True on insert."""
        expires_at = None
        if payload.expires_in_seconds is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=payload.expires_in_seconds)

        original_url = str(payload.url)
        if payload.custom_alias:
            row = self._repository.create(
                code=payload.custom_alias,
                original_url=original_url,
                expires_at=expires_at,
                is_custom=True,
            )
        else:
            row = self._create_with_generated_code(original_url, expires_at)

        self._cache.set(row.code, row.original_url, row.expires_at)
        return self._to_response(row), True

    def _create_with_generated_code(self, original_url: str, expires_at: datetime | None) -> ShortURL:
        last_error: Exception | None = None
        for _ in range(self.MAX_CODE_RETRIES):
            code = generate_code(self._settings.short_code_length)
            try:
                return self._repository.create(
                    code=code,
                    original_url=original_url,
                    expires_at=expires_at,
                    is_custom=False,
                )
            except ConflictError as exc:
                last_error = exc
                continue
        raise RuntimeError("Failed to generate a unique short code") from last_error

    def get_metadata(self, code: str) -> URLResponse:
        row = self._repository.get_by_code(code)
        if row is None:
            raise NotFoundError(f"Short URL '{code}' not found")
        self._ensure_not_expired(row)
        return self._to_response(row)

    def resolve_for_redirect(self, code: str) -> str:
        cached = self._cache.get(code)
        if cached is not None:
            self._ensure_not_expired_values(code, cached.expires_at)
            updated = self._repository.increment_access_count(code)
            if updated is None:
                # Row expired or deleted between cache hit and update
                self._cache.delete(code)
                row = self._repository.get_by_code(code)
                if row is None:
                    raise NotFoundError(f"Short URL '{code}' not found")
                self._ensure_not_expired(row)
                raise GoneError(f"Short URL '{code}' has expired")
            return cached.original_url

        row = self._repository.get_by_code(code)
        if row is None:
            raise NotFoundError(f"Short URL '{code}' not found")
        self._ensure_not_expired(row)

        updated = self._repository.increment_access_count(code)
        if updated is None:
            raise GoneError(f"Short URL '{code}' has expired")

        self._cache.set(row.code, row.original_url, row.expires_at)
        return row.original_url

    def _ensure_not_expired(self, row: ShortURL) -> None:
        self._ensure_not_expired_values(row.code, row.expires_at)

    def _ensure_not_expired_values(self, code: str, expires_at: datetime | None) -> None:
        if expires_at is None:
            return
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            self._cache.delete(code)
            raise GoneError(f"Short URL '{code}' has expired")

    def _to_response(self, row: ShortURL) -> URLResponse:
        base = self._settings.base_url.rstrip("/")
        return URLResponse(
            code=row.code,
            short_url=f"{base}/{row.code}",
            original_url=row.original_url,
            created_at=row.created_at,
            expires_at=row.expires_at,
            access_count=row.access_count,
            is_custom=row.is_custom,
        )
