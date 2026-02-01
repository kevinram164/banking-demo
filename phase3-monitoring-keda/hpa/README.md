# HPA — Autoscaling theo CPU + Memory

Scale các Deployment `auth-service`, `account-service`, `transfer-service`, `notification-service` theo **CPU** và **Memory** (native Kubernetes HPA).

## HPA vs KEDA

| | HPA (này) | KEDA |
|---|-----------|------|
| **Trigger** | CPU, Memory | Prometheus (RPS, latency...) |
| **Phụ thuộc** | metrics-server | Prometheus + KEDA operator |
| **Ưu điểm** | Đơn giản, built-in, CPU cao → scale ngay | Scale theo RPS/business metric |

**Quan trọng:** Không dùng **cả hai** (HPA + KEDA ScaledObject) cho cùng một deployment. Chọn một trong hai.

## Điều kiện

- **metrics-server** đã cài trên cluster (thường có sẵn).
- Namespace `banking` và các deployment đã tồn tại.

## Apply HPA (thay thế KEDA)

Nếu đang dùng KEDA, xóa ScaledObjects trước:

```bash
kubectl -n banking delete scaledobject auth-service-scaler account-service-scaler transfer-service-scaler notification-service-scaler
```

Sau đó apply HPA:

```bash
kubectl apply -f hpa-auth.yaml
kubectl apply -f hpa-account.yaml
kubectl apply -f hpa-transfer.yaml
kubectl apply -f hpa-notification.yaml
```

Hoặc apply tất cả:

```bash
kubectl apply -f .
```

## Cấu hình mặc định

- **CPU target:** 70% utilization → scale up
- **Memory target:** 80% utilization → scale up
- **minReplicas:** 1
- **maxReplicas:** 5
- **scaleDown:** stabilization 120s
- **scaleUp:** không stabilization (scale nhanh khi tải cao)

## Kiểm tra

```bash
kubectl get hpa -n banking
kubectl top pod -n banking
kubectl describe hpa auth-service -n banking
```

Sau khi chạy load test, CPU/memory tăng → replicas tăng.
