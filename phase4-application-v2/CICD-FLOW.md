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

## Chi tiết CI (GitHub Actions)

### Cấu trúc workflow

Workflow `.github/workflows/ci.yml` gồm 6 jobs chạy tuần tự:

```
detect-changes → lint → test → build-images → push-images → security-scan
                      ↘ ci-summary (chạy song song sau push)
```

| Job | Mô tả | Điều kiện chạy |
|-----|-------|----------------|
| **detect-changes** | Phát hiện services thay đổi | Luôn chạy |
| **lint** | Ruff check Python (v1 + v2) | Khi có service thay đổi |
| **test** | pytest + syntax check | Sau lint (trừ khi `skip_tests=true`) |
| **build-images** | Docker build (selective) | Sau test, matrix theo service |
| **push-images** | Push lên GitLab Registry | Chỉ khi push main/develop hoặc manual + force_push |
| **security-scan** | Trivy scan image | Sau push (continue-on-error) |
| **ci-summary** | Tổng hợp kết quả | Luôn chạy (summary) |

### Chi tiết từng job

#### 1. detect-changes

- Dùng `dorny/paths-filter` để detect file thay đổi
- Filter paths:
  - `auth-service`: `services/auth-service/**`, `phase4-application-v2/services/auth-service/**`
  - Tương tự cho `account-service`, `transfer-service`, `notification-service`, `frontend`
  - `common`: `common/**`, `phase4-application-v2/common/**` → nếu đổi common → build **all** services
- Output: `services-list` = `all` hoặc `auth-service,account-service,...` hoặc `none`

#### 2. lint

- Python 3.11
- `ruff check common services --ignore E501`
- `ruff check phase4-application-v2/common phase4-application-v2/services --ignore E501`
- Chạy `|| true` (không fail CI nếu có warning)

#### 3. test

- Cài: `common/requirements.txt`, `phase4-application-v2/requirements-dev.txt`
- Syntax check: `python -m compileall` cho common, services (v1 + v2)
- Pytest: `pytest -q phase4-application-v2/tests` (|| true)
- Skip khi manual trigger có `skip_tests: true`

#### 4. build-images

- **Matrix**: 5 services (auth, account, transfer, notification, frontend)
- Chỉ build service nằm trong `services-list`
- Mỗi service có `context` và `dockerfile` riêng
- Tags: `<sha>`, `<branch>`, `latest` (chỉ main)
- Build xong upload artifact (`/tmp/<service>.tar`) → dùng cho push job

#### 5. push-images

- Chỉ chạy khi:
  - `push` vào `main` hoặc `develop`, **hoặc**
  - `workflow_dispatch` + `force_push=true` (hoặc đang ở main)
- Download artifact → load image → login GitLab → tag & push
- Cần secrets: `GITLAB_USERNAME`, `GITLAB_TOKEN`

#### 6. security-scan

- Trivy scan image `:latest` của mỗi service
- Severity: HIGH, CRITICAL
- `exit-code: 0`, `continue-on-error: true` → không fail CI

### Manual trigger (workflow_dispatch)

| Input | Mô tả | Giá trị mặc định |
|-------|-------|------------------|
| `services` | Chọn services: `all`, `auth-service`, `auth-service,frontend`, ... | `all` |
| `skip_tests` | Bỏ qua test (cho hotfix) | `false` |
| `force_push` | Push image dù không ở main | `false` |

**Cách dùng**: GitHub → Actions → CI → Run workflow → chọn inputs.

### Secrets cần thiết

| Secret | Mô tả |
|--------|-------|
| `GITLAB_USERNAME` | Username GitLab (hoặc deploy token username) |
| `GITLAB_TOKEN` | Personal Access Token hoặc Deploy Token (scope: read_registry, write_registry) |

### Path filters (trigger)

CI **chỉ** chạy khi có thay đổi trong:

- `common/**`
- `services/**`
- `frontend/**`
- `phase4-application-v2/**`
- `.github/workflows/ci.yml`

