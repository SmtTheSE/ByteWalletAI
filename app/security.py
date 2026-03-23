"""
app/security.py

Production security utilities:
- API Key authentication
- Rate limiting with SlowAPI
- CORS origin validation
"""
from __future__ import annotations
import time
from typing import Callable, Optional
from functools import wraps

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

# HTTP Bearer scheme for API key extraction
security_bearer = HTTPBearer(auto_error=False)


class RateLimitExceeded(HTTPException):
    """Custom exception for rate limit violations."""
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


class APIKeyAuth:
    """
    API Key authentication handler.
    
    Validates X-API-Key header against configured allowed keys.
    Skips validation if API_AUTH_ENABLED is not set (dev mode).
    """
    
    async def __call__(self, request: Request) -> Optional[str]:
        """Validate API key from request headers."""
        # Skip auth if not enabled (dev mode)
        if not settings.api_auth_enabled:
            return None
        
        # Get API key from header
        api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required. Include X-API-Key header.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if api_key not in settings.api_keys_list:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key.",
            )
        
        return api_key


class SimpleRateLimiter:
    """
    In-memory rate limiter.
    
    Tracks requests per client (IP + API key if available).
    Cleans expired entries automatically.
    
    For production at scale, replace with Redis-based limiter.
    """
    
    def __init__(self):
        self._requests: dict[str, list[float]] = {}
        self._window_seconds = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
        }
    
    def _get_window_seconds(self, period: str) -> int:
        """Convert period string to seconds."""
        return self._window_seconds.get(period.lower(), 60)
    
    def _get_client_id(self, request: Request) -> str:
        """Generate unique client identifier."""
        # Prefer API key if available, fallback to IP
        api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key", "")
        client_ip = request.client.host if request.client else "unknown"
        return f"{client_ip}:{api_key}" if api_key else client_ip
    
    def is_allowed(self, request: Request, limit: int, period: str) -> tuple[bool, dict]:
        """
        Check if request is within rate limit.
        
        Returns:
            Tuple of (allowed: bool, headers: dict with rate limit info)
        """
        window = self._get_window_seconds(period)
        client_id = self._get_client_id(request)
        now = time.time()
        
        # Clean old entries
        if client_id in self._requests:
            self._requests[client_id] = [
                ts for ts in self._requests[client_id] 
                if now - ts < window
            ]
        else:
            self._requests[client_id] = []
        
        current_count = len(self._requests[client_id])
        
        # Build rate limit headers
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(0, limit - current_count - 1)),
            "X-RateLimit-Window": str(window),
        }
        
        # Check if over limit
        if current_count >= limit:
            return False, headers
        
        # Record this request
        self._requests[client_id].append(now)
        return True, headers
    
    def cleanup_old_entries(self, max_age_seconds: int = 3600):
        """Remove entries older than max_age_seconds."""
        now = time.time()
        to_remove = []
        for client_id, timestamps in self._requests.items():
            self._requests[client_id] = [
                ts for ts in timestamps 
                if now - ts < max_age_seconds
            ]
            if not self._requests[client_id]:
                to_remove.append(client_id)
        for client_id in to_remove:
            del self._requests[client_id]


# Global rate limiter instance
rate_limiter = SimpleRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to apply rate limiting to all requests.
    
    Skips rate limiting for health check endpoints.
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Skip rate limiting for health checks
        if request.url.path in ["/", "/health"]:
            return await call_next(request)
        
        limit, period = settings.rate_limit_parts
        allowed, headers = rate_limiter.is_allowed(request, limit, period)
        
        if not allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers=headers,
            )
        
        response = await call_next(request)
        
        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value
        
        return response


# Dependencies for FastAPI routes
async def verify_api_key(request: Request) -> Optional[str]:
    """Dependency to verify API key on protected routes."""
    auth = APIKeyAuth()
    return await auth(request)


def require_api_key() -> Callable:
    """
    Factory to create a dependency that requires API key authentication.
    
    Usage:
        @router.post("/v1/predict-burn-rate", dependencies=[require_api_key()])
    """
    async def _check_auth(request: Request) -> str:
        auth = APIKeyAuth()
        result = await auth(request)
        if result is None and settings.api_auth_enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key validation failed.",
            )
        return result or ""
    return _check_auth
