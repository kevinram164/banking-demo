# KEDA — Autoscaling cho Banking Services

Scale các Deployment `auth-service`, `account-service`, `transfer-service`, `notification-service` theo **Prometheus metrics** (rate `http_requests_total`).

> **HPA theo CPU/Memory:** Nếu bạn muốn scale theo CPU và Memory thay vì Prometheus, dùng thư mục `../hpa/`. Không dùng cả KEDA và HPA cùng lúc cho cùng một deployment.

## Điều kiện

- KEDA đã cài trên cluster (operator + CRDs).
- Prometheus trong namespace `monitoring`, scrape được `/metrics` của các service trong `banking`. ScaledObjects mặc định trỏ `serverAddress` tới `kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090` (đúng khi cài `kube-prometheus-stack` với release `kube-prometheus-stack`). Nếu release hoặc tên service khác, sửa từng file `scaledobject-*.yaml`.

## Cài KEDA (nếu chưa có)

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
kubectl create namespace keda
helm install keda kedacore/keda -n keda
```

Hoặc dùng [manifest YAML](https://github.com/kedacore/keda/releases).

## Apply ScaledObjects

```bash
kubectl apply -f scaledobject-auth.yaml
kubectl apply -f scaledobject-account.yaml
kubectl apply -f scaledobject-transfer.yaml
kubectl apply -f scaledobject-notification.yaml
```

## Cấu hình ScaledObject

- **Trigger:** Prometheus scaler.
- **Query:** `sum(rate(http_requests_total{job="<service>"}[2m]))` — RPS trung bình 2 phút.
- **threshold:** Scale up khi RPS > giá trị này (vd. 5).
- **activationThreshold:** Scale down khi RPS < giá trị này (vd. 1). Min replica vẫn được tôn trọng.
- **minReplicaCount / maxReplicaCount:** 1 và 5 trong ví dụ; có thể chỉnh trong từng file.

## Kiểm tra

```bash
kubectl get scaledobject -n banking
kubectl get hpa -n banking
kubectl describe scaledobject <name> -n banking
```

Sau khi chạy load test, replicas tăng khi RPS vượt threshold và giảm khi tải hạ.
