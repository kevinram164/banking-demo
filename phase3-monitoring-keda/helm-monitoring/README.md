# Helm Monitoring — Prometheus, Grafana, Loki, OpenTelemetry, Tempo

Triển khai **monitoring** (Prometheus + Grafana), **logging** (Loki + Promtail), **tracing** (OpenTelemetry Collector + Tempo) bằng Helm. Pull chart về, chỉnh config trong các file `values-*.yaml` rồi `helm install/upgrade` với `-f values-*.yaml`.

---

## Helm repos

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update
```

---

## Thứ tự cài đặt

Tất cả cài vào namespace `monitoring`. Tạo namespace trước (hoặc `--create-namespace`).

1. **Kube Prometheus Stack** (Prometheus + Grafana + Alertmanager + operator)
2. **Loki** (logging backend)
3. **Promtail** (log shipper → Loki)
4. **Tempo** (tracing backend, nhẹ hơn Jaeger)
5. **OpenTelemetry Collector** (nhận OTLP từ app → export traces sang Tempo)

Sau khi cài xong, chỉnh **Grafana** `additionalDataSources` (Loki, Tempo) trong `values-kube-prometheus-stack.yaml` nếu chưa trỏ đúng URL, rồi upgrade.

---

## 1. Kube Prometheus Stack (Prometheus + Grafana)

- **Chart:** `prometheus-community/kube-prometheus-stack`
- **Values:** `values-kube-prometheus-stack.yaml`
  - Namespace `monitoring`
  - `additionalScrapeConfigs` cho banking services (auth, account, transfer, notification) **và** Kong, Redis, PostgreSQL:
    - **Kong:** `kong.banking.svc.cluster.local:8001/metrics` (cần bật Prometheus plugin trong Kong — đã cấu hình trong phase2 `kong.globalPlugins`).
    - **Redis:** qua `redis-exporter` trong namespace banking (xem `phase3-monitoring-keda/exporters/`).
    - **PostgreSQL:** qua `postgres-exporter` trong namespace banking (xem `phase3-monitoring-keda/exporters/`).
  - Grafana `additionalDataSources`: Loki, Tempo (sửa URL nếu release khác; kiểm tra `kubectl get svc -n monitoring`).
  - Có thể bật Ingress cho Grafana/Prometheus (tùy cluster)

```bash
kubectl create namespace monitoring
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring \
  -f values-kube-prometheus-stack.yaml
```

---

## 2. Loki (logging)

- **Chart:** `grafana/loki`
- **Values:** `values-loki.yaml`
  - Deploy dạng single binary (hoặc simple scalable tùy chỉnh)
  - Persistence dùng PVC; có thể set `storageClassName: nfs-client` nếu dùng NFS

```bash
helm upgrade --install loki grafana/loki -n monitoring -f values-loki.yaml
```

---

## 3. Promtail (log shipper → Loki)

- **Chart:** `grafana/promtail`
- **Values:** `values-promtail.yaml`
  - Trỏ `clients` tới Loki URL (ví dụ `http://loki-gateway.monitoring.svc.cluster.local`)
  - Thu thập log pod trong cluster (default), có thể giới hạn namespace/label

```bash
helm upgrade --install promtail grafana/promtail -n monitoring -f values-promtail.yaml
```

---

## 4. Tempo (tracing)

- **Chart:** `grafana/tempo`
- **Values:** `values-tempo.yaml`
  - Nhẹ hơn Jaeger, tích hợp tốt với Grafana
  - Nhận OTLP gRPC (4317) và HTTP (4318)
  - Storage local (filesystem), persistence bật sẵn

```bash
helm upgrade --install tempo grafana/tempo -n monitoring -f values-tempo.yaml
```

---

## 5. OpenTelemetry Collector

- **Chart:** `open-telemetry/opentelemetry-collector`
- **Values:** `values-otel-collector.yaml`
  - Mode `deployment`
  - OTLP receiver (grpc 4317, http 4318) để app gửi trace
  - Export traces sang Tempo qua OTLP

```bash
helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
  -n monitoring \
  -f values-otel-collector.yaml
```

---

## Dashboard Banking Services

Có 2 bản dashboard; apply theo phase đang chạy:

| Phase | File | Ghi chú |
|-------|------|---------|
| **Phase 5** | `grafana-dashboard-banking-services.yaml` | auth/account/transfer/notification expose HTTP trực tiếp |
| **Phase 8** | `grafana-dashboard-banking-services-phase8.yaml` | api-producer nhận HTTP, RabbitMQ → consumers |

```bash
# Phase 5 (mặc định, rollback)
kubectl apply -f grafana-dashboard-banking-services.yaml

# Phase 8
kubectl apply -f grafana-dashboard-banking-services-phase8.yaml
```

Grafana sidecar load ConfigMap có label `grafana_dashboard=1`. Vào Grafana → Dashboards → **Banking Services**.

Dashboard gồm:
- **Request Rate (RPS)** theo từng service
- **P95 Latency** theo từng service
- **Error Rate (5xx)** theo từng service
- **Stat panels** RPS cho từng service
- **Request Rate by Endpoint** (Auth)
- **Request Rate by Status Code**
- **Transfer** — tỷ lệ thành công / thất bại

