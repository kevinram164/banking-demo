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

| Service | Dockerfile |
|---------|------------|
| api-producer | `phase8-application-v3/producer/Dockerfile` |
| auth-service | `phase8-application-v3/services/auth-service/Dockerfile` |
| account-service | `phase8-application-v3/services/account-service/Dockerfile` |
| transfer-service | `phase8-application-v3/services/transfer-service/Dockerfile` |
| notification-service | `phase8-application-v3/services/notification-service/Dockerfile` |

Chỉ build service có file thay đổi dưới `phase8-application-v3/` khi **BUILD_TARGET = auto**.

### Build with Parameters

| BUILD_TARGET | Hành vi |
|--------------|---------|
| `auto` (mặc định) | Chỉ build service có diff trong commit; không diff → skip |
| `all` | Build mọi service |
| `api-producer`, `auth-service`, … | Build đúng một service |

Pod agent: `serviceAccountName: jenkins-kaniko`, image Kaniko `*-debug`.

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
