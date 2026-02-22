import json
import logging
import os
import time
import traceback
import uuid
from typing import Any, Dict

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


def get_json_logger(service_name: str) -> logging.Logger:
    """
    Return a logger that prints plain JSON to stdout.

    - Không đụng tới cấu hình uvicorn mặc định.
    - Mỗi log line là một JSON object, dễ parse bằng Loki / Elasticsearch.
    """
    logger = logging.getLogger(service_name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    # Formatter chỉ in message (đã là JSON string)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """
    Log một sự kiện business ở dạng JSON.

    Ví dụ:
        log_event(logger, "transfer_success", from_user=1, to_user=2, amount=1000)
    """
    payload: Dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "event": event,
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False))


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Middleware ghi access log dạng JSON cho từng request."""

    def __init__(self, app, logger: logging.Logger, service_name: str) -> None:
        super().__init__(app)
        self.logger = logger
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        # Bỏ qua health/metrics để log gọn hơn
        path = request.url.path
        if path in ("/health", "/metrics"):
            return await call_next(request)

        start = time.perf_counter()

        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())

        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "event": "http_request",
            "service": self.service_name,
            "method": request.method,
            "path": path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": request.client.host if request.client else None,
            "request_id": request_id,
        }

        self.logger.info(json.dumps(payload, ensure_ascii=False))

        response.headers.setdefault("X-Request-Id", request_id)
        return response


def setup_exception_logging(app, logger: logging.Logger, service_name: str):
    """
    Gắn global exception handler vào FastAPI app.
    Mọi unhandled exception sẽ được log thành 1 JSON line duy nhất
    (thay vì multi-line traceback mặc định của uvicorn).
    """

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            raise exc

        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "event": "unhandled_exception",
            "service": service_name,
            "method": request.method,
            "path": request.url.path,
            "error": str(exc),
            "error_type": type(exc).__name__,
            "traceback": "".join(tb).replace("\n", "\\n"),
        }
        logger.error(json.dumps(payload, ensure_ascii=False))
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

