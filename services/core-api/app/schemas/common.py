"""Common schemas used across the API."""

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Error detail structure."""

    field: str | None = None
    reason: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response format."""

    code: str
    message: str
    details: ErrorDetail | dict[str, Any] | None = None
    trace_id: str | None = None


class APIError(BaseModel):
    """API error wrapper."""

    error: ErrorResponse


class PaginatedResponse(BaseModel):
    """Base paginated response."""

    total: int
    limit: int
    offset: int
