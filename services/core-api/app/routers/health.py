"""Health check endpoints - CouchDB-based."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.couchdb import get_couchdb

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    couchdb: str


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check application health."""
    couchdb_status = "healthy"

    # Check CouchDB
    try:
        db = get_couchdb()
        await db.info()
    except Exception:
        couchdb_status = "unhealthy"

    overall_status = "healthy" if couchdb_status == "healthy" else "unhealthy"

    return HealthResponse(
        status=overall_status,
        couchdb=couchdb_status,
    )


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Kubernetes readiness probe endpoint."""
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """Kubernetes liveness probe endpoint."""
    return {"status": "alive"}
