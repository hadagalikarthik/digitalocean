from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.api.deps import get_shortener_service
from app.schemas.url import ErrorResponse
from app.services.shortener import ShortenerService

router = APIRouter(tags=["redirect"])


@router.get(
    "/{code}",
    responses={
        302: {"description": "Redirect to original URL"},
        404: {"model": ErrorResponse},
        410: {"model": ErrorResponse},
    },
    status_code=302,
)
def redirect_to_original(
    code: str,
    service: Annotated[ShortenerService, Depends(get_shortener_service)],
) -> RedirectResponse:
    original_url = service.resolve_for_redirect(code)
    return RedirectResponse(url=original_url, status_code=302)
