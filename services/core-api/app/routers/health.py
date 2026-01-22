"""Health check endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.redis import get_redis

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    database: str
    redis: str


@router.get("/healthz", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Check application health."""
    db_status = "healthy"
    redis_status = "healthy"

    # Check database
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    # Check Redis
    try:
        redis_client = await get_redis()
        await redis_client.ping()
    except Exception:
        redis_status = "unhealthy"

    overall_status = "healthy" if db_status == "healthy" and redis_status == "healthy" else "unhealthy"

    return HealthResponse(
        status=overall_status,
        database=db_status,
        redis=redis_status,
    )


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Kubernetes readiness probe endpoint."""
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """Kubernetes liveness probe endpoint."""
    return {"status": "alive"}