Yêu cầu: Prometheus đã scrape `/metrics` (đã cấu hình trong `additionalScrapeConfigs`). Phase 5: auth/account/transfer/notification :8001-8004. Phase 8: api-producer :8080.

---

## Dashboard RabbitMQ (Phase 8)

```bash
kubectl apply -f grafana-dashboard-rabbitmq.yaml
```

Yêu cầu:
- RabbitMQ Helm chart (Bitnami) với `metrics.enabled: true` (port 9419).
- Prometheus scrape job `rabbitmq` (đã cấu hình trong `values-kube-prometheus-stack.yaml`).

Dashboard gồm: Queues, Consumers, Connections, Channels, Messages Ready/Unacked, Message Rate (Published/Delivered), Memory, Disk Space, File Descriptors.

### Dashboard không cập nhật / No data

1. **Apply lại ConfigMap và reload Grafana:**
   ```bash
   kubectl apply -f grafana-dashboard-banking-services.yaml
   kubectl rollout restart deployment -n monitoring kube-prometheus-stack-grafana
   ```
2. **Kiểm tra Prometheus scrape api-producer:**
   ```bash
   kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
   # Mở http://localhost:9090/targets — target api-producer phải "UP"
   ```
3. **Có traffic:** Dashboard cần HTTP request để có `http_requests_total`. Thử login, chuyển khoản trên frontend hoặc chạy load test (`load-test/k6-*.js`).
4. **Time range:** Dùng "Last 15 minutes" hoặc "Last 1 hour"; đảm bảo "Refresh" bật (ví dụ 10s).

---

## Lưu ý

- **Prometheus service:** KEDA ScaledObjects trỏ tới `kube-prometheus-stack-prometheus.monitoring...`. Nếu release name khác hoặc service đổi tên, sửa `serverAddress` trong từng `phase3-monitoring-keda/keda/scaledobject-*.yaml`.
- **Loki URL (Promtail / Grafana):** Thường là `loki-gateway`. Kiểm tra `kubectl get svc -n monitoring` và chỉnh `values-promtail.yaml` / Grafana datasource nếu cần.
- **Tempo URL (Grafana):** `tempo:3100` (HTTP API cho datasource).

---

## Monitoring Kong, Redis, PostgreSQL

| Thành phần | Exporter / Metrics | Grafana Dashboard |
|------------|--------------------|-------------------|
| **Kong** | Plugin `prometheus` tại Admin API `:8001/metrics` | [Kong Official 7424](https://grafana.com/grafana/dashboards/7424-kong-official/) |
| **Redis** | redis-exporter (job `redis`) | [Redis 11835](https://grafana.com/grafana/dashboards/11835-redis-dashboard-for-prometheus-redis-exporter-helm-stable-redis-ha/) |
| **PostgreSQL** | postgres-exporter (job `postgres`) | [PostgreSQL 9628](https://grafana.com/grafana/dashboards/9628-postgresql-database/) |

**Cách import dashboard:** Grafana → Dashboards → New → Import → nhập Dashboard ID (ví dụ `11835`).

- **Kong:** Đã bật global plugin `prometheus` trong phase2. Metrics tại `kong.banking.svc.cluster.local:8001/metrics`.
- **Redis:** Deploy **redis-exporter** (`kubectl apply -f exporters/redis-exporter.yaml`). Prometheus scrape `redis-exporter.banking.svc.cluster.local:9121`.
- **PostgreSQL:** Deploy **postgres-exporter** (`kubectl apply -f exporters/postgres-exporter.yaml`), dùng secret `banking-db-secret`. Prometheus scrape `postgres-exporter.banking.svc.cluster.local:9187`.

Chi tiết: xem `phase3-monitoring-keda/exporters/README.md`.

---

## App gửi trace / metrics

- **Metrics:** Prometheus scrape `/metrics` (đã cấu hình qua `additionalScrapeConfigs` cho banking services + Kong + Redis + Postgres).
- **Traces:** App set `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector-opentelemetry-collector.monitoring.svc.cluster.local:4317` và export OTLP gRPC.

Đảm bảo app trong `banking` có thể resolve được service OTEL Collector trong `monitoring`.

---

## Chỉnh config (values)

- Sửa trực tiếp các file `values-*.yaml` trong folder này.
- Sau khi sửa, chạy lại `helm upgrade --install ... -f values-*.yaml` tương ứng.
- Kiểm tra: `helm list -n monitoring`, `kubectl get pods -n monitoring`.

---

## Gợi ý truy cập UI

- **Grafana:** `kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80` → `http://localhost:3000` (user: admin, pass: admin)
- **Prometheus:** port-forward `svc/kube-prometheus-stack-prometheus 9090:9090`
- **Tempo:** Grafana → Explore → datasource Tempo (không cần port-forward Tempo riêng)

Hoặc cấu hình Ingress cho từng thành phần trong values (host, TLS, v.v.) nếu cluster đã có Ingress controller.
