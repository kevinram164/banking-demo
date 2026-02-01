# Giai đoạn 6: Deployment Strategies (Blue-Green & Canary)

Giai đoạn 6 tập trung vào **chiến lược rollout** trên Kubernetes: Blue-Green và Canary để deploy phiên bản mới an toàn, dễ rollback.

## Mục tiêu

- Hiểu **Blue-Green**: hai môi trường (blue = hiện tại, green = mới), chuyển traffic một lần.
- Hiểu **Canary**: đưa một phần traffic sang version mới, tăng dần hoặc rollback nếu lỗi.
- Áp dụng với **Phase 2 Helm chart** (banking-demo) và có thể kết hợp **Phase 3** (metrics) để quyết định promote/rollback.

## Cấu trúc thư mục

```text
phase6-deployment-strategies/
├── PHASE6.md                 # File này – overview + checklist
├── blue-green/
│   └── BLUE-GREEN.md         # Thiết kế Blue-Green với K8s/Helm
└── canary/
    └── CANARY.md             # Thiết kế Canary với K8s/Ingress hoặc Argo Rollouts
```

## So sánh nhanh

| Chiến lược   | Ý tưởng                    | Rollback              | Tài nguyên      |
|-------------|----------------------------|------------------------|-----------------|
| **Rolling** | K8s mặc định: cập nhật pod dần | Tự động (rollback revision) | 1 bản deploy    |
| **Blue-Green** | 2 bản (blue/green), switch traffic | Đổi lại Service/Ingress → blue | 2 bản chạy song song |
| **Canary**  | % traffic sang version mới | Giảm % hoặc xóa canary       | 2 bản, 1 nhận ít traffic |

## Lộ trình thực hiện (gợi ý)

1. **Blue-Green** – đọc `blue-green/BLUE-GREEN.md`. Có thể triển khai bằng:
   - Hai Deployment + hai Service; Ingress trỏ tới Service “active” (blue hoặc green). Đổi Ingress/Service khi promote.
   - Hoặc một Service với selector thay đổi (version label): deploy green, đổi selector → green nhận traffic.
2. **Canary** – đọc `canary/CANARY.md`. Có thể triển khai bằng:
   - Ingress (HAProxy/NGINX) hỗ trợ traffic split theo weight hoặc header.
   - Hoặc Argo Rollouts / Flagger nếu muốn canary tự động + analysis dựa trên Prometheus (Phase 3).
3. **Kết hợp Phase 3** – dùng SLO/error rate từ Prometheus để quyết định promote canary hoặc rollback (xem Phase 5 `sre/SLO-ALERTING.md`).

## Điều kiện tiên quyết

- **Phase 2** Helm chart banking-demo đã chạy (namespace `banking`).
- (Khuyến nghị) **Phase 3** monitoring đã cài (Prometheus + Grafana) để theo dõi canary/blue-green khi switch traffic.
- **Phase 4** nếu bạn rollout image v2: build image v2, dùng cùng chart với tag khác cho green/canary.

## Lệnh tham chiếu (Phase 2)

```bash
# Từ repo root
cd phase2-helm-chart/banking-demo

# Cài/upgrade với image tag (ví dụ v2 cho green)
helm upgrade --install banking-demo . -n banking -f charts/common/values.yaml \
  --set auth-service.image.tag=v2
```

Phase 6 không thay thế Phase 2; nó bổ sung **cách** bạn rollout (blue-green hoặc canary) trên cùng chart đó.
