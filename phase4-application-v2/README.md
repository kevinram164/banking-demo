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

Sửa các file trong `phase2-helm-chart/banking-demo/charts/`:

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
git add phase2-helm-chart/banking-demo/charts/
git commit -m "chore: bump images to abc1234"
git push origin main
```

Vào **ArgoCD UI** → Applications → `banking-demo` → **Refresh** → **Sync**.

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
| 5 | Commit, push → ArgoCD sync |
| 6 | Verify |
| 7 | Smoke test (sau ArgoCD sync) |

---

## Tài liệu thêm

- `RUNBOOK_EXTERNAL_DB_REDIS.md` — Dùng DB/Redis bên ngoài cluster
- `phase2-helm-chart/argocd/ARGOCD.md` — Hướng dẫn ArgoCD đầy đủ
