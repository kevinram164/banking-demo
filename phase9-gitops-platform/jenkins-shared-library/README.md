# Jenkins Shared Library — banking-demo

Thư viện Groovy dùng trong `Jenkinsfile` (root repo) để:

1. Build image Phase 8 bằng **Kaniko**
2. Push lên **Harbor** (`harbor-platform.apps.../banking-demo/...`)
3. Cập nhật tag trong **`gitops/values-images.yaml`** và push Git

## Ai cấu hình gì?

| Việc | Cách làm |
|------|----------|
| Cài Jenkins + plugin | ArgoCD app `platform-jenkins` |
| Đăng ký library `banking-demo` | **Tự động** qua JCasC trong `jenkins.yaml` |
| Jenkins admin | **Vault** `secret/platform/jenkins` → ESO → Helm |
| Harbor robot + GitHub PAT | **Vault** `secret/platform/harbor`, `secret/platform/github` — pipeline đọc runtime |
| Tạo job pipeline | **Thủ công** — Multibranch Pipeline trỏ repo |

Hướng dẫn OCP: [OCP-DEPLOY-GUIDE.md § 5](../OCP-DEPLOY-GUIDE.md)

## Luồng secret (không Jenkins Credential Store)

```text
Vault secret/platform/harbor   ─┐
Vault secret/platform/github  ─┼─► agent pod (SA jenkins-kaniko)
                                 │   Kubernetes auth → VaultClient.groovy
                                 └─► Kaniko push / git push GitOps

Vault secret/platform/jenkins ──► ESO ──► jenkins-platform-credentials (admin only)
```

| Vault path | Key | Dùng cho |
|------------|-----|----------|
| `platform/harbor` | `username`, `password` | Kaniko push Harbor |
| `platform/github` | `username`, `pat` | Push `values-images.yaml` |
| `platform/jenkins` | `admin_*` | Login UI Jenkins |

Không tạo credential `harbor-ci-push` / `github-gitops-push` trên Jenkins. Chi tiết Vault: [vault/README.md](../vault/README.md).

## Services được build

| Service | Dockerfile | Context |
|---------|------------|---------|
| api-producer | `phase8-application-v3/producer/Dockerfile` | repo root |
| auth-service | `phase8-application-v3/services/auth-service/Dockerfile` | repo root |
| account-service | `phase8-application-v3/services/account-service/Dockerfile` | repo root |
| transfer-service | `phase8-application-v3/services/transfer-service/Dockerfile` | repo root |
| notification-service | `phase8-application-v3/services/notification-service/Dockerfile` | repo root |
| frontend | `frontend/Dockerfile` | `frontend/` |

**BUILD_TARGET = auto:** build khi diff chạm thư mục service / `phase8-application-v3/common/` (Python) hoặc `frontend/`.

### Build with Parameters

| BUILD_TARGET | Hành vi |
|--------------|---------|
| `auto` (mặc định) | Chỉ build service có diff trong commit; không diff → skip |
| `all` | Build mọi service (kể cả frontend) |
| `api-producer`, `auth-service`, `frontend`, … | Build đúng một service |

Pod agent: `serviceAccountName: jenkins-kaniko`, image Kaniko `*-debug`.

### Stages trên Jenkins UI

```text
Checkout
Build api-producer          ← chỉ khi service nằm trong targets
Build auth-service
Build account-service
…
Build frontend
Update GitOps
```

Mỗi image một stage — fail ở service nào hiện đúng stage đó (không gộp chung `Build & Push`).

### Kaniko push OK nhưng stage FAILURE / exit -1

Log có `Pushed …@sha256:…` rồi:

```text
wrapper script does not seem to be touching the log file
(JENKINS-48300…)
ERROR: script returned exit code -1
```

→ **Image đã lên Harbor**; Jenkins durable-task mất heartbeat (workspace NFS / agent lag).

Đã xử lý trong repo: heartbeat + `javaOpts` HEARTBEAT/USE_BINARY_WRAPPER. Shell Kaniko = `/home/jenkins/agent/bin/sh` (copy busybox) + `--ignore-path` — tránh mất `/busybox/sh` sau build frontend.

Hotfix tạm (chưa sync): **Manage Jenkins → Script Console**:

```groovy
System.setProperty('org.jenkinsci.plugins.durabletask.BourneShellScript.HEARTBEAT_CHECK_INTERVAL', '300')
```

Verify image: Harbor UI project `banking-demo` / tag vừa push. Nếu GitOps chưa bump — chạy lại pipeline hoặc `BUILD_TARGET=<svc>`.

## Jenkinsfile mẫu (dev-ocp)

```groovy
@Library('banking-demo') _

bankingDemoPipeline([
  harborHost           : 'harbor-platform.apps.ocp01.npd.co',
  harborProject        : 'banking-demo',
  gitBranch            : 'dev-ocp',
  vaultAddr            : 'http://vault.vault.svc.cluster.local:8200',
  vaultRole            : 'jenkins-kaniko',
  vaultHarborPath      : 'platform/harbor',
  vaultGithubPath      : 'platform/github',
  kanikoSkipTlsVerify  : true,
])
```

Bản generic: [../jenkins/Jenkinsfile.example](../jenkins/Jenkinsfile.example)
