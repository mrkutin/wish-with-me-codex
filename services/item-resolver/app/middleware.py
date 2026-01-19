from __future__ import annotations

import contextvars
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .errors import ErrorResponse, ResolverError

REQUEST_ID_HEADER = "X-Request-Id"
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request_id_var.set(request_id)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def resolver_error_handler(request: Request, exc: ResolverError) -> JSONResponse:
    trace_id = getattr(request.state, "request_id", None) or get_request_id()
    error_response = ErrorResponse(
        code=exc.error_code.value,
        message=exc.error_message,
        details=exc.error_details,
        trace_id=trace_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(exclude_none=True),
        headers={REQUEST_ID_HEADER: trace_id} if trace_id else None,
    )


def setup_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(ResolverError, resolver_error_handler)
