"""
Observability: OpenTelemetry tracing + logs + Prometheus metrics.
- Tracing/Logs: OTLP export to collector (optional via OTEL_EXPORTER_OTLP_ENDPOINT).
- Metrics: Prometheus /metrics endpoint.
- Heartbeat: periodic SERVER span so services stay visible without traffic.
- RMQ: W3C tracecontext inject/extract so producer → consumer = one APM trace.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import nullcontext
from typing import Any, Mapping

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CollectorRegistry

_metrics_registry: CollectorRegistry | None = None
_request_count: Counter | None = None
_request_latency: Histogram | None = None
_transfer_outcomes: Counter | None = None
_transfers_pending: Gauge | None = None
_heartbeat_started: set[str] = set()
_otel_resource_cache = None
_logs_provider = None
_tracing_ready = False


def _otel_endpoint() -> str:
    return os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()


def _otel_service_name(service_name: str) -> str:
    return os.getenv("OTEL_SERVICE_NAME", service_name).strip() or service_name


def _get_otel_resource(service_name: str):
    """Shared Resource for traces + logs (honours OTEL_RESOURCE_ATTRIBUTES)."""
    global _otel_resource_cache
    if _otel_resource_cache is not None:
        return _otel_resource_cache
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

    _otel_resource_cache = Resource.create({SERVICE_NAME: _otel_service_name(service_name)})
    return _otel_resource_cache


def init_tracing(service_name: str) -> None:
    """Initialize OpenTelemetry tracer; export to OTLP if OTEL_EXPORTER_OTLP_ENDPOINT is set."""
    global _tracing_ready
    if _tracing_ready:
        return
    endpoint = _otel_endpoint()
    if not endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
        from opentelemetry.baggage.propagation import W3CBaggagePropagator

        provider = TracerProvider(resource=_get_otel_resource(service_name))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(insecure=True)))
        trace.set_tracer_provider(provider)
        set_global_textmap(
            CompositePropagator([TraceContextTextMapPropagator(), W3CBaggagePropagator()])
        )
        _tracing_ready = True

        try:
            from opentelemetry.instrumentation.redis import RedisInstrumentor
            RedisInstrumentor().instrument()
        except Exception:
            pass

        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            from common import db
            if getattr(db, "engine", None):
                SQLAlchemyInstrumentor().instrument(engine=db.engine)
        except Exception:
            pass
    except Exception:
        pass


def init_logging(service_name: str) -> None:
    """
    OTLP logs → collector → Instana/APM (all levels the app logger emits).
    Disable: OTEL_LOGS=0. Logger level: LOG_LEVEL (default INFO → INFO/WARN/ERROR/CRITICAL;
    set LOG_LEVEL=DEBUG for DEBUG too).
    """
    global _logs_provider
    if _logs_provider is not None:
        return
    if not _otel_endpoint():
        return
    if os.getenv("OTEL_LOGS", "1").strip().lower() in ("0", "false", "no", "off"):
        return
    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

        provider = LoggerProvider(resource=_get_otel_resource(service_name))
        provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(insecure=True))
        )
        set_logger_provider(provider)
        _logs_provider = provider
    except Exception:
        _logs_provider = None


def attach_otlp_log_handler(logger: logging.Logger) -> None:
    """Forward every record accepted by `logger` to OTLP (no extra level filter)."""
    if _logs_provider is None:
        return
    if any(getattr(h, "_otel_otlp_logs", False) for h in logger.handlers):
        return
    try:
        from opentelemetry.sdk._logs import LoggingHandler

        # NOTSET = do not filter; logger.setLevel(LOG_LEVEL) decides which levels flow.
        handler = LoggingHandler(level=logging.NOTSET, logger_provider=_logs_provider)
        handler._otel_otlp_logs = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    except Exception:
        pass


def get_tracer(service_name: str):
    """Get tracer for manual spans. Returns None if tracing not initialized."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(service_name, "1.0")
    except Exception:
        return None


def current_trace_fields() -> dict[str, str]:
    """Fields for Kibana log↔trace correlation (`trace.id`, `span.id`)."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if not ctx or not ctx.is_valid:
            return {}
        return {
            "trace.id": format(ctx.trace_id, "032x"),
            "span.id": format(ctx.span_id, "016x"),
        }
    except Exception:
        return {}


def set_span_attributes(**attrs: Any) -> None:
    """Attach business attributes onto the current span (skip None)."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if not span or not span.is_recording():
            return
        for key, value in attrs.items():
            if value is None or value == "":
                continue
            if isinstance(value, (bool, int, float, str)):
                span.set_attribute(key, value)
            else:
                span.set_attribute(key, str(value))
    except Exception:
        pass


def _carrier_from_headers(headers: Mapping[str, Any] | None) -> dict[str, str]:
    if not headers:
        return {}
    out: dict[str, str] = {}
    for key, value in headers.items():
        k = key.decode("utf-8", "replace") if isinstance(key, (bytes, bytearray)) else str(key)
        if isinstance(value, (bytes, bytearray)):
            v = value.decode("utf-8", "replace")
        else:
            v = str(value)
        out[k] = v
    return out


