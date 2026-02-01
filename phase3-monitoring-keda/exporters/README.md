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

## Lưu ý

- **postgres-exporter**: Dùng `banking-db-secret` (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB). Nếu mật khẩu có ký tự đặc biệt, có thể cần tạo Secret riêng chứa `DATA_SOURCE_NAME` và dùng `envFrom` thay vì command build URI.
- **redis-exporter**: Kết nối tới `redis.banking.svc.cluster.local:6379` (headless service Redis).
