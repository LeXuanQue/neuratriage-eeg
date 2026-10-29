"""Response envelope: every JSON body wraps as {success, data} or {success, error}.

Frontend (frontend/lib/api.js) requires this exact shape — do not break it.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger("neuratriage.envelope")


def ok(data: Any = None, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "data": jsonable_encoder(data)},
    )


def err(message: str, code: str = "ERROR", status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {"message": message, "code": code},
        },
    )


class EnvelopeError(Exception):
    """Raise from anywhere to produce a {success:false, error:{...}} response."""

    def __init__(
        self,
        message: str,
        code: str = "ERROR",
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


async def envelope_error_handler(_: Request, exc: EnvelopeError) -> JSONResponse:
    return err(exc.message, exc.code, exc.status_code)


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "HTTP_" + str(exc.status_code)
    detail: Optional[str] = None
    if isinstance(exc.detail, str):
        detail = exc.detail
    elif exc.detail is not None:
        detail = str(exc.detail)
    return err(detail or exc.__class__.__name__, code, exc.status_code)


async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    msg = first.get("msg") or "Invalid request"
    return err(msg, "VALIDATION_ERROR", status.HTTP_422_UNPROCESSABLE_ENTITY)


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    # Log the full exception server-side, but never echo raw exception text
    # (which can embed SQL, file paths, model internals) back to the client.
    logger.exception("Unhandled exception", exc_info=exc)
    return err("Internal server error", "INTERNAL_ERROR", 500)
