# Exporters — Redis & PostgreSQL cho Prometheus

Các exporter này chạy trong namespace `banking` và expose metrics để Prometheus (trong namespace `monitoring`) scrape qua `additionalScrapeConfigs` đã cấu hình trong `helm-monitoring/values-kube-prometheus-stack.yaml`.

## Yêu cầu

- Redis và PostgreSQL đã chạy trong namespace `banking` (từ phase2 banking-demo).
- Secret `banking-db-secret` tồn tại (cho postgres-exporter).

## Cài đặt

```bash
kubectl apply -f redis-exporter.yaml
kubectl apply -f postgres-exporter.yaml
```

Kiểm tra:

```bash
kubectl get pods,svc -n banking -l 'app in (redis-exporter,postgres-exporter)'
```

## Scrape targets (từ Prometheus trong monitoring)

| Job       | Target                                              |
|----------|------------------------------------------------------|
| redis    | `redis-exporter.banking.svc.cluster.local:9121`      |
| postgres | `postgres-exporter.banking.svc.cluster.local:9187`   |

Sau khi cài **Kube Prometheus Stack** với `values-kube-prometheus-stack.yaml`, Prometheus sẽ tự scrape hai job trên (không cần ServiceMonitor).

## Troubleshooting — Dashboard "No data"

Khi Redis / PostgreSQL dashboard trong Grafana hiện "No data", kiểm tra theo thứ tự:

### 1. Exporters đang chạy

```bash
kubectl get pods -n banking -l 'app in (redis-exporter,postgres-exporter)'
# Cả hai phải Running
```

### 2. Metrics có sẵn trực tiếp từ exporter

```bash
kubectl -n banking port-forward svc/redis-exporter 9121:9121
# Trên máy khác: curl http://localhost:9121/metrics | head -20

kubectl -n banking port-forward svc/postgres-exporter 9187:9187
# curl http://localhost:9187/metrics | head -20
```

### 3. Prometheus có scrape được không

Vào Prometheus UI → Status → Targets. Tìm job `redis` và `postgres` — phải **UP**.

Hoặc query thử trong Prometheus:

```
redis_up
pg_up
```

Nếu có kết quả → Prometheus đã scrape OK; vấn đề có thể là biến (variable) trong dashboard.

### 4. Biến dashboard (namespace, instance)

Một số dashboard dùng dropdown **namespace** / **instance**. Nếu không chọn đúng giá trị → "No data".

- Thử chọn **instance = All** hoặc giá trị tương ứng (redis, postgres).
- Hoặc vào Edit dashboard → Variables → kiểm tra query có khớp với labels trong Prometheus không.

### 5. Postgres-exporter: Secret và quyền

Nếu postgres-exporter CrashLoopBackOff hoặc không kết nối được DB:

```bash
kubectl -n banking logs deploy/postgres-exporter --tail=30
```

Đảm bảo `banking-db-secret` có đủ `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`.

---

## Lưu ý

- **postgres-exporter**: Dùng `banking-db-secret` (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB). Nếu mật khẩu có ký tự đặc biệt, có thể cần tạo Secret riêng chứa `DATA_SOURCE_NAME` và dùng `envFrom` thay vì command build URI.
- **redis-exporter**: Kết nối tới `redis.banking.svc.cluster.local:6379` (headless service Redis).
