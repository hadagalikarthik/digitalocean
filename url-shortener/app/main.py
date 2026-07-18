from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import redirect, urls
from app.config import get_settings
from app.core.errors import AppError, ConflictError, GoneError, NotFoundError, ValidationAppError


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0")

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.message})

    @app.exception_handler(GoneError)
    async def gone_handler(_: Request, exc: GoneError) -> JSONResponse:
        return JSONResponse(status_code=410, content={"detail": exc.message})

    @app.exception_handler(ConflictError)
    async def conflict_handler(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": exc.message})

    @app.exception_handler(ValidationAppError)
    async def validation_handler(_: Request, exc: ValidationAppError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.message})

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.message})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(urls.router)
    app.include_router(redirect.router)
    return app


app = create_app()
