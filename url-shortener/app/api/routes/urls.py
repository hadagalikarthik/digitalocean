from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from app.api.deps import get_idempotency, get_shortener_service
from app.core.errors import ConflictError
from app.schemas.url import CreateURLRequest, ErrorResponse, URLResponse
from app.services.idempotency import IdempotencyService
from app.services.shortener import ShortenerService

router = APIRouter(prefix="/api/v1/urls", tags=["urls"])


@router.post(
    "",
    response_model=URLResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": URLResponse, "description": "Idempotent replay"},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def create_url(
    payload: CreateURLRequest,
    response: Response,
    service: Annotated[ShortenerService, Depends(get_shortener_service)],
    idempotency: Annotated[IdempotencyService, Depends(get_idempotency)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> URLResponse:
    if not idempotency_key:
        result, _ = service.create(payload)
        return result

    body_for_hash = {
        "url": str(payload.url),
        "custom_alias": payload.custom_alias,
        "expires_in_seconds": payload.expires_in_seconds,
    }
    request_hash = idempotency.request_hash(body_for_hash)

    cached = idempotency.get_cached_response(idempotency_key, request_hash)
    if cached is not None:
        response.status_code = status.HTTP_200_OK
        return URLResponse.model_validate(cached["body"])

    if not idempotency.acquire_lock(idempotency_key):
        waited = idempotency.wait_for_result(idempotency_key, request_hash)
        if waited is not None:
            response.status_code = status.HTTP_200_OK
            return URLResponse.model_validate(waited["body"])
        raise ConflictError("Idempotent request is still in progress; retry shortly")

    try:
        # Re-check after acquiring lock
        cached = idempotency.get_cached_response(idempotency_key, request_hash)
        if cached is not None:
            response.status_code = status.HTTP_200_OK
            return URLResponse.model_validate(cached["body"])

        result, _ = service.create(payload)
        body = result.model_dump(mode="json")
        idempotency.store_response(idempotency_key, request_hash, status.HTTP_201_CREATED, body)
        response.status_code = status.HTTP_201_CREATED
        return result
    finally:
        idempotency.release_lock(idempotency_key)


@router.get(
    "/{code}",
    response_model=URLResponse,
    responses={
        404: {"model": ErrorResponse},
        410: {"model": ErrorResponse},
    },
)
def get_url_metadata(
    code: str,
    service: Annotated[ShortenerService, Depends(get_shortener_service)],
) -> URLResponse:
    return service.get_metadata(code)
