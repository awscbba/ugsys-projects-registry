"""Domain and unhandled exception handlers for FastAPI."""

from __future__ import annotations

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

from src.domain.exceptions import (
    AccountLockedError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    ExternalServiceError,
    NotFoundError,
    RepositoryError,
    ValidationError,
)

logger = structlog.get_logger()

_STATUS_MAP: dict[type[DomainError], int] = {
    ValidationError: 422,
    NotFoundError: 404,
    ConflictError: 409,
    AuthenticationError: 401,
    AuthorizationError: 403,
    AccountLockedError: 423,
    RepositoryError: 500,
    ExternalServiceError: 502,
}


async def domain_exception_handler(request: Request, exc: DomainError) -> JSONResponse:
    status = _STATUS_MAP.get(type(exc), 500)
    logger.error(
        "domain_error",
        error_code=exc.error_code,
        message=exc.message,
        status=status,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=status,
        content={
            "error": exc.error_code,
            "message": exc.user_message,
            "data": exc.additional_data,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
    )
