"""
Observability: OpenTelemetry tracing + Prometheus metrics.
- Tracing: OTLP export to collector (optional via OTEL_EXPORTER_OTLP_ENDPOINT).
- Metrics: Prometheus /metrics endpoint (prometheus_client).
"""
import os
from prometheus_client import Counter, Histogram, generate_latest, REGISTRY, CollectorRegistry

# Default registry with optional service label
_metrics_registry: CollectorRegistry | None = None
_request_count: Counter | None = None
_request_latency: Histogram | None = None


def setup_metrics(service_name: str) -> None:
    """Initialize Prometheus metrics for this service."""
    global _metrics_registry, _request_count, _request_latency
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


def get_request_counter():
    return _request_count


def get_request_latency():
    return _request_latency


def get_metrics_content() -> bytes:
    """Return Prometheus text format for /metrics endpoint."""
    if _metrics_registry is None:
        return b""
    return generate_latest(_metrics_registry)


def init_tracing(service_name: str) -> None:
    """Initialize OpenTelemetry tracer; export to OTLP if OTEL_EXPORTER_OTLP_ENDPOINT is set."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME

        name = os.getenv("OTEL_SERVICE_NAME", service_name).strip() or service_name
        resource = Resource.create({SERVICE_NAME: name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(insecure=True)))
        trace.set_tracer_provider(provider)
    except Exception:
        pass  # optional: tracing off if deps missing or collector unreachable


_heartbeat_started: set[str] = set()


def start_heartbeat(service_name: str) -> None:
    """Periodic SERVER span so Instana keeps the service visible without traffic."""
    import threading
    import time

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
    try:
        from opentelemetry import trace
        from opentelemetry.trace import SpanKind, Status, StatusCode

        tracer = trace.get_tracer(service_name, "1.0")
    except Exception:
        return

    def _loop() -> None:
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


def instrument_fastapi(app, service_name: str) -> None:
    """Add OpenTelemetry FastAPI auto-instrumentation, Prometheus metrics middleware, and /metrics route."""
    init_tracing(service_name)
    setup_metrics(service_name)
    start_heartbeat(service_name)

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        pass

    from fastapi import Response
    from starlette.middleware.base import BaseHTTPMiddleware
    import time

    class PrometheusMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path in ("/metrics", "/health", "/__heartbeat__"):
                return await call_next(request)
            start = time.perf_counter()
            response = await call_next(request)
            duration = time.perf_counter() - start
            c, h = get_request_counter(), get_request_latency()
            if c and h:
                endpoint = request.url.path or "/"
                c.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
                h.labels(method=request.method, endpoint=endpoint).observe(duration)
            return response

    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics")
    async def metrics():
        return Response(content=get_metrics_content(), media_type="text/plain; charset=utf-8")
