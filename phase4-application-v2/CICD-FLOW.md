# CI/CD Flow — Banking Demo

## Tổng quan

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CI (GitHub Actions)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────┐                                                    │
│   │ Detect Changes  │ ← Chỉ build services thay đổi                      │
│   └────────┬────────┘                                                    │
│            │                                                             │
│            ▼                                                             │
│   ┌──────┐    ┌──────┐    ┌───────────────┐    ┌──────────────┐         │
│   │ Lint │───▶│ Test │───▶│ Build Images  │───▶│ Push Images  │         │
│   └──────┘    └──────┘    │ (selective)   │    └──────┬───────┘         │
│                           └───────────────┘           │                  │
│                                                       ▼                  │
│                                               ┌──────────────┐          │
│                                               │ Security     │          │
│                                               │ Scan (Trivy) │          │
│                                               └──────────────┘          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ registry.gitlab.com/kiettt164/banking-demo-payment/*
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              CD (ArgoCD)                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ArgoCD Application (Phase 2 Helm chart)                               │
│       │                                                                  │
│       ├── Sync khi image tag thay đổi trong values.yaml                 │
│       │                                                                  │
│       ▼                                                                  │
│   ┌──────────────────┐    ┌──────────────────┐    ┌─────────────────┐   │
│   │ DB Migration     │───▶│ Deploy Services  │───▶│ Smoke Test      │   │
│   │ (Helm pre-hook)  │    │ (Deployments)    │    │ (Helm post-hook)│   │
│   └──────────────────┘    └──────────────────┘    └─────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Path Filters — Khi nào CI chạy?

CI **CHỈ** chạy khi thay đổi code:

| Path | CI chạy? | Lý do |
|------|----------|-------|
| `common/**` | ✅ | Shared code → build ALL services |
| `services/auth-service/**` | ✅ | Build auth-service |
| `services/account-service/**` | ✅ | Build account-service |
| `frontend/**` | ✅ | Build frontend |
| `phase4-application-v2/**` | ✅ | Build v2 services |
| `phase2-helm-chart/**` | ❌ | Helm values → CD job, không cần build |
| `k8s/**` | ❌ | K8s manifests → CD job |
| `*.md` | ❌ | Documentation |
| `phase3-monitoring-keda/**` | ❌ | Monitoring config |

**Tại sao?** Khi đổi image tag trong Helm values → không cần build lại image, ArgoCD chỉ cần sync.

---

## Selective Build — Build riêng từng service

### Auto-detect (default)

CI tự detect file thay đổi và chỉ build services liên quan:

```bash
# Chỉ đổi auth-service → chỉ build auth-service
git commit -m "fix auth bug"
# CI: Build auth-service only

# Đổi common/ → build ALL (vì common dùng chung)
git commit -m "update models"
# CI: Build all services
```

### Manual trigger — chọn services

GitHub Actions → Run workflow → chọn:

| Input | Options | Mô tả |
|-------|---------|-------|
| `services` | `all`, `auth-service`, `frontend`, ... | Chọn service cần build |
| `skip_tests` | `true/false` | Bỏ qua test (cho hotfix) |
| `force_push` | `true/false` | Push image dù không ở main |

---

## CI Stages (GitHub Actions)

| Stage | Trigger | Mục đích |
|-------|---------|----------|
| **1. Detect Changes** | always | Xác định services nào cần build |
| **2. Lint** | có thay đổi | Check code style (ruff) |
| **3. Test** | sau lint | Syntax check + pytest |
| **4. Build Images** | sau test | Docker build (chỉ services thay đổi) |
| **5. Push Images** | main branch | Push lên GitLab Registry |
| **6. Security Scan** | sau push | Trivy scan vulnerabilities |

### Image tags

Mỗi image được tag theo:

- `<sha>` — commit SHA ngắn (vd: `abc1234`)
- `<branch>` — tên branch (vd: `main`, `develop`)
- `latest` — chỉ khi push vào main

Ví dụ:

```
registry.gitlab.com/kiettt164/banking-demo-payment/auth-service:abc1234
registry.gitlab.com/kiettt164/banking-demo-payment/auth-service:main
registry.gitlab.com/kiettt164/banking-demo-payment/auth-service:latest
```

### Khi nào chạy gì?

| Event | Lint | Test | Build | Push | Scan |
|-------|------|------|-------|------|------|
| PR to main | ✅ | ✅ | ✅ | ❌ | ❌ |
| Push to main | ✅ | ✅ | ✅ | ✅ | ✅ |
| Push to develop | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## CD Flow (ArgoCD)

ArgoCD **không dùng** Helm hooks (`helm.sh/hook`), nhưng **có dùng** ArgoCD hooks nếu bạn muốn.

Hiện tại Phase 2 Helm chart có:

- `dbMigration` (Helm hook) — **chỉ chạy khi dùng `helm upgrade`**, không chạy qua ArgoCD sync.
- `smokeTest` (Helm hook) — tương tự.

### Option 1: CD bằng Helm CLI (khuyến nghị cho demo)

```bash
# CI push image xong, chạy:
helm upgrade --install banking-demo phase2-helm-chart/banking-demo \
  -n banking \
  --set dbMigration.enabled=true \
  --set smokeTest.enabled=true \
  --set auth-service.image.tag=<new-sha>
```

→ Helm hooks (migration, smoke-test) **sẽ chạy**.

### Option 2: CD bằng ArgoCD (production)

Nếu dùng ArgoCD sync:

1. Update `values.yaml` với image tag mới.
2. ArgoCD sync → apply manifests.
3. Helm hooks **không tự động chạy** (ArgoCD chỉ `kubectl apply`).

Nếu cần migration/smoke-test trong ArgoCD:

- Chuyển annotation từ `helm.sh/hook` sang `argocd.argoproj.io/hook: PreSync/PostSync`.

---

## Quy trình release chuẩn (end-to-end)

```bash
# 1. Developer push code
git push origin feature/xyz

# 2. Tạo PR → CI chạy lint/test/build (không push image)

# 3. Merge PR vào main → CI chạy đầy đủ:
#    lint → test → build → push → scan

# 4. Image mới xuất hiện trên GitLab Registry với tag: <sha>, main, latest

# 5. CD (chọn 1):
#    a) Helm CLI: helm upgrade --set image.tag=<sha> ...
#    b) ArgoCD: update values.yaml, commit, ArgoCD sync

# 6. Verify:
#    - kubectl get pods -n banking
#    - curl https://npd-banking.co/api/auth/health
```

---

## Files liên quan

| File | Mô tả |
|------|-------|
| `.github/workflows/ci.yml` | CI workflow đầy đủ |
| `phase2-helm-chart/` | Helm chart cho CD |
| `phase2-helm-chart/argocd/` | ArgoCD Application manifests |
| `phase4-application-v2/requirements-dev.txt` | Dev deps (pytest, ruff) |
