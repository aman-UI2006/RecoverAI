"""
RecoverAI - Core HTTP Middleware Components (Step 24)
"""

import time
import uuid
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware attaching request trace ID (X-Trace-ID) to requests and responses."""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        request.state.trace_id = trace_id

        start_time = time.perf_counter()
        response: Response = await call_next(request)
        process_time_ms = (time.perf_counter() - start_time) * 1000

        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Process-Time-MS"] = f"{process_time_ms:.2f}"

        logger.info(
            f"Method={request.method} Path={request.url.path} "
            f"Status={response.status_code} TraceID={trace_id} Time={process_time_ms:.2f}ms"
        )
        return response
