# Jenkins Shared Library — banking-demo

Thư viện Groovy dùng trong `Jenkinsfile` (root repo) để:

1. Build image Phase 8 bằng **Kaniko**
2. Push lên **Harbor** (`harbor-npd.co/banking-demo/...`)
3. Cập nhật tag trong **`gitops/values-images.yaml`** và push Git

## Ai cấu hình gì?

| Việc | Cách làm |
|------|----------|
| Cài Jenkins + plugin | ArgoCD app `platform-jenkins` |
| Đăng ký library `banking-demo` | **Tự động** qua JCasC trong `jenkins.yaml` |
| Credential Harbor + GitHub | **Vault** `secret/platform/jenkins` | Xem [vault/README.md](../vault/README.md) |
| Tạo job pipeline | **Thủ công** — Multibranch Pipeline trỏ repo |

Hướng dẫn đầy đủ từng bước: [K3D-DEPLOY-GUIDE.md § 4.4](../K3D-DEPLOY-GUIDE.md#44-jenkins--cấu-hình-ci-từng-bước)

**Sơ đồ chi tiết:** [overview (ảnh chính)](../../articles/viblo-series/assets/jenkins-shared-library-overview.png) · [flow](../../articles/viblo-series/assets/jenkins-shared-library-flow.png) · [sequence](../../articles/viblo-series/assets/jenkins-shared-library-sequence.png)

## Credential ID (bắt buộc đúng tên)

| Credential ID | Nguồn | Vault path / key |
|---------------|--------|------------------|
| `harbor-ci-push` | Vault → ESO → JCasC | `platform/jenkins` → `harbor_username`, `harbor_password` |
| `github-gitops-push` | Vault → ESO → JCasC | `platform/jenkins` → `github_username`, `github_pat` |
| Jenkins admin | Vault → ESO → Helm | `platform/jenkins` → `admin_password` |

Không tạo credential thủ công trên Jenkins UI. Chi tiết: [vault/README.md](../vault/README.md).

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

Lần chạy Multibranch **đầu tiên** sau khi thêm parameter: chạy job một lần, lần sau dùng **Build with Parameters**.

Push thay đổi shared library → branch `dev-k3d` → Jenkins load library mới (hoặc restart `jenkins-0` nếu cache library cũ).

Pod agent dùng image **`gcr.io/kaniko-project/executor:*-debug`** — bản `executor` thường không có `/busybox/cat` (Jenkins giữ container sống trước khi `sh` chạy `/kaniko/executor`).

## Jenkinsfile mẫu

Repo đã có `Jenkinsfile` ở root (nhánh `dev-k3d`):

```groovy
@Library('banking-demo') _

bankingDemoPipeline([
  harborHost      : 'harbor-npd.co',
  harborProject   : 'banking-demo',
  gitBranch       : 'dev-k3d',
  gitRepoUrl      : 'https://github.com/kevinram164/banking-demo.git',
  gitopsValuesFile     : 'phase9-gitops-platform/gitops/values-images.yaml',
  kanikoSkipTlsVerify  : true,   // lab k3d — Harbor cert self-signed
])
```

Bản generic: [../jenkins/Jenkinsfile.example](../jenkins/Jenkinsfile.example)
