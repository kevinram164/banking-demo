# Observability: Prometheus, Grafana, OpenTelemetry, Jaeger

Dự án banking-demo đã được gắn **metrics** (Prometheus) và **tracing** (OpenTelemetry → Jaeger). Có thể xem **dashboard** và **traces** trên Grafana và Jaeger UI.

## Kiến trúc

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Banking Services (auth, account, transfer, notification)                │
│  - Expose /metrics (Prometheus format)                                   │
│  - Send traces via OTLP gRPC → OpenTelemetry Collector                   │
└───────────────┬─────────────────────────────────┬───────────────────────┘
                │                                 │
                │ scrape /metrics                 │ OTLP (traces)
                ▼                                 ▼
┌───────────────────────┐           ┌─────────────────────────────┐
│  Prometheus           │           │  OpenTelemetry Collector    │
│  (metrics storage)    │           │  (batch, forward)           │
└───────────┬───────────┘           └──────────────┬──────────────┘
            │                                      │
            │                                      ▼
            │                          ┌─────────────────────────────┐
            │                          │  Jaeger                     │
            │                          │  (trace storage + UI)       │
            │                          └─────────────────────────────┘
            │
            ▼
┌───────────────────────┐
│  Grafana              │
│  - Prometheus (metrics)
│  - Jaeger (traces)    │
└───────────────────────┘
```

## Thư mục K8s monitoring

| File | Mô tả |
|------|--------|
| `k8s/monitoring/namespace.yaml` | Namespace `monitoring` |
| `k8s/monitoring/prometheus-configmap.yaml` | Cấu hình scrape các service trong `banking` |
| `k8s/monitoring/prometheus.yaml` | Deployment + Service Prometheus |
| `k8s/monitoring/otel-collector-config.yaml` | Config OTel Collector (OTLP → Jaeger) |
| `k8s/monitoring/otel-collector.yaml` | Deployment + Service OpenTelemetry Collector |
| `k8s/monitoring/jaeger.yaml` | Jaeger all-in-one (nhận OTLP, lưu trace, UI) |
| `k8s/monitoring/grafana-datasources.yaml` | Datasource Prometheus + Jaeger cho Grafana |
| `k8s/monitoring/grafana-dashboard-provider.yaml` | Provisioning dashboards |
| `k8s/monitoring/grafana-dashboard-banking.yaml` | Dashboard mẫu Banking Services |
| `k8s/monitoring/grafana.yaml` | Deployment + Service Grafana |
| `k8s/monitoring/ingress.yaml` | Ingress Grafana, Jaeger, Prometheus (host: grafana/jaeger/prometheus.banking.local) |

## Code instrumentation

- **common/observability.py**: Khởi tạo tracing (OTLP) + metrics (Prometheus), middleware đếm request/latency, route `/metrics`.
- **common/requirements.txt**: Thêm `prometheus_client`, `opentelemetry-*`, `opentelemetry-instrumentation-fastapi`.
- Mỗi service gọi `instrument_fastapi(app, "tên-service")` → tự động có tracing và `/metrics`.

**Metrics hiện có:**

- `http_requests_total{method, endpoint, status}` – số request theo method, path, status.
- `http_request_duration_seconds` – histogram latency theo method, endpoint.

**Tracing:** FastAPI được instrument bằng OpenTelemetry; mỗi request tạo span, gửi qua OTLP tới Collector → Jaeger.

## Deploy stack monitoring lên K8s

1. **Đảm bảo đã deploy banking app** (namespace `banking`, các service có `/metrics`).

2. **Apply monitoring** (theo thứ tự):

```bash
# Namespace
kubectl apply -f k8s/monitoring/namespace.yaml

# OTel Collector & Jaeger (trước để app gửi trace được)
kubectl apply -f k8s/monitoring/otel-collector-config.yaml
kubectl apply -f k8s/monitoring/jaeger.yaml
kubectl apply -f k8s/monitoring/otel-collector.yaml

# Prometheus
kubectl apply -f k8s/monitoring/prometheus-configmap.yaml
kubectl apply -f k8s/monitoring/prometheus.yaml

# Grafana (datasources + dashboards + server)
kubectl apply -f k8s/monitoring/grafana-datasources.yaml
kubectl apply -f k8s/monitoring/grafana-dashboard-provider.yaml
kubectl apply -f k8s/monitoring/grafana-dashboard-banking.yaml
kubectl apply -f k8s/monitoring/grafana.yaml
kubectl apply -f k8s/monitoring/ingress.yaml
```

Hoặc apply cả thư mục:

```bash
kubectl apply -f k8s/monitoring/
```

3. **Biến môi trường cho app:** Các Deployment trong `banking` đã có `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.monitoring.svc.cluster.local:4317`. Rebuild và redeploy image app nếu bạn vừa thêm instrumentation.

## Truy cập UI (qua Ingress)

Sau khi apply **k8s/monitoring/ingress.yaml** và thêm host (xem [K8S_DEPLOY.md](K8S_DEPLOY.md)), truy cập qua Ingress:

| UI        | URL | Ghi chú |
|-----------|-----|--------|
| **Grafana**   | http://grafana.banking.local | Login: `admin` / `admin`. Explore → Prometheus hoặc Jaeger. |
| **Prometheus**| http://prometheus.banking.local | Query: `rate(http_requests_total[5m])`. |
| **Jaeger**    | http://jaeger.banking.local | Chọn service (auth-service, …) và tìm trace. |

Thêm vào `/etc/hosts` (thay `<INGRESS_IP>` bằng IP Ingress, ví dụ `minikube ip`):

```
<INGRESS_IP> grafana.banking.local jaeger.banking.local prometheus.banking.local
```

Nếu không dùng Ingress, có thể dùng port-forward: `kubectl -n monitoring port-forward svc/grafana 3000:3000` rồi mở http://localhost:3000 (tương tự cho prometheus:9090, jaeger:16686).

## Chạy với Docker Compose (optional)

Nếu chạy app bằng Docker Compose, tracing chỉ hoạt động khi có OTel Collector (và Jaeger) cùng mạng. Đặt biến môi trường cho từng service:

- `OTEL_EXPORTER_OTLP_ENDPOINT=http://<host-otel-collector>:4317`

Và chạy thêm container OTel Collector + Jaeger (có thể thêm vào `docker-compose.yml` nếu cần).

## Tắt tracing

Để tắt gửi trace (chỉ giữ metrics): xóa hoặc để trống biến môi trường `OTEL_EXPORTER_OTLP_ENDPOINT` trong Deployment. Ứng dụng vẫn expose `/metrics` bình thường.
