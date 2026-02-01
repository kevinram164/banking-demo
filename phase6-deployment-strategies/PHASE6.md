# Giai đoạn 6: Deployment Strategies (Blue-Green & Canary)

Giai đoạn 6 tập trung vào **chiến lược rollout** trên Kubernetes: Blue-Green và Canary để deploy phiên bản mới an toàn, dễ rollback.

## Mục tiêu

- Hiểu **Blue-Green**: hai môi trường (blue = hiện tại, green = mới), chuyển traffic một lần.
- Hiểu **Canary**: đưa một phần traffic sang version mới, tăng dần hoặc rollback nếu lỗi.
- Áp dụng với **Phase 2 Helm chart** (banking-demo) và có thể kết hợp **Phase 3** (metrics) để quyết định promote/rollback.

## Cấu trúc thư mục

```text
phase6-deployment-strategies/
├── PHASE6.md                     # File này – overview + checklist
├── helm-deployment-strategies/   # Helm chart riêng Phase 6 (không lẫn Phase 2)
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-blue-green.yaml
│   ├── values-canary.yaml
│   ├── README.md
│   └── templates/
│       ├── _helpers.tpl
│       ├── deployment-slot.yaml
│       ├── service-slot.yaml
│       └── service-active.yaml
├── blue-green/
│   └── BLUE-GREEN.md             # Thiết kế Blue-Green với K8s/Helm
└── canary/
    └── CANARY.md                 # Thiết kế Canary với K8s/Ingress hoặc Argo Rollouts
```

## So sánh nhanh

| Chiến lược   | Ý tưởng                    | Rollback              | Tài nguyên      |
|-------------|----------------------------|------------------------|-----------------|
| **Rolling** | K8s mặc định: cập nhật pod dần | Tự động (rollback revision) | 1 bản deploy    |
| **Blue-Green** | 2 bản (blue/green), switch traffic | Đổi lại Service/Ingress → blue | 2 bản chạy song song |
| **Canary**  | % traffic sang version mới | Giảm % hoặc xóa canary       | 2 bản, 1 nhận ít traffic |

## Helm chart Phase 6 (riêng, không lẫn Phase 2)

Phase 6 có **một bộ Helm chart riêng** trong `helm-deployment-strategies/`:

- **Chart**: `banking-deployment-strategies` – deploy các service banking (auth, account, transfer, notification) theo **Blue-Green** hoặc **Canary**.
- **Cách dùng**: Tắt các service tương ứng trong Phase 2 (auth-service, account-service, …), rồi cài chart Phase 6 trong cùng namespace `banking`. Kong (Phase 2) vẫn trỏ tới tên `auth-service`, `account-service` – chart Phase 6 tạo đúng các Service đó với selector blue/green hoặc stable.
- **Chi tiết**: xem `helm-deployment-strategies/README.md`.

## Lộ trình thực hiện (gợi ý)

1. **Blue-Green** – dùng chart `helm-deployment-strategies` với `strategy: blueGreen`; đọc `blue-green/BLUE-GREEN.md`.
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

## Lệnh tham chiếu

**Phase 6 chart (khuyến nghị):**

```bash
cd phase6-deployment-strategies/helm-deployment-strategies
helm upgrade -i banking-rollout . -n banking -f values.yaml -f values-blue-green.yaml
helm upgrade banking-rollout . -n banking -f values.yaml -f values-blue-green.yaml --set activeSlot=green  # promote
```

**Phase 2** (chỉ dùng khi không dùng Phase 6 chart): `phase2-helm-chart/banking-demo` – cài banking-demo; khi dùng Phase 6 chart thì **tắt** auth-service, account-service, transfer-service, notification-service trong Phase 2 để tránh trùng tên.
