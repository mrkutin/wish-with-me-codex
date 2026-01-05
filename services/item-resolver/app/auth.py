from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException, status


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0].strip(), parts[1].strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def require_bearer_token(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> None:
    expected = os.environ.get("RU_BEARER_TOKEN")
    if not expected:
        # Fail closed: service is misconfigured.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RU_BEARER_TOKEN is not configured",
        )

    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    # Constant-time compare
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")


