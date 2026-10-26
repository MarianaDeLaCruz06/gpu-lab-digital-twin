"""Maps every failure to the contract ErrorBody so no stack trace reaches a client."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from gpu_lab_twin.api.schemas import ErrorBody
from gpu_lab_twin.domain.errors import DomainError, ErrorCode

logger = logging.getLogger(__name__)

HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.ERR_SCHEMA: 422,
    ErrorCode.ERR_CAPACITY_RANGE: 422,
    ErrorCode.ERR_UNKNOWN_NODE: 404,
    ErrorCode.ERR_INGRESS_UNAVAILABLE: 503,
}
_DEFAULT_CONFLICT_STATUS = 409


def error_response(error: DomainError) -> JSONResponse:
    body = ErrorBody(code=error.code, message=error.message, retryable=error.retryable, details=error.details)
    status = HTTP_STATUS.get(error.code, _DEFAULT_CONFLICT_STATUS)
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        return error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", ()) if part not in ("body", "path"))
        rule = first.get("msg", "invalid value")
        return error_response(
            DomainError(
                ErrorCode.ERR_SCHEMA,
                f"Field {field or 'request'} violates {rule}.",
                details={"field": field, "rule": first.get("type", "invalid")},
            )
        )

    @app.exception_handler(Exception)
    async def _unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error; request rolled back", exc_info=exc)
        return error_response(
            DomainError(ErrorCode.ERR_INGRESS_UNAVAILABLE, "Ingress is unavailable; the event was not accepted.")
        )
