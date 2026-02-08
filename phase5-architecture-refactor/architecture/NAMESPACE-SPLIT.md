# Tách namespace (Phase 5)

Mục tiêu: tách **Kong**, **Redis**, **Postgres** (DB ứng dụng) sang các **namespace riêng**, không còn chung namespace `banking` với app. Ứng dụng banking giữ namespace `banking` và kết nối tới Redis/Postgres/Kong qua DNS cross-namespace.

## 1. Kiến trúc sau khi tách

```text
Namespace banking:
  - frontend, auth-service, account-service, transfer-service, notification-service
  - Ingress (trỏ backend tới Kong ở ns kong)
  - Secret (banking-db-secret) – URL trỏ tới postgres.postgres, redis.redis

Namespace kong (hoặc api-gateway):
  - Kong Deployment + Service
  - (Tùy chọn) Postgres riêng cho Kong (Kong DB mode)

Namespace redis:
  - Redis StatefulSet + Service

Namespace postgres (hoặc data):
  - Postgres StatefulSet + Service (DB ứng dụng banking)
```

## 2. DNS cross-namespace

Trong Kubernetes, Service ở namespace khác gọi qua FQDN:

- **Postgres (ứng dụng)**: `postgres.postgres.svc.cluster.local:5432`
- **Redis**: `redis.redis.svc.cluster.local:6379`
- **Kong (từ Ingress hoặc từ banking)**: `kong.kong.svc.cluster.local:8000` (proxy), `:8001` (admin)

Trong namespace `banking`, cấu hình:

- **DATABASE_URL**: `postgresql://user:pass@postgres.postgres.svc.cluster.local:5432/banking`
- **REDIS_URL**: `redis://redis.redis.svc.cluster.local:6379/0`

Ingress (trong ns `banking` hoặc `ingress` tùy setup) trỏ path `/api` tới backend **Kong** ở ns `kong`:

- Backend service: `kong.kong.svc.cluster.local:8000` (cần chỉnh Ingress backend theo cluster: dùng tên Service nếu Ingress controller hỗ trợ cross-ns, hoặc dùng ExternalName / Service trong ns banking trỏ tới Kong).

**Lưu ý**: Một số Ingress controller yêu cầu backend Service cùng namespace với Ingress. Khi đó có thể: (1) đặt Ingress trong ns `kong` và trỏ path `/` tới frontend ở ns `banking` (cross-ns), hoặc (2) tạo Service dạng ExternalName trong ns `banking` trỏ tới `kong.kong.svc.cluster.local`, hoặc (3) dùng Ingress controller hỗ trợ backend cross-namespace (ví dụ một số bản HAProxy/NGINX).

## 3. Thứ tự triển khai

1. Tạo namespace: `kubectl create namespace kong` (và `redis`, `postgres` nếu tách).
2. Deploy Postgres (ứng dụng) vào ns `postgres`; tạo Secret chứa connection string.
3. Deploy Redis vào ns `redis`.
4. Deploy Kong vào ns `kong`; cấu hình Kong trỏ backend tới các service trong ns `banking` (FQDN: `auth-service.banking.svc.cluster.local:8001`, …).
5. Chỉnh chart banking-demo: bỏ Postgres, Redis, Kong khỏi chart; chỉnh values (common) dùng `postgres.postgres.svc.cluster.local`, `redis.redis.svc.cluster.local`; tạo Secret trong ns `banking` tham chiếu hoặc copy connection string.
6. Chỉnh Ingress: backend API trỏ tới Kong (cross-ns nếu được, hoặc qua ExternalName Service như trên).

## 4. Secret và quyền

- Secret chứa **DATABASE_URL**, **REDIS_URL** có thể đặt trong ns `banking` (app đọc); hoặc dùng External Secrets / Vault, mỗi ns lấy đúng secret.
- Kong có thể cần ServiceAccount với quyền đọc ConfigMap/Secret trong ns `kong`; DB riêng cho Kong (nếu dùng DB mode) cũng trong ns `kong` hoặc `postgres`.

## 5. Checklist

- [ ] Tạo namespace `kong`, `redis`, `postgres`.
- [ ] Deploy Postgres (app DB) vào ns `postgres`; tạo Secret cho banking.
- [ ] Deploy Redis vào ns `redis`.
- [ ] Deploy Kong vào ns `kong`; cấu hình backends trỏ tới `*.banking.svc.cluster.local`.
- [ ] Thu gọn chart banking-demo: chỉ còn app + Ingress; values dùng FQDN postgres/redis.
- [ ] Ingress trỏ /api tới Kong (cross-ns hoặc ExternalName).
- [ ] Kiểm tra kết nối: app → Postgres/Redis; client → Ingress → Kong → app.
