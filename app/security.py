import time
from typing import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

# In-memory IP rate limiter: {ip: [timestamp, timestamp, ...]}
_IP_REQUEST_LOG: dict[str, list[float]] = {}
MAX_REQUEST_BODY_BYTES = 1024 * 1024  # 1 MB


def check_rate_limit(client_ip: str) -> bool:
    """
    Sliding window rate limiter: allows up to settings.rate_limit_per_min requests per minute.
    """
    now = time.time()
    window_start = now - 60.0
    limit = settings.rate_limit_per_min

    timestamps = _IP_REQUEST_LOG.get(client_ip, [])
    # Filter out requests older than 1 minute
    recent = [t for t in timestamps if t > window_start]

    if len(recent) >= limit:
        _IP_REQUEST_LOG[client_ip] = recent
        return False

    recent.append(now)
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
            client_ip = request.client.host if request.client else "127.0.0.1"
            # Trust forward headers if provided
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()

            if not check_rate_limit(client_ip):
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please wait a minute before making more requests."
                )

        return await call_next(request)
