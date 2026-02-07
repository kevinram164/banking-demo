# Phase 4 — Hướng dẫn chạy Application v2

Phase 4 là bản nâng cấp: đăng nhập bằng số điện thoại, số tài khoản, chuyển tiền theo account number.

**Chạy qua CI/CD**: CI (GitHub Actions) → CD (ArgoCD).

---

## Bạn cần có trước

- Kubernetes cluster đã có ArgoCD + banking-demo deploy (Phase 2)
- GitHub repo + GitLab Container Registry
- Secrets GitHub: `GITLAB_USERNAME`, `GITLAB_TOKEN`

---

## Các bước thực hiện (theo thứ tự)

### Bước 1: DB Migration (bắt buộc — làm TRƯỚC khi deploy v2)

v2 thêm 2 cột `phone`, `account_number` vào bảng `users`. Nếu deploy trước khi migration, app sẽ crash.

**1.1. Backup DB trước khi ALTER/backfill**

```bash
# K8s: dump qua kubectl
kubectl exec -it postgres-0 -n banking -- pg_dump -U banking banking > backup_before_v2_$(date +%Y%m%d).sql

# Hoặc nếu có pg_dump local, kết nối trực tiếp
pg_dump -h <postgres-host> -U banking -d banking > backup_before_v2.sql
```

**1.2. Chạy SQL sau (qua `psql` hoặc `kubectl exec` vào Postgres):**

```sql
-- 1. Add columns (nullable)
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS account_number VARCHAR(20);

-- 2. Backfill account_number cho user cũ (nếu có)
DO $$
DECLARE
  r RECORD;
  candidate TEXT;
BEGIN
  FOR r IN SELECT id FROM users WHERE account_number IS NULL LOOP
    LOOP
      candidate := lpad((floor(random()*1e12))::bigint::text, 12, '0');
      EXIT WHEN NOT EXISTS (SELECT 1 FROM users WHERE account_number = candidate);
    END LOOP;
    UPDATE users SET account_number = candidate WHERE id = r.id;
  END LOOP;
END $$;

-- 3. Add unique index
CREATE UNIQUE INDEX IF NOT EXISTS users_account_number_uq ON users(account_number) WHERE account_number IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS users_phone_uq ON users(phone) WHERE phone IS NOT NULL;
```

**1.3. Cách chạy SQL (K8s):**

```bash
kubectl exec -it postgres-0 -n banking -- psql -U banking -d banking -c "
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS account_number VARCHAR(20);
-- paste phần backfill + index từ trên
"
```

---

### Bước 2: Cấu hình GitHub Secrets

Vào **GitHub repo → Settings → Secrets and variables → Actions**, thêm:

| Secret | Mô tả |
|--------|-------|
| `GITLAB_USERNAME` | Username GitLab |
| `GITLAB_TOKEN` | Personal Access Token (scope: read_registry, write_registry) |

---

### Bước 3: Push code → CI chạy

Push code phase4 lên `main` hoặc `develop`:

```bash
git push origin main
```

CI sẽ: Lint → Test → Build images → Push lên GitLab Registry.

Lấy **commit SHA** (vd: `abc1234`) từ GitHub Actions run hoặc:

```bash
git rev-parse --short HEAD
```

---

### Bước 4: Cập nhật image tag trong Helm values

Chỉ sửa **5 file** (không sửa postgres, redis — tránh restart DB/cache):

- `auth-service/values.yaml`
- `account-service/values.yaml`
- `transfer-service/values.yaml`
- `notification-service/values.yaml`
- `frontend/values.yaml`

Đổi `image.tag` thành SHA từ bước 3 (vd: `abc1234`):

```yaml
# Ví dụ auth-service/values.yaml
auth-service:
  image:
    tag: abc1234
```

---

### Bước 5: Commit và ArgoCD sync

