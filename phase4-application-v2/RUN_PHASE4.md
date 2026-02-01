# Hướng dẫn chạy Phase 4 (Application v2) — CI/CD chuẩn production

Phase 4 chạy theo mô hình **production-like**:

- **CI**: GitHub Actions — build images, push lên GitLab Registry
- **CD**: ArgoCD — deploy lên Kubernetes theo GitOps (sync từ Git)

---

## ⚠️ Thứ tự bắt buộc

**DB Migration phải chạy TRƯỚC khi deploy v2.** v2 thêm cột `phone`, `account_number` — nếu deploy trước khi ALTER bảng, app sẽ crash.

```
1. DB Migration (ALTER TABLE, backfill...)  ← TRƯỚC TIÊN
2. CI (build & push images)
3. CD (ArgoCD sync)
```

---

## Tổng quan flow

```
┌──────────────────────┐     ┌─────────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  1. DB Migration     │     │  2. Push code       │     │  3. CI (GitHub       │     │  4. CD          │
│  ALTER TABLE users   │ ──▶ │  phase4 → main      │ ──▶ │  Actions) Build →   │ ──▶ │  ArgoCD sync    │
│  + backfill          │     │                     │     │  Push images         │     │  Deploy K8s     │
└──────────────────────┘     └─────────────────────┘     └──────────────────────┘     └─────────────────┘
         │                              │                           │                           │
         │                              └───────────────────────────┴───────────────────────────┘
         │                                         Cập nhật image tag trong values → commit → push
         │
         └── Phải xong trước bước 4 (deploy)
```

---

## Bước 0: DB Migration (BẮT BUỘC trước khi deploy v2)

v2 thêm 2 cột: `phone`, `account_number`. **Phải chạy migration trước** khi ArgoCD sync deploy v2.

### SQL cần chạy

```sql
-- Bước 1: Add columns (nullable)
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS account_number VARCHAR(20);

-- Bước 2: Backfill account_number cho user cũ (nếu có)
-- (Xem DB_MIGRATION_GUIDE.md để copy script đầy đủ)

-- Bước 3: Add unique index
CREATE UNIQUE INDEX IF NOT EXISTS users_account_number_uq ON users(account_number) WHERE account_number IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS users_phone_uq ON users(phone) WHERE phone IS NOT NULL;
```

### Cách chạy (K8s)

```bash
# Lấy DATABASE_URL từ Secret banking-db-secret
kubectl get secret banking-db-secret -n banking -o jsonpath='{.data.DATABASE_URL}' | base64 -d

# Chạy migration (thay $DATABASE_URL)
kubectl run -it --rm migration --image=postgres:15-alpine -n banking -- \
  env PGPASSWORD=... psql -h postgres -U banking -d banking -c "
  ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
  ALTER TABLE users ADD COLUMN IF NOT EXISTS account_number VARCHAR(20);
  -- + backfill + index (xem DB_MIGRATION_GUIDE.md)
"
```

Chi tiết đầy đủ: **[DB_MIGRATION_GUIDE.md](./DB_MIGRATION_GUIDE.md)**.

---

## Bước 1: CI — GitHub Actions

### Trigger

CI chạy khi có thay đổi trong:

- `phase4-application-v2/**`
- `common/**` → build **all** services

### Flow

1. **Push** code lên `main` hoặc `develop` → CI tự chạy
2. **Manual**: GitHub → Actions → CI → Run workflow → chọn `services: all` (hoặc services cần build)

### Secrets

GitHub repo → Settings → Secrets → Actions:

| Secret | Mô tả |
|--------|-------|
| `GITLAB_USERNAME` | Username GitLab |
| `GITLAB_TOKEN` | Personal Access Token (scope: read_registry, write_registry) |

### Kết quả

Images push lên `registry.gitlab.com/kiettt164/banking-demo-payment/<service>:<sha>`, `:main`, `:latest`.

Lấy **commit SHA** (vd: `abc1234`) từ CI run hoặc `git rev-parse --short HEAD`.

---

## Bước 2: CD — ArgoCD

### Cập nhật image tag trong Git

Sau khi CI push xong, cập nhật `image.tag` trong Helm values:

**Files cần sửa** (trong `phase2-helm-chart/banking-demo/charts/`):

- `auth-service/values.yaml` → `auth-service.image.tag`
- `account-service/values.yaml` → `account-service.image.tag`
- `transfer-service/values.yaml` → `transfer-service.image.tag`
- `notification-service/values.yaml` → `notification-service.image.tag`
- `frontend/values.yaml` → `frontend.image.tag`

Ví dụ (thay `<sha>` bằng SHA từ CI, vd: `abc1234`):

```yaml
# charts/auth-service/values.yaml
auth-service:
  image:
    tag: abc1234
```

### Commit và push

```bash
git add phase2-helm-chart/banking-demo/charts/*/values.yaml
git commit -m "chore: bump image tags to abc1234"
git push origin main
```

### ArgoCD sync

1. Vào ArgoCD UI → Applications → `banking-demo`
2. **Refresh** (hard refresh) → **Sync**
3. ArgoCD apply manifests mới → Rolling update pods với image mới

Nếu bật **Auto Sync**, ArgoCD tự sync khi detect thay đổi trong Git.

---

## Smoke test (sau khi deploy)

ArgoCD **không chạy Helm hooks** khi sync. Chạy smoke test thủ công sau khi ArgoCD sync xong.

Chạy thủ công sau khi sync (từ root repo):

```bash
helm template banking-demo phase2-helm-chart/banking-demo \
  -n banking \
  -f phase2-helm-chart/banking-demo/charts/common/values.yaml \
  --set smokeTest.enabled=true \
  -s templates/smoke-test-job.yaml | kubectl apply -f - -n banking
```

Hoặc chuyển smoke-test Job sang ArgoCD PostSync hook.

---

## Tóm tắt quy trình release

```bash
# 0. DB Migration TRƯỚC (bắt buộc)
#    ALTER TABLE users ADD COLUMN phone, account_number + backfill + index
#    Xem DB_MIGRATION_GUIDE.md

# 1. Developer push code phase4
git push origin main

# 2. CI chạy → build & push images (SHA: abc1234)

# 3. Cập nhật image tag trong values
#    charts/auth-service/values.yaml, charts/account-service/values.yaml, ...
#    image.tag: abc1234

# 4. Commit và push
git add phase2-helm-chart/banking-demo/charts/
git commit -m "chore: bump images to abc1234"
git push origin main

# 5. ArgoCD sync (auto hoặc manual)
# 6. Smoke test + Verify
```

---

## Files tham khảo

| File | Nội dung |
|------|----------|
| [CICD-FLOW.md](./CICD-FLOW.md) | Chi tiết CI, smoke test, ArgoCD hooks |
| [DB_MIGRATION_GUIDE.md](./DB_MIGRATION_GUIDE.md) | Migration DB cho v2 |
| [phase2-helm-chart/argocd/ARGOCD.md](../phase2-helm-chart/argocd/ARGOCD.md) | Hướng dẫn ArgoCD đầy đủ |
