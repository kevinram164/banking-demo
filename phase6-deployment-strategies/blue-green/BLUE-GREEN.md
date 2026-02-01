# Blue-Green Deployment (Phase 6)

Blue-Green: chạy **hai bản** (blue = hiện tại, green = mới). Toàn bộ traffic chuyển sang green trong **một lần**; nếu lỗi thì chuyển lại traffic về blue.

## 1. Ý tưởng

- **Blue**: version đang phục vụ user.
- **Green**: version mới đã deploy, đã smoke-test (hoặc health check) nhưng chưa nhận traffic.
- **Switch**: đổi Service/Ingress trỏ từ blue → green. User ngay lập tức dùng green.
- **Rollback**: đổi lại Service/Ingress trỏ về blue.

Ưu điểm: rollback nhanh (chỉ đổi backend), không cần chờ rolling. Nhược: cần tài nguyên gấp đôi trong lúc chạy hai bản.

## 2. Cách triển khai trên K8s (gắn với Phase 2 chart)

Có hai hướng chính.

### 2.1. Hai Deployment + hai Service + một Ingress (đổi backend)

- **Deployment** `auth-service-blue`, **Deployment** `auth-service-green` (cùng app, khác `version` label và image tag).
- **Service** `auth-service-blue` (selector `version=blue`), **Service** `auth-service-green` (selector `version=green`).
- **Ingress** trỏ path `/api/auth` tới **một** trong hai Service. Khi promote: sửa Ingress backend từ `auth-service-blue` → `auth-service-green`. Rollback: sửa lại về blue.

Với Helm Phase 2, bạn có thể:

- Dùng **hai release** (ví dụ `banking-demo-blue`, `banking-demo-green`) với values khác nhau (image tag, suffix label `version: blue` / `version: green`), rồi một Ingress chung trỏ tới Service của release “active”.
- Hoặc mở rộng chart: thêm template/values cho “blue/green mode” (hai Deployment, hai Service, Ingress nhận `activeSlot: blue` hoặc `green`).

### 2.2. Một Service, selector theo version (flip selector)

- **Deployment** `auth-service-blue` (labels `app=auth-service, version=blue`).
- **Deployment** `auth-service-green` (labels `app=auth-service, version=green`).
- **Service** `auth-service` có **selector** `app=auth-service, version=blue` (hoặc green). Traffic luôn đi qua Service này; chỉ có pod nào khớp selector mới nhận request.
- **Promote**: deploy green xong, đổi selector của Service thành `version=green`. **Rollback**: đổi lại selector thành `version=blue`.

Cách này không cần sửa Ingress; chỉ cần `kubectl patch service` hoặc Helm upgrade với value `activeVersion: green`.

## 3. Ví dụ: Service selector (hướng 2.2)

Giả sử bạn đã có sẵn Deployment blue và green (tạo bằng Helm với values khác nhau). Chỉ cần một Service và đổi selector:

```yaml
# Service auth-service – selector quyết định blue hay green nhận traffic
apiVersion: v1
kind: Service
metadata:
  name: auth-service
  namespace: banking
spec:
  selector:
    app: auth-service
    version: blue    # Đổi thành "green" khi promote
  ports:
    - port: 80
      targetPort: 8080
      name: http
```

Promote sang green:

```bash
kubectl patch svc auth-service -n banking -p '{"spec":{"selector":{"app":"auth-service","version":"green"}}}'
```

Rollback:

```bash
kubectl patch svc auth-service -n banking -p '{"spec":{"selector":{"app":"auth-service","version":"blue"}}}'
```

## 4. Gắn với Phase 2 Helm chart

- Chart hiện tại: một Deployment + một Service mỗi app (auth-service, account-service, …). Để làm blue-green **trong** chart, cần:
  - Thêm label `version: {{ .Values.global.activeSlot | default "blue" }}` vào Deployment và selector của Service.
  - Khi install/upgrade: deploy **green** với `global.activeSlot: green` và image tag v2; nhưng Service vẫn đang selector `version=blue` (activeSlot vẫn blue). Sau khi smoke-test green, upgrade lần nữa chỉ để đổi `global.activeSlot: green` → Service selector đổi sang green.
- Hoặc giữ chart đơn giản, làm blue-green **bên ngoài**: hai release Helm (banking-demo-blue, banking-demo-green) + script/CI đổi Ingress hoặc Service selector như trên.

## 5. Checklist Blue-Green

1. [ ] Xác định service cần blue-green (ví dụ auth-service, frontend).
2. [ ] Chọn cách: hai Service + Ingress hay một Service + selector theo version.
3. [ ] Deploy green (image mới) song song blue; đảm bảo green pass readiness/health.
4. [ ] Smoke-test green (gọi nội bộ hoặc qua Service green).
5. [ ] Switch traffic (patch Ingress/Service) → green.
6. [ ] Theo dõi Phase 3 (metrics/errors); nếu lỗi thì rollback (trỏ lại blue).
7. [ ] Sau khi ổn định, có thể xóa hoặc giữ blue cho lần rollout tiếp theo.

## 6. Liên kết

- **Phase 2**: Helm chart `phase2-helm-chart/banking-demo` – cấu trúc Deployment/Service/Ingress.
- **Phase 3**: Prometheus/Grafana – theo dõi error rate, latency sau khi switch.
- **Phase 4**: Image v2 – dùng làm “green” khi rollout application v2.
