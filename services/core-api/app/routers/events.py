"""Server-Sent Events endpoint for real-time updates."""

import asyncio
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.user import User
from app.redis import TokenBlocklist
from app.security import decode_access_token
from app.services.events import create_ping_event, event_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])

# Keepalive interval in seconds
KEEPALIVE_INTERVAL = 30


async def get_user_from_token_query(
    token: Annotated[str, Query(description="JWT access token")],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Authenticate user from query parameter token.

    EventSource API doesn't support custom headers, so we accept
    the JWT token as a query parameter for SSE endpoints only.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")

        if user_id_str is None:
            raise credentials_exception

        # Check if token is blocklisted
        if jti and await TokenBlocklist.is_blocked(jti):
            raise credentials_exception

        user_id = UUID(user_id_str)

    except (JWTError, ValueError):
        raise credentials_exception

    # Fetch user from database
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


@router.get("/stream")
async def event_stream(
    request: Request,
    current_user: Annotated[User, Depends(get_user_from_token_query)],
) -> StreamingResponse:
    """SSE endpoint for real-time updates.

    Client connects and receives events when:
    - Items are updated/resolved
    - Wishlists are modified
    - Marks change

    Connection auto-closes when client disconnects.
    Keepalive ping sent every 30 seconds to maintain connection.
    """

    async def generate():
        queue = await event_manager.connect(current_user.id)
        logger.info(
            f"SSE connected: user={current_user.id}, "
            f"total={event_manager.connection_count}"
        )

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.debug(f"Client disconnected: user={current_user.id}")
                    break

                try:
                    # Wait for event with timeout for keepalive
                    event = await asyncio.wait_for(
                        queue.get(), timeout=KEEPALIVE_INTERVAL
                    )

                    if event is None:
                        # None signals connection should close
                        # (user reconnected elsewhere or logout)
                        logger.debug(
                            f"SSE connection signaled to close: user={current_user.id}"
                        )
                        break

                    yield event.format()

                except asyncio.TimeoutError:
                    # Send keepalive ping
                    ping = create_ping_event()
                    yield ping.format()

        except asyncio.CancelledError:
            logger.debug(f"SSE cancelled: user={current_user.id}")
        except Exception as e:
            logger.exception(f"SSE error for user {current_user.id}: {e}")
        finally:
            # Pass the queue to disconnect to avoid race condition where
            # a new connection's queue gets removed by old connection's cleanup
            await event_manager.disconnect(current_user.id, queue)
            logger.info(
                f"SSE disconnected: user={current_user.id}, "
                f"total={event_manager.connection_count}"
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/status")
async def connection_status(current_user: CurrentUser) -> dict:
    """Check if user has active SSE connection.

    Useful for debugging and monitoring.
    """
    return {
        "connected": event_manager.is_connected(current_user.id),
        "total_connections": event_manager.connection_count,
    }
