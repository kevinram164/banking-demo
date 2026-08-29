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


def mask_account_number(account: str) -> str:
    """Che STK: 4 số đầu + **** + 2 số cuối. VD: 123456789012 -> 1234****9012."""
    s = (account or "").strip()
    if len(s) <= 6:
        return "*" * min(4, len(s)) if s else "******"
    return f"{s[:4]}****{s[-2:]}"

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


def should_log_request_flow() -> bool:
    """Bật/tắt log chi tiết flow (RabbitMQ, Redis, request). Lab: false."""
    return os.getenv("LOG_REQUEST_FLOW", "false").lower() in ("true", "1", "yes")


def should_log_transfer_json() -> bool:
    """JSON chi tiết transfer (Loki). Mặc định tắt — dùng log_transfer one-liner."""
    return os.getenv("LOG_TRANSFER_JSON", "false").lower() in ("true", "1", "yes")


_PROBE_ACCESS_MARKERS = (
    '"GET /health ',
    '"HEAD /health ',
    '"GET /metrics ',
    '"GET /api/health ',
)


class _HideProbeAccessLog(logging.Filter):
    """Lọc dòng uvicorn access log từ kube-probe / Prometheus scrape."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(m in msg for m in _PROBE_ACCESS_MARKERS)


def silence_http_probe_logs() -> None:
    """
    Tắt log GET /health, /metrics trong stdout (uvicorn access logger).
    Probe K8s vẫn chạy bình thường — chỉ không in ra log ứng dụng.
    SILENCE_PROBE_ACCESS_LOGS=false hoặc UVICORN_ACCESS_LOG=on để bật lại.
    """
    if os.getenv("SILENCE_PROBE_ACCESS_LOGS", "true").lower() not in ("true", "1", "yes"):
        return
    flt = _HideProbeAccessLog()
    for name in ("uvicorn.access", "uvicorn"):
        logging.getLogger(name).addFilter(flt)
    if os.getenv("UVICORN_ACCESS_LOG", "off").lower() in ("off", "0", "false", "no"):
        access = logging.getLogger("uvicorn.access")
        access.disabled = True
        access.propagate = False


def format_vnd(amount: int | float) -> str:
    return f"{int(amount):,}".replace(",", ".") + "đ"


def log_transfer(
    logger: logging.Logger,
    *,
    outcome: str,
    transfer_id: int | None = None,
    txn_type: str = "P2P",
    amount: int | None = None,
    sender: str = "",
    receiver: str = "",
    note: str | None = None,
    error_code: str | None = None,
    detail: str | None = None,
    extra: str | None = None,
) -> None:
    """Một dòng dễ đọc cho lifecycle giao dịch (lab tail -f logs)."""
    if os.getenv("LOG_TRANSFER_PRETTY", "true").lower() not in ("true", "1", "yes"):
        return
    parts = [f"[transfer] {outcome}"]
    if transfer_id is not None:
        parts.append(f"id={transfer_id}")
    if txn_type:
        parts.append(txn_type)
    if amount is not None:
        parts.append(format_vnd(amount))
    if sender or receiver:
        parts.append(f"| {sender or '?'} → {receiver or '?'}")
    if note:
        parts.append(f"| {note}")
    if error_code:
        parts.append(f"| {error_code}")
    if detail:
        parts.append(f"— {detail}")
    if extra:
        parts.append(f"| {extra}")
    logger.info(" ".join(parts))


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
        if corr_id := response.headers.get("X-Correlation-Id"):
            payload["correlation_id"] = corr_id
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
