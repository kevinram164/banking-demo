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
| Credential Harbor + GitHub | **Thủ công** trên Jenkins UI (2 ID cố định) |
| Tạo job pipeline | **Thủ công** — Multibranch Pipeline trỏ repo |

Hướng dẫn đầy đủ từng bước: [K3D-DEPLOY-GUIDE.md § 4.4](../K3D-DEPLOY-GUIDE.md#44-jenkins--cấu-hình-ci-từng-bước)

## Credential ID (bắt buộc đúng tên)

| ID | Dùng cho |
|----|----------|
| `harbor-ci-push` | Robot Harbor push (`robot$ci-push` + token) |
| `github-gitops-push` | GitHub PAT commit `values-images.yaml` |

## Services được build

| Service | Dockerfile |
|---------|------------|
| api-producer | `phase8-application-v3/producer/Dockerfile` |
| auth-service | `phase8-application-v3/services/auth-service/Dockerfile` |
| account-service | `phase8-application-v3/services/account-service/Dockerfile` |
| transfer-service | `phase8-application-v3/services/transfer-service/Dockerfile` |
| notification-service | `phase8-application-v3/services/notification-service/Dockerfile` |

Chỉ build service có file thay đổi dưới `phase8-application-v3/`.

## Jenkinsfile mẫu

Repo đã có `Jenkinsfile` ở root (nhánh `dev-k3d`):

```groovy
@Library('banking-demo') _

bankingDemoPipeline([
  harborHost      : 'harbor-npd.co',
  harborProject   : 'banking-demo',
  gitBranch       : 'dev-k3d',
  gitRepoUrl      : 'https://github.com/kevinram164/banking-demo.git',
  gitopsValuesFile: 'phase9-gitops-platform/gitops/values-images.yaml',
])
```

Bản generic: [../jenkins/Jenkinsfile.example](../jenkins/Jenkinsfile.example)
