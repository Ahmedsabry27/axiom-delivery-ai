import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging.logger import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        # Ignore browser favicon requests
        if request.url.path == "/favicon.ico":
            return await call_next(request)

        # Generate Request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Request metadata
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")

        start = time.perf_counter()

        # --------------------------------------------------
        # Request Started
        # --------------------------------------------------
        logger.info(
            "request_started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": client_ip,
                "user_agent": user_agent,
            },
        )

        try:
            response = await call_next(request)

            duration = round((time.perf_counter() - start) * 1000, 2)

            response.headers["X-Request-ID"] = request_id

            response_size = response.headers.get(
                "content-length",
                "unknown",
            )

            # --------------------------------------------------
            # Request Completed
            # --------------------------------------------------
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration,
                    "response_size": response_size,
                },
            )

            return response

        except Exception:
            duration = round((time.perf_counter() - start) * 1000, 2)

            # --------------------------------------------------
            # Request Failed
            # --------------------------------------------------
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": client_ip,
                    "duration_ms": duration,
                },
            )

            raise
