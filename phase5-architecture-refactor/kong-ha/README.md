# Triển khai Kong HA với Postgres (Phase 5)

Hướng dẫn deploy Kong HA (2 replica) dùng Postgres làm datastore, config từ file declarative được import vào DB. Kong chạy trong namespace riêng `kong`, kết nối tới Postgres HA có sẵn trong ns `postgres`.

---

## Điều kiện tiên quyết

- **Postgres HA** đã triển khai trong ns `postgres` (xem `postgres-ha/README.md`)
- **Banking app** đang chạy trong ns `banking` (auth-service, account-service, transfer-service, notification-service)

---

## Bước 1: Tạo database Kong trên Postgres

Chạy Job tạo DB `kong` và user `kong` trên Postgres HA có sẵn.

```bash
# Sửa kong-db-init-job.yaml nếu release Postgres khác:
# - postgres-postgresql-primary  → postgres-ha-postgresql-primary (nếu release = postgres-ha)
# - Secret postgres-postgresql   → postgres-ha-postgresql

kubectl apply -f kong-ha/kong-db-init-job.yaml -n postgres
kubectl -n postgres get jobs
kubectl -n postgres logs job/kong-db-init
```

Đảm bảo Job hoàn thành thành công (`COMPLETIONS 1/1`).

---

## Bước 2: Thêm Helm repo và deploy Kong

```bash
helm repo add kong https://charts.konghq.com
helm repo update

kubectl create namespace kong

# Sửa values-kong-ha.yaml nếu cần:
# - env.pg_host: postgres-ha-postgresql-primary.postgres... (nếu release = postgres-ha)
# - env.pg_password: khớp với kongpass trong kong-db-init-job

helm upgrade -i kong kong/kong -n kong -f kong-ha/values-kong-ha.yaml

# Chờ Kong Ready
kubectl -n kong get pods -l app.kubernetes.io/name=kong -w
# Ctrl+C khi tất cả Running, Ready 1/1
```

Kong sẽ chạy migrations (tạo bảng) lần đầu. Pod `kong-kong-pre-upgrade-migrations` và `kong-kong-post-upgrade-migrations` cần Completed.

---

## Bước 3: Import config declarative vào Kong DB

Sau khi Kong đã chạy và migrations xong, import routes/services/plugins từ file.

```bash
# Cách 1: Dùng ConfigMap có sẵn trong kong-import-job.yaml
kubectl apply -f kong-ha/kong-import-job.yaml -n kong

# Cách 2: Tạo ConfigMap từ file kong-declarative.yaml (nếu chỉnh sửa)
kubectl create configmap kong-declarative-config \
  --from-file=kong.yml=kong-ha/kong-declarative.yaml -n kong --dry-run=client -o yaml | kubectl apply -f -
# Rồi apply Job (bỏ phần ConfigMap trong kong-import-job.yaml nếu đã tạo trước)

kubectl -n kong get jobs
kubectl -n kong logs job/kong-config-import -f
```

Đảm bảo Job hoàn thành. Nếu chạy lại (re-apply) có thể gặp lỗi duplicate – xóa Job cũ và apply lại, hoặc dùng `kong config db_import` với flag `--no-overwrite` tùy phiên bản.

---

## Bước 4: Cập nhật Ingress trỏ sang Kong mới

Ingress trong ns `banking` (hoặc ns chứa Ingress) cần backend trỏ tới Kong ở ns `kong`:

```yaml
# backend /api và /ws
serviceName: kong-kong-proxy   # hoặc tên Service do chart tạo
servicePort: 8000
# Nếu Ingress không hỗ trợ cross-namespace, tạo ExternalName Service:
# kind: Service
# spec:
#   type: ExternalName
#   externalName: kong-kong-proxy.kong.svc.cluster.local
```

Tên Service: `kong-kong-proxy` (release `kong`, chart tạo suffix `-kong-proxy`). Kiểm tra:

```bash
kubectl -n kong get svc
```

Nếu dùng HAProxy Ingress hoặc Ingress khác yêu cầu backend cùng namespace, tạo Service trong ns `banking`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: kong-proxy
  namespace: banking
spec:
  type: ExternalName
  externalName: kong-kong-proxy.kong.svc.cluster.local
```

Rồi Ingress trỏ `serviceName: kong-proxy`, `servicePort: 8000`. Một số Ingress controller không hỗ trợ ExternalName – cần dùng annotation hoặc endpoint thủ công.

---

## Bước 5: Tắt Kong cũ (Phase 2)

Trong chart `banking-demo` (Phase 2), tắt Kong:

```yaml
# values banking-demo
kong:
  enabled: false
```

Restart hoặc upgrade release banking-demo.

---

## Bước 6: Kiểm tra Kong HA

```bash
# Pods Kong
kubectl -n kong get pods -l app.kubernetes.io/name=kong

# Services
kubectl -n kong get svc

# Test proxy (từ trong cluster)
kubectl run curl-test --rm -it --restart=Never --image=curlimages/curl -- \
  curl -s -o /dev/null -w "%{http_code}" http://kong-kong-proxy.kong.svc.cluster.local:8000/api/auth/health

# Admin API (list services)
kubectl run curl-test --rm -it --restart=Never --image=curlimages/curl -- \
  curl -s http://kong-kong-admin.kong.svc.cluster.local:8001/services | head -20
```

---

## Tóm tắt thứ tự

1. Job `kong-db-init` – tạo DB `kong` + user trên Postgres
2. `helm upgrade -i kong kong/kong -n kong -f values-kong-ha.yaml`
3. Job `kong-config-import` – import declarative config vào DB
4. Cập nhật Ingress backend → Kong mới (ns `kong`)
5. Tắt Kong cũ trong banking-demo
6. Kiểm tra routes, đăng nhập, chuyển tiền

---

## Lưu ý

- **pg_host / Secret**: Nếu dùng release Postgres `postgres-ha`, sửa `pg_host` và tên Secret trong Job tương ứng.
- **Backends FQDN**: File `kong-declarative.yaml` dùng `*.banking.svc.cluster.local` vì Kong ở ns `kong`, app ở ns `banking`.
- **CORS**: Điều chỉnh `origins` trong declarative config nếu domain khác.
- **decK** (thay db_import): Có thể dùng `deck sync -s kong.yml --kong-addr http://kong-kong-admin.kong:8001` từ image `kong/deck` nếu cần sync thường xuyên.
