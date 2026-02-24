import hashlib
import json
import logging
import os
import time
import traceback
import uuid
from typing import Any, Dict


def mask_amount(amount: int | float) -> str:
    """Hash amount for logs — không ghi số tiền thật để bảo mật."""
    secret = os.getenv("LOG_AMOUNT_SECRET", "banking-demo-default")
    h = hashlib.sha256(f"{amount}:{secret}".encode()).hexdigest()
    return f"amt:{h[:12]}"

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


def get_json_logger(service_name: str) -> logging.Logger:
    logger = logging.getLogger(service_name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload: Dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "event": event,
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False))


def log_error_event(logger: logging.Logger, event: str, exc: Exception | None = None, **fields: Any) -> None:
    """Log error event at ERROR level with optional traceback."""
    payload: Dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "event": event,
        "level": "error",
        **fields,
    }
    if exc is not None:
        payload["error"] = str(exc)
        payload["error_type"] = type(exc).__name__
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        payload["traceback"] = "".join(tb).replace("\n", "\\n")
    logger.error(json.dumps(payload, ensure_ascii=False))


class RequestLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger: logging.Logger, service_name: str) -> None:
        super().__init__(app)
        self.logger = logger
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
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
