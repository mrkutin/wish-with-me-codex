from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from fastapi import HTTPException, status


@dataclass(frozen=True)
class ValidatedURL:
    url: str
    hostname: str
    scheme: str


def _env_allowlist_hosts() -> set[str]:
    raw = (os.environ.get("SSRF_ALLOWLIST_HOSTS") or "").strip()
    if not raw:
        return set()
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _is_forbidden_ip(ip: ipaddress._BaseAddress) -> bool:
    # Block internal addressing by default.
    return bool(
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or getattr(ip, "is_reserved", False)
    )


def _resolve_all_ips(hostname: str) -> Iterable[ipaddress._BaseAddress]:
    # Note: resolution happens on the server; this is SSRF-critical.
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return []
    ips: list[ipaddress._BaseAddress] = []
    for family, _, _, _, sockaddr in infos:
        try:
            if family == socket.AF_INET:
                ips.append(ipaddress.ip_address(sockaddr[0]))
            elif family == socket.AF_INET6:
                ips.append(ipaddress.ip_address(sockaddr[0]))
        except Exception:
            continue
    return ips


def validate_public_http_url(url: str) -> ValidatedURL:
    u = (url or "").strip()
    if not u:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="url is required")

    parsed = urlparse(u)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="url must be http(s)")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="url must include hostname")

    # Fast path blocks
    if hostname in ("localhost",):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SSRF blocked")
    if hostname.endswith(".local"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SSRF blocked")

    allowlist = _env_allowlist_hosts()
    if hostname in allowlist:
        return ValidatedURL(url=u, hostname=hostname, scheme=scheme)

    ips = list(_resolve_all_ips(hostname))
    if not ips:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Host could not be resolved")
    if any(_is_forbidden_ip(ip) for ip in ips):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SSRF blocked")

    return ValidatedURL(url=u, hostname=hostname, scheme=scheme)


