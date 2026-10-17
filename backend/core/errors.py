"""Shared API errors and exception handlers."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from json import JSONDecodeError
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details if details is not None else {}


def error_response(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details if details is not None else {},
            }
        },
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = sorted(
            {
                ".".join(str(part) for part in error.get("loc", ()) if part != "body")
                or "body"
                for error in exc.errors()
            }
        )
        return error_response(
            400,
            "VALIDATION_ERROR",
            "Request validation failed",
            {"fields": fields},
        )

    @app.exception_handler(JSONDecodeError)
    async def json_decode_error_handler(
        _request: Request, _exc: JSONDecodeError
    ) -> JSONResponse:
        return error_response(
            400, "VALIDATION_ERROR", "Malformed JSON", {"fields": ["body"]}
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        if exc.status_code == 404:
            code, message = "NOT_FOUND", "Not found"
        elif exc.status_code == 405:
            code, message = "METHOD_NOT_ALLOWED", "Method not allowed"
        else:
            code, message = "HTTP_ERROR", str(exc.detail)
        return error_response(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        _request: Request, _exc: Exception
    ) -> JSONResponse:
        return error_response(500, "INTERNAL_SERVER_ERROR", "Internal server error")
