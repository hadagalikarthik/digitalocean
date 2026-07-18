from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl, field_validator

AliasStr = Annotated[str, Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")]


class CreateURLRequest(BaseModel):
    url: HttpUrl
    custom_alias: AliasStr | None = None
    expires_in_seconds: int | None = Field(default=None, gt=0, le=31_536_000)

    @field_validator("custom_alias")
    @classmethod
    def reject_reserved_aliases(cls, value: str | None) -> str | None:
        if value is None:
            return value
        reserved = {"api", "health", "docs", "openapi.json", "redoc"}
        if value.lower() in reserved:
            raise ValueError(f"Alias '{value}' is reserved")
        return value


class URLResponse(BaseModel):
    code: str
    short_url: str
    original_url: str
    created_at: datetime
    expires_at: datetime | None
    access_count: int
    is_custom: bool

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    detail: str
