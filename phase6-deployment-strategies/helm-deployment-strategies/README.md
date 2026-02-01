# Phase 6 – Helm chart: Deployment Strategies (Blue-Green & Canary)

Chart **riêng** cho Phase 6, không lẫn với Phase 2. Deploy các service banking (auth, account, transfer, notification) theo chiến lược **Blue-Green** hoặc **Canary**.

## Điều kiện

- **Phase 2** đã chạy trong namespace `banking`: Kong, postgres, redis, frontend.
- Khi dùng chart này: **tắt** các service auth-service, account-service, transfer-service, notification-service trong Phase 2 (để tránh trùng tên Deployment/Service). Chart Phase 6 tạo đủ Deployment + Service + Service "active" (tên `auth-service`, `account-service`, …) để Kong trỏ tới.

## Cài đặt

```bash
# Từ repo root
cd phase6-deployment-strategies/helm-deployment-strategies

# Blue-Green (mặc định)
helm upgrade -i banking-rollout . -n banking -f values.yaml -f values-blue-green.yaml

# Hoặc Canary
helm upgrade -i banking-rollout . -n banking -f values.yaml -f values-canary.yaml
```

Namespace `banking` phải đã tồn tại (từ Phase 2). Secret `banking-db-secret` (DATABASE_URL, REDIS_URL) phải có sẵn.

## Blue-Green

- Chart tạo với mỗi service: Deployment `auth-service-blue`, `auth-service-green`, Service `auth-service-blue`, `auth-service-green`, và **Service `auth-service`** (selector = `activeSlot`).
- Kong (Phase 2) gọi `auth-service` → traffic vào blue hoặc green tùy `activeSlot`.

**Promote sang green:**

```bash
helm upgrade banking-rollout . -n banking -f values.yaml -f values-blue-green.yaml --set activeSlot=green
```

**Rollback về blue:**

```bash
helm upgrade banking-rollout . -n banking -f values.yaml -f values-blue-green.yaml --set activeSlot=blue
```

## Canary

- Chart tạo: Deployment/Service `auth-service-stable`, `auth-service-canary`. Service **`auth-service`** (selector = `stable`) để Kong vẫn hoạt động.
- Chia % traffic sang canary cần cấu hình **Ingress canary** (NGINX canary annotations) hoặc Argo Rollouts – xem `../canary/CANARY.md`.

## Values chính

| Key | Mô tả |
|-----|--------|
| `strategy` | `blueGreen` \| `canary` |
| `activeSlot` | Blue-Green: `blue` \| `green` – slot đang nhận traffic |
| `canaryWeight` | Canary: % traffic canary (chỉ dùng khi có Ingress canary) |
| `services.<name>.enabled` | Bật/tắt từng service |
| `services.<name>.image.blueTag` / `greenTag` | Image tag cho blue/green |
| `services.<name>.image.stableTag` / `canaryTag` | Image tag cho stable/canary |

## Cấu trúc templates

- `deployment-slot.yaml`: Deployment cho từng slot (blue, green hoặc stable, canary).
- `service-slot-1.yaml`, `service-slot-2.yaml`: Service cho từng slot (ví dụ `auth-service-blue`, `auth-service-green`).
- `service-active.yaml`: Service tên `auth-service`, `account-service`, … (selector = activeSlot hoặc stable) – Kong trỏ tới đây.

**Lưu ý:** Nếu `helm template` báo lỗi "unexpected EOF", thử chạy từ WSL/Linux hoặc dùng Helm 3.28+; chart vẫn dùng được với `helm upgrade --install`.

## Liên kết

- **PHASE6.md** – tổng quan Phase 6.
- **blue-green/BLUE-GREEN.md** – thiết kế Blue-Green.
- **canary/CANARY.md** – thiết kế Canary và Ingress canary.
