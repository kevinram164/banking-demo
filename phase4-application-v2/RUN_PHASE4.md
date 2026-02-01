# Hướng dẫn chạy Phase 4 (Application v2) — CI/CD chuẩn production

Phase 4 chạy theo mô hình **production-like**:

- **CI**: GitHub Actions — build images, push lên GitLab Registry
- **CD**: ArgoCD — deploy lên Kubernetes theo GitOps (sync từ Git)

---

## Tổng quan flow

```
┌─────────────────────┐         ┌──────────────────────┐         ┌─────────────────┐
│  Push code phase4   │         │  GitHub Actions (CI)  │         │  ArgoCD (CD)    │
│  → main/develop     │ ──────▶ │  Build → Push images │ ──────▶ │  Sync từ Git    │
│                     │         │  Registry             │         │  Deploy K8s     │
└─────────────────────┘         └──────────────────────┘         └─────────────────┘
         │                                    │                             │
         │                                    │                             │
         └────────────────────────────────────┴─────────────────────────────┘
                          Cập nhật image tag trong values → commit → push
```

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

## Migration DB và Smoke test với ArgoCD

**Lưu ý**: ArgoCD **không chạy Helm hooks** (dbMigration, smokeTest) khi sync — ArgoCD chỉ `kubectl apply` manifests.

### Migration DB

Có 2 cách:

1. **Chạy migration thủ công** trước khi sync lần đầu lên v2:
   ```bash
   kubectl run -it --rm migration --image=postgres:15-alpine -n banking -- \
     psql $DATABASE_URL -c "
     ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
     ALTER TABLE users ADD COLUMN IF NOT EXISTS account_number VARCHAR(20);
   "
   ```
   (Chi tiết: [DB_MIGRATION_GUIDE.md](./DB_MIGRATION_GUIDE.md))

2. **Dùng ArgoCD PreSync hook**: chuyển Job migration sang annotation `argocd.argoproj.io/hook: PreSync` — ArgoCD sẽ chạy trước khi apply manifests.

### Smoke test

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
# 1. Developer push code phase4
git push origin main

# 2. CI chạy → build & push images (SHA: abc1234)

# 3. Cập nhật image tag trong values
# Sửa charts/auth-service/values.yaml, charts/account-service/values.yaml, ... 
# image.tag: abc1234

# 4. Commit và push
git add phase2-helm-chart/banking-demo/charts/
git commit -m "chore: bump images to abc1234"
git push origin main

# 5. ArgoCD sync (auto hoặc manual)
# 6. Verify: curl https://<host>/api/auth/health
```

---

## Files tham khảo

| File | Nội dung |
|------|----------|
| [CICD-FLOW.md](./CICD-FLOW.md) | Chi tiết CI, smoke test, ArgoCD hooks |
| [DB_MIGRATION_GUIDE.md](./DB_MIGRATION_GUIDE.md) | Migration DB cho v2 |
| [phase2-helm-chart/argocd/ARGOCD.md](../phase2-helm-chart/argocd/ARGOCD.md) | Hướng dẫn ArgoCD đầy đủ |