def inject_trace_headers(headers: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inject W3C traceparent/tracestate into a mutable header dict (RMQ / HTTP)."""
    carrier: dict[str, Any] = dict(headers or {})
    try:
        from opentelemetry.propagate import inject

        inject(carrier)
    except Exception:
        pass
    return carrier


def extract_trace_context(headers: Mapping[str, Any] | None):
    """Extract remote parent context from RMQ/HTTP headers."""
    try:
        from opentelemetry.propagate import extract

        return extract(_carrier_from_headers(headers))
    except Exception:
        try:
            from opentelemetry import context as otel_context

            return otel_context.get_current()
        except Exception:
            return None


def start_heartbeat(service_name: str) -> None:
    """Periodic SERVER span so Instana/APM keeps the service visible without traffic."""
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip():
        return
    if os.getenv("OTEL_HEARTBEAT", "1").strip().lower() in ("0", "false", "no", "off"):
        return
    if service_name in _heartbeat_started:
        return
    _heartbeat_started.add(service_name)
    try:
        interval = max(10, int(os.getenv("OTEL_HEARTBEAT_SECONDS", "30")))
    except ValueError:
        interval = 30
    tracer = get_tracer(service_name)
    if not tracer:
        return

    def _loop() -> None:
        from opentelemetry.trace import SpanKind, Status, StatusCode

        while True:
            try:
                with tracer.start_as_current_span(
                    "otel.heartbeat",
                    kind=SpanKind.SERVER,
                    attributes={"heartbeat": True, "http.route": "/__heartbeat__"},
                ) as span:
                    span.set_status(Status(StatusCode.OK))
            except Exception:
                pass
            time.sleep(interval)

    threading.Thread(target=_loop, name=f"otel-hb-{service_name}", daemon=True).start()


def consumer_span(
    tracer,
    name: str,
    attributes: dict | None = None,
    carrier: Mapping[str, Any] | None = None,
):
    """
    Start a messaging CONSUMER span.
    If `carrier` (RMQ headers) has traceparent, span joins the producer HTTP trace.
    """
    if not tracer:
        return nullcontext()
    from opentelemetry.trace import SpanKind

    attrs = {
        "messaging.system": "rabbitmq",
        "messaging.operation": "process",
    }
    if attributes:
        attrs.update({k: v for k, v in attributes.items() if v is not None})

    parent = extract_trace_context(carrier) if carrier is not None else None
    if parent is not None:
        return tracer.start_as_current_span(
            name, context=parent, kind=SpanKind.CONSUMER, attributes=attrs
        )
    return tracer.start_as_current_span(name, kind=SpanKind.CONSUMER, attributes=attrs)


def producer_span(tracer, name: str, attributes: dict | None = None):
    """PRODUCER span around RMQ publish (child of current HTTP span)."""
    if not tracer:
        return nullcontext()
    from opentelemetry.trace import SpanKind

    attrs = {
        "messaging.system": "rabbitmq",
        "messaging.operation": "publish",
    }
    if attributes:
        attrs.update({k: v for k, v in attributes.items() if v is not None})
    return tracer.start_as_current_span(name, kind=SpanKind.PRODUCER, attributes=attrs)


def setup_metrics(service_name: str) -> None:
    global _metrics_registry, _request_count, _request_latency, _transfer_outcomes, _transfers_pending
    _metrics_registry = CollectorRegistry()
    _request_count = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
        registry=_metrics_registry,
    )
    _request_latency = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency",
        ["method", "endpoint"],
        registry=_metrics_registry,
    )
    _transfer_outcomes = Counter(
        "banking_transfer_outcomes_total",
        "Banking transfer business outcomes (not HTTP status)",
        ["outcome", "txn_type"],
        registry=_metrics_registry,
    )
    _transfers_pending = Gauge(
        "banking_transfers_pending",
        "Current open PENDING transfers (hold chưa settle)",
        registry=_metrics_registry,
    )


def inc_transfer_outcome(outcome: str, txn_type: str | None = None) -> None:
    """outcome: success | failed | pending | expired | cancelled"""
    c = _transfer_outcomes
    if not c:
        return
    o = (outcome or "failed").strip().lower()
    tt = (txn_type or "UNKNOWN").strip().upper() or "UNKNOWN"
    try:
        c.labels(outcome=o, txn_type=tt).inc()
    except Exception:
        pass


def set_transfers_pending(count: int) -> None:
    g = _transfers_pending
    if not g:
        return
    try:
        g.set(max(0, int(count)))
    except Exception:
        pass


def adjust_transfers_pending(delta: int) -> None:
    g = _transfers_pending
    if not g:
        return
    try:
        g.inc(int(delta))
    except Exception:
        pass


def get_metrics_content() -> bytes:
    if _metrics_registry is None:
        return b""
    return generate_latest(_metrics_registry)


def instrument_fastapi(app, service_name: str) -> None:
    from common.logging_utils import get_json_logger, silence_http_probe_logs

    silence_http_probe_logs()
    init_tracing(service_name)
    init_logging(service_name)
    # Ensure OTLP log handler even if get_json_logger ran before init_logging.
    attach_otlp_log_handler(get_json_logger(service_name))
    setup_metrics(service_name)
    start_heartbeat(service_name)
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health,/metrics,/docs,/openapi.json,/redoc",
        )
    except Exception:
        pass

    from fastapi import Response
    from starlette.middleware.base import BaseHTTPMiddleware

    class PrometheusMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path in ("/metrics", "/health", "/__heartbeat__"):
                return await call_next(request)
            start = time.perf_counter()
            response = await call_next(request)
            duration = time.perf_counter() - start
            c, h = _request_count, _request_latency
            if c and h:
                endpoint = request.url.path or "/"
                c.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
                h.labels(method=request.method, endpoint=endpoint).observe(duration)
            return response

    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics")
    async def metrics():
        return Response(content=get_metrics_content(), media_type="text/plain; charset=utf-8")
