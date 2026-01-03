import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status

from app.routers import auth, shares, sync, users, wishlists

app = FastAPI(title="Wish With Me - Core API")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


def _error_payload(code: str, message: str, details: dict, trace_id: str | None) -> dict:
    return {"code": code, "message": message, "details": details, "trace_id": trace_id}


def _status_code_label(status_code: int) -> str:
    mapping = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_409_CONFLICT: "CONFLICT",
        status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
    }
    return mapping.get(status_code, "HTTP_ERROR")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    trace_id = getattr(request.state, "request_id", None)
    details = exc.detail if isinstance(exc.detail, dict) else {}
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    payload = _error_payload(_status_code_label(exc.status_code), message, details, trace_id)
    response = JSONResponse(status_code=exc.status_code, content=payload)
    if trace_id:
        response.headers["X-Request-Id"] = trace_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "request_id", None)
    payload = _error_payload("VALIDATION_ERROR", "Validation failed", {"errors": exc.errors()}, trace_id)
    response = JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)
    if trace_id:
        response.headers["X-Request-Id"] = trace_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "request_id", None)
    payload = _error_payload("INTERNAL_ERROR", "Internal server error", {}, trace_id)
    response = JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)
    if trace_id:
        response.headers["X-Request-Id"] = trace_id
    return response

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(wishlists.router)
app.include_router(shares.router)
app.include_router(sync.router)


@app.get("/health")
async def health():
    return {"ok": True}
