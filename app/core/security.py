import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import Settings

logger = logging.getLogger("zhaoxingzhai.request")


class InMemoryRateLimiter:
    """Process-local limiter suitable for one-instance deployments.

    Replace this with Redis before running multiple backend replicas.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        current = now if now is not None else time.monotonic()
        cutoff = current - self.window_seconds
        entries = self._requests[key]
        while entries and entries[0] <= cutoff:
            entries.popleft()
        if len(entries) >= self.limit:
            retry_after = max(1, int(self.window_seconds - (current - entries[0])))
            return False, retry_after
        entries.append(current)
        return True, 0


class ApiProtectionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self.limiter = InMemoryRateLimiter(
            settings.app_rate_limit_requests,
            settings.app_rate_limit_window_seconds,
        )
        self.auth_limiter = InMemoryRateLimiter(10, 60)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = self._request_id(request)
        request.state.request_id = request_id
        started = time.monotonic()

        protected_paths = {
            "/api/v1/interpret",
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/auth/request-email-verification",
            "/api/v1/auth/confirm-email",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/avatar",
            "/api/v1/auth/me",
        }
        if request.url.path in protected_paths:
            max_bytes = (
                self.settings.app_avatar_max_bytes + 65536
                if request.url.path == "/api/v1/auth/avatar"
                else self.settings.app_max_request_bytes
            )
            too_large = self._request_too_large(request, max_bytes)
            if too_large:
                return self._error(413, "请求内容过大", request_id)

            limiter = self.limiter if request.url.path == "/api/v1/interpret" else self.auth_limiter
            allowed, retry_after = limiter.allow(self._client_key(request))
            if not allowed:
                response = self._error(429, "请求过于频繁，请稍后再试", request_id)
                response.headers["Retry-After"] = str(retry_after)
                return response

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            raise

        response.headers["X-Request-ID"] = request_id
        elapsed_ms = round((time.monotonic() - started) * 1000)
        # Do not log query strings, bodies, authorization headers, or AI keys.
        logger.info(
            "request_complete request_id=%s method=%s path=%s status=%s elapsed_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    def _client_key(self, request: Request) -> str:
        if self.settings.app_trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            if forwarded:
                return forwarded
        return request.client.host if request.client else "unknown"

    def _request_too_large(self, request: Request, max_bytes: int) -> bool:
        raw_length = request.headers.get("content-length")
        if not raw_length:
            return False
        try:
            return int(raw_length) > max_bytes
        except ValueError:
            return True

    @staticmethod
    def _request_id(request: Request) -> str:
        supplied = request.headers.get("x-request-id", "").strip()
        if supplied and len(supplied) <= 128 and supplied.isascii():
            return supplied
        return uuid.uuid4().hex

    @staticmethod
    def _error(status_code: int, message: str, request_id: str) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={"detail": message, "requestId": request_id},
            headers={"X-Request-ID": request_id},
        )