**Không** trigger khi đổi: `phase2-helm-chart/**`, `*.md`, `k8s/**`, v.v.

---

## Hướng dẫn Smoke Test khi nâng cấp Application

Smoke test là Job verify health + auth flow qua Kong sau khi deploy.

### Khi dùng ArgoCD (production)

ArgoCD **không** chạy Helm hooks. Chạy smoke test thủ công sau sync, hoặc chuyển Job sang ArgoCD PostSync hook. Chi tiết: [RUN_PHASE4.md](./RUN_PHASE4.md#migration-db-và-smoke-test-với-argocd).

### Khi dùng Helm CLI (demo)

#### Bước 1: Bật smoke test trong upgrade

```bash
# Lấy SHA từ CI (ví dụ: abc1234)
NEW_SHA="abc1234"

helm upgrade --install banking-demo phase2-helm-chart/banking-demo \
  -n banking \
  --set dbMigration.enabled=true \
  --set smokeTest.enabled=true \
  --set auth-service.image.tag=$NEW_SHA \
  --set account-service.image.tag=$NEW_SHA \
  --set transfer-service.image.tag=$NEW_SHA \
  --set notification-service.image.tag=$NEW_SHA \
  --set frontend.image.tag=$NEW_SHA
```

Thứ tự Helm sẽ chạy:

1. **pre-upgrade**: DB migration Job
2. Deploy các Deployment mới
3. **post-upgrade**: Smoke test Job

#### Bước 2: Đợi smoke test hoàn thành

```bash
# Xem trạng thái Job
kubectl get jobs -n banking | grep smoke-test

# Xem logs (thay xxx bằng suffix của Job)
kubectl logs -n banking job/banking-demo-smoke-test-xxx -f
```

- Nếu **thành công**: Job complete, pod bị xóa (hook-delete-policy)
- Nếu **thất bại**: Job fail, pod còn lại để debug → `helm upgrade` coi như fail

#### Bước 3: Nếu smoke test fail

```bash
# Xem logs
kubectl logs -n banking -l app.kubernetes.io/component=smoke-test

# Kiểm tra Kong và services
kubectl get pods -n banking
curl -s http://<kong-svc>:8000/api/auth/health
```

Sau khi sửa, chạy lại `helm upgrade` (có thể tạm tắt smoke: `--set smokeTest.enabled=false` để deploy nhanh, rồi chạy smoke thủ công).

### Khi dùng ArgoCD

ArgoCD **không** chạy Helm hooks khi sync. Có 2 cách:

#### Option A: Chạy smoke test thủ công sau sync

1. ArgoCD sync → deploy services
2. Chạy smoke test Job thủ công:

```bash
# Tạo Job từ template Helm (export manifest)
helm template banking-demo phase2-helm-chart/banking-demo \
  -n banking \
  --set smokeTest.enabled=true \
  | kubectl apply -f - -n banking

# Hoặc apply file smoke-test-job đã render
kubectl apply -f - <<EOF
# paste manifest từ helm template
EOF
```

#### Option B: Chuyển sang ArgoCD hook

Sửa `smoke-test-job.yaml`: đổi annotation từ `helm.sh/hook` sang `argocd.argoproj.io/hook: PostSync` để ArgoCD chạy sau mỗi sync. (Chi tiết xem tài liệu ArgoCD.)

### Cấu hình smoke test (values.yaml)

Trong `phase2-helm-chart/banking-demo/charts/common/values.yaml`:

```yaml
smokeTest:
  enabled: false          # Bật = true khi upgrade
  image: "curlimages/curl:8.11.0"
  hookWeight: "10"        # Chạy sau Deployment (số dương)
  backoffLimit: 1
  activeDeadlineSeconds: 120
  authUser: "smoke-user"  # User test để register/login
  authPassword: "smoke-pass"
```

**Lưu ý**: `authUser`/`authPassword` phải khớp với user có thể đăng ký (nếu cần custom, override bằng `--set smokeTest.authUser=...`).

### Smoke test làm gì?

1. **Health checks**: GET `/api/auth/health`, `/api/account/health`, `/api/transfer/health`, `/api/notifications/health`
2. **Register**: POST `/api/auth/register` (chấp nhận 200, 201, 409)
3. **Login**: POST `/api/auth/login` (phải 200)

Tất cả gọi qua Kong (`KONG_HOST:KONG_PORT`).

### Ví dụ upgrade end-to-end với smoke test

```bash
# 1. CI đã push image với tag abc1234
# 2. Upgrade với migration + smoke test
helm upgrade --install banking-demo phase2-helm-chart/banking-demo \
  -n banking \
  --set dbMigration.enabled=true \
  --set smokeTest.enabled=true \
  --set auth-service.image.tag=abc1234 \
  --set account-service.image.tag=abc1234 \
  --set transfer-service.image.tag=abc1234 \
  --set notification-service.image.tag=abc1234 \
  --set frontend.image.tag=abc1234

# 3. Theo dõi
kubectl get pods -n banking -w
# Đợi smoke test Job complete (hoặc fail)

# 4. Verify
curl -s https://npd-banking.co/api/auth/health
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

## CD Flow — ArgoCD (chuẩn production)

**Mô hình production**: CI (GitHub Actions) + CD (ArgoCD). ArgoCD sync manifests từ Git → deploy lên Kubernetes.

### Quy trình CD với ArgoCD

1. CI push images lên Registry (tag: `<sha>`, `main`, `latest`)
2. Cập nhật `phase2-helm-chart/banking-demo/charts/<service>/values.yaml` — `image.tag: <sha>`
3. Commit và push
4. ArgoCD sync → apply manifests → rolling update

(Xem [RUN_PHASE4.md](./RUN_PHASE4.md) — hướng dẫn chi tiết.)

### Migration và Smoke test với ArgoCD

ArgoCD **không chạy Helm hooks** (`helm.sh/hook`) — ArgoCD chỉ `kubectl apply` manifests.

Hiện tại Helm chart có:

- `dbMigration` (Helm hook) — **không chạy** qua ArgoCD sync
- `smokeTest` (Helm hook) — **không chạy** qua ArgoCD sync

**Cách xử lý:**

- **Migration**: Chạy thủ công trước sync, hoặc chuyển Job sang `argocd.argoproj.io/hook: PreSync`
- **Smoke test**: Chạy thủ công sau sync, hoặc chuyển Job sang `argocd.argoproj.io/hook: PostSync`

### Alternative: Helm CLI (cho demo/test local)

Khi dùng `helm upgrade` thay vì ArgoCD, Helm hooks **sẽ chạy** (migration + smoke test). Phù hợp demo nhanh, không dùng cho production.

---

## Quy trình release chuẩn (end-to-end) — CI + ArgoCD

```bash
# 1. Developer push code phase4
git push origin main

# 2. CI (GitHub Actions) chạy: lint → test → build → push → scan
#    Images: <sha>, main, latest trên GitLab Registry

# 3. CD (ArgoCD): Cập nhật image.tag trong charts/<service>/values.yaml
#    → commit → push

# 4. ArgoCD sync (auto hoặc manual) → deploy

# 5. Verify:
#    kubectl get pods -n banking
#    curl https://npd-banking.co/api/auth/health
```

---

## Files liên quan

| File | Mô tả |
|------|-------|
| `.github/workflows/ci.yml` | CI workflow đầy đủ |
| `phase2-helm-chart/` | Helm chart cho CD |
| `phase2-helm-chart/banking-demo/templates/smoke-test-job.yaml` | Smoke test Job template |
| `phase2-helm-chart/banking-demo/charts/common/values.yaml` | Cấu hình smokeTest, dbMigration |
| `phase2-helm-chart/argocd/` | ArgoCD Application manifests |
| `phase4-application-v2/requirements-dev.txt` | Dev deps (pytest, ruff) |
