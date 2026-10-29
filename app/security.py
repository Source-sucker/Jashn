import time
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

# In-memory IP rate limiter: {ip: [timestamp, timestamp, ...]}
_IP_REQUEST_LOG: dict[str, list[float]] = {}
MAX_TRACKED_IPS = 10000
EVICTION_THRESHOLD_IPS = 500
MAX_REQUEST_BODY_BYTES = 1024 * 1024  # 1 MB


def resolve_client_ip(request: Request, trusted_proxy_count: int = 0) -> str:
    """
    Resolves client IP securely:
    - If trusted_proxy_count > 0, reads X-Forwarded-For taking the hop that is
      trusted_proxy_count hops from the right (upstream proxy).
    - If trusted_proxy_count <= 0, uses request.client.host directly to prevent header spoofing.
    """
    if trusted_proxy_count > 0:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            if len(hops) >= trusted_proxy_count:
                return hops[-trusted_proxy_count]
            elif hops:
                return hops[0]

    return request.client.host if request.client else "127.0.0.1"


def evict_stale_ips(now: float | None = None) -> int:
    """
    Evicts stale IP entries older than 60 seconds from memory to prevent unbounded growth.
    Returns the count of evicted IP keys.
    """
    current_time = now if now is not None else time.time()
    window_start = current_time - 60.0
    stale_ips = []

    for ip, timestamps in list(_IP_REQUEST_LOG.items()):
        recent = [t for t in timestamps if t > window_start]
        if not recent:
            stale_ips.append(ip)
        else:
            _IP_REQUEST_LOG[ip] = recent

    for ip in stale_ips:
        _IP_REQUEST_LOG.pop(ip, None)

    # If still exceeding capacity under attack, purge oldest entries
    if len(_IP_REQUEST_LOG) > MAX_TRACKED_IPS:
        excess = len(_IP_REQUEST_LOG) - MAX_TRACKED_IPS
        for _ in range(excess):
            _IP_REQUEST_LOG.pop(next(iter(_IP_REQUEST_LOG)), None)

    return len(stale_ips)


def check_rate_limit(client_ip: str, now: float | None = None) -> bool:
    """
    Sliding window rate limiter: allows up to settings.rate_limit_per_min requests per minute.
    Evicts stale entries to ensure memory remains bounded.
    """
    current_time = now if now is not None else time.time()
    window_start = current_time - 60.0
    limit = settings.rate_limit_per_min

    # Periodic housekeeping if tracking many IPs
    if len(_IP_REQUEST_LOG) >= EVICTION_THRESHOLD_IPS:
        evict_stale_ips(current_time)

    timestamps = _IP_REQUEST_LOG.get(client_ip, [])
    recent = [t for t in timestamps if t > window_start]

    if len(recent) >= limit:
        _IP_REQUEST_LOG[client_ip] = recent
        return False

    recent.append(current_time)
    _IP_REQUEST_LOG[client_ip] = recent
    return True


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only rate limit /api/ routes to prevent blocking static asset delivery
        if request.url.path.startswith("/api/"):
            client_ip = resolve_client_ip(request, settings.trusted_proxy_count)

            if not check_rate_limit(client_ip):
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please wait a minute before making more requests."
                )

        return await call_next(request)
