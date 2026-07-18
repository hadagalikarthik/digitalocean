from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models.url import ShortURL


class URLRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(
        self,
        *,
        code: str,
        original_url: str,
        expires_at: datetime | None,
        is_custom: bool,
    ) -> ShortURL:
        row = ShortURL(
            code=code,
            original_url=original_url,
            expires_at=expires_at,
            is_custom=is_custom,
            access_count=0,
        )
        self._db.add(row)
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            if self._is_unique_violation(exc):
                raise ConflictError(f"Alias '{code}' is already taken") from exc
            raise
        self._db.refresh(row)
        return row

    def get_by_code(self, code: str) -> ShortURL | None:
        return self._db.scalar(select(ShortURL).where(ShortURL.code == code))

    def increment_access_count(self, code: str) -> ShortURL | None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(ShortURL)
            .where(
                ShortURL.code == code,
                (ShortURL.expires_at.is_(None)) | (ShortURL.expires_at > now),
            )
            .values(access_count=ShortURL.access_count + 1)
            .returning(ShortURL)
        )
        row = self._db.scalar(stmt)
        if row is None:
            self._db.rollback()
            return None
        self._db.commit()
        return row

    @staticmethod
    def _is_unique_violation(exc: IntegrityError) -> bool:
        orig = getattr(exc, "orig", None)
        message = str(orig).lower() if orig is not None else str(exc).lower()
        return "unique" in message or "duplicate" in message