```bash
# Chỉ add 5 service values — KHÔNG add postgres, redis (tránh restart DB)
git add phase2-helm-chart/banking-demo/charts/auth-service/values.yaml \
  phase2-helm-chart/banking-demo/charts/account-service/values.yaml \
  phase2-helm-chart/banking-demo/charts/transfer-service/values.yaml \
  phase2-helm-chart/banking-demo/charts/notification-service/values.yaml \
  phase2-helm-chart/banking-demo/charts/frontend/values.yaml
git commit -m "chore: bump images to abc1234"
git push origin main
```

**ArgoCD sync — tránh restart postgres/redis:**

- **Cách 1 (1 Application)**: ArgoCD UI → banking-demo → Sync → **Selective Sync** → Chọn chỉ các Deployment (auth, account, transfer, notification, frontend), bỏ chọn postgres, redis StatefulSets.
- **Cách 2 (per-service Applications)**: Chỉ sync 5 app: `banking-demo-auth-service`, `banking-demo-account-service`, `banking-demo-transfer-service`, `banking-demo-notification-service`, `banking-demo-frontend`. Không sync `banking-demo-postgres`, `banking-demo-redis`.

---

### Bước 6: Verify

```bash
# Kiểm tra pods
kubectl get pods -n banking

# Health check
curl https://<ingress-host>/api/auth/health
```

---

## Smoke test (sau khi ArgoCD sync xong)

Smoke test verify health + auth flow qua Kong. **Chạy sau Bước 5** (sau khi ArgoCD sync xong, pods mới đã chạy).

### Bước 1: Chạy smoke test Job

Từ **root repo**:

```bash
helm template banking-demo phase2-helm-chart/banking-demo \
  -n banking \
  -f phase2-helm-chart/banking-demo/charts/common/values.yaml \
  -f phase2-helm-chart/banking-demo/charts/kong/values.yaml \
  --set smokeTest.enabled=true \
  -s templates/smoke-test-job.yaml | kubectl apply -f - -n banking
```

### Bước 2: Xem trạng thái Job

```bash
kubectl get jobs -n banking | grep smoke-test
```

### Bước 3: Xem logs

```bash
# Lấy tên Job (vd: banking-demo-smoke-test-xxxxx)
kubectl logs -n banking -l app.kubernetes.io/component=smoke-test -f
```

- **Thành công**: Log có `✅ Smoke tests (health + login) passed.`
- **Thất bại**: Log báo lỗi, Job fail

### Bước 4: Debug nếu fail

```bash
# Kiểm tra pods services
kubectl get pods -n banking

# Test health thủ công qua Kong
kubectl run -it --rm curl --image=curlimages/curl -n banking -- \
  curl -s http://kong:8000/api/auth/health
```

### Cấu hình (nếu cần)

Trong `charts/common/values.yaml`, smoke test dùng:

- `authUser`: `smoke-user` (user test cho register/login)
- `authPassword`: `smoke-pass`

**Lưu ý v2**: Phase 4 đăng ký dùng `phone`. Smoke test mặc định dùng `username` — v2 vẫn hỗ trợ login bằng username (backward compatible). Nếu register fail (400), có thể user `smoke-user` đã tồn tại từ lần test trước → login vẫn pass.

---

## Tóm tắt nhanh

