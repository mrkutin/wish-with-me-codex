from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel


class ErrorCode(str, Enum):
    INVALID_URL = "INVALID_URL"
    SSRF_BLOCKED = "SSRF_BLOCKED"
    BLOCKED_OR_UNAVAILABLE = "BLOCKED_OR_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    UNSUPPORTED_CONTENT = "UNSUPPORTED_CONTENT"
    LLM_PARSE_FAILED = "LLM_PARSE_FAILED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    trace_id: str | None = None


class ResolverError(HTTPException):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error_code = code
        self.error_message = message
        self.error_details = details
        super().__init__(status_code=status_code, detail=message)


def invalid_url(message: str = "Invalid URL") -> ResolverError:
    return ResolverError(
        ErrorCode.INVALID_URL,
        message,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def ssrf_blocked(message: str = "Request blocked for security reasons") -> ResolverError:
    return ResolverError(
        ErrorCode.SSRF_BLOCKED,
        message,
        status_code=status.HTTP_403_FORBIDDEN,
    )


def blocked_or_unavailable(message: str = "Target page is blocked or unavailable") -> ResolverError:
    return ResolverError(
        ErrorCode.BLOCKED_OR_UNAVAILABLE,
        message,
        status_code=status.HTTP_502_BAD_GATEWAY,
    )


def timeout(message: str = "Request timed out") -> ResolverError:
    return ResolverError(
        ErrorCode.TIMEOUT,
        message,
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
    )


def unsupported_content(message: str = "Unsupported content type") -> ResolverError:
    return ResolverError(
        ErrorCode.UNSUPPORTED_CONTENT,
        message,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def llm_parse_failed(message: str = "Failed to parse LLM response") -> ResolverError:
    return ResolverError(
        ErrorCode.LLM_PARSE_FAILED,
        message,
        status_code=status.HTTP_502_BAD_GATEWAY,
    )


def unknown_error(message: str = "An unexpected error occurred") -> ResolverError:
    return ResolverError(
        ErrorCode.UNKNOWN_ERROR,
        message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