| Bước | Việc cần làm |
|------|--------------|
| 1 | Backup DB → Chạy DB migration (ALTER TABLE + backfill + index) |
| 2 | Cấu hình GitHub Secrets (GITLAB_USERNAME, GITLAB_TOKEN) |
| 3 | Push code → CI build & push images |
| 4 | Sửa `image.tag` trong charts/*/values.yaml |
| 5 | Commit, push → ArgoCD sync (chỉ 5 app services, không sync postgres/redis) |
| 6 | Verify |
| 7 | Smoke test (sau ArgoCD sync) |

---

## Khắc phục: Postgres/Redis bị restart khi update images

**Nguyên nhân**: Sync ArgoCD apply cả postgres/redis, hoặc commit nhầm file values của postgres/redis.

**Cách tránh**:
1. Chỉ sửa 5 file values (auth, account, transfer, notification, frontend) — không sửa postgres/redis
2. Dùng `git add` chọn lọc (như Bước 5 trên)
3. ArgoCD sync: Selective Sync (bỏ chọn postgres, redis) hoặc dùng per-service Applications — chỉ sync 5 app
4. `application.yaml` đã có `ApplyOutOfSyncOnly=true` — chỉ apply resources thay đổi

---

## Khắc phục: Grafana không ghi nhận giao dịch transfer thành công

**Triệu chứng**: Chuyển khoản OK trên app, nhưng dashboard Grafana (Transfer — Thành công vs thất bại, Tỷ lệ thành công) vẫn 0.

**Luồng dữ liệu**: Frontend → Kong (`/api/transfer/transfer`) → transfer-service (`/transfer`) → metrics `http_requests_total{job="transfer-service",endpoint="/transfer",status="200"}` → Prometheus scrape → Grafana.

### Chẩn đoán (làm lần lượt)

**1. Kiểm tra Prometheus targets**

Vào `http://<prometheus-url>:9090/targets` (hoặc port-forward `kubectl port-forward svc/xxx-prometheus-server -n monitoring 9090:80`). Tìm target `transfer-service`. Nếu **DOWN** → Prometheus không scrape được (kiểm tra network, Service, namespace `banking`).

**2. Kiểm tra transfer-service có expose /metrics**

```bash
kubectl exec -it deploy/transfer-service -n banking -- curl -s http://localhost:8003/metrics | head -50
```

Phải thấy dòng `http_requests_total` với labels `method`, `endpoint`, `status`. Nếu không có → image transfer-service cũ (chưa có `observability.py`) → cần deploy image Phase 4.

**3. Kiểm tra labels trong Prometheus**

Vào Prometheus → Query (`http://<prometheus-url>:9090/graph`):

```promql
http_requests_total{job="transfer-service"}
```

Xem có series với `endpoint="/transfer"` và `status=~"2.."` không. Nếu có `endpoint="/"` thay vì `/transfer` → Kong strip_path có thể đang gửi path sai (hiếm); hoặc Grafana query dùng sai label.

**4. Kiểm tra time range**

Grafana mặc định `now-1h` đến `now`. Đảm bảo time range bao gồm thời điểm bạn chuyển khoản. `rate(...[5m])` cần có scrape trong 5 phút gần đây.

**5. Thử query thư giãn hơn (chỉ để test)**

Trong Grafana, thêm panel tạm với:

```promql
http_requests_total{job="transfer-service"}
```

Nếu panel này có dữ liệu mà panel Transfer không có → vấn đề nằm ở filter `endpoint="/transfer"` hoặc `status=~"2.."`.

### Khắc phục thường gặp

| Nguyên nhân | Cách sửa |
|-------------|----------|
| Image transfer-service cũ (không có metrics) | Bump `image.tag` trong `charts/transfer-service/values.yaml` → ArgoCD sync |
| Prometheus target DOWN | Kiểm tra Service, network policies; scrape config dùng `transfer-service.banking.svc.cluster.local:8003` |
| Sai time range | Chọn Last 15m hoặc 1h trong Grafana |
| Prometheus chưa cài đặt | Deploy `helm-monitoring` (kube-prometheus-stack) với `values-kube-prometheus-stack.yaml` |

---

## Tài liệu thêm

- `CICD-FLOW.md` — Luồng CI/CD chi tiết (GitHub Actions jobs, ArgoCD)
- `RUNBOOK_EXTERNAL_DB_REDIS.md` — Dùng DB/Redis bên ngoài cluster
- `phase2-helm-chart/argocd/ARGOCD.md` — Hướng dẫn ArgoCD đầy đủ
