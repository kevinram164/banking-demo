# Phase 9 — GitOps Platform (Quick Start)

Triển khai **CI (Jenkins + Kaniko + Harbor)** và **CD (ArgoCD App of Apps)** cho banking-demo Phase 8 trên nền Phase 5.

Chi tiết: [PHASE9.md](./PHASE9.md) | Bootstrap: [bootstrap/BOOTSTRAP.md](./bootstrap/BOOTSTRAP.md)

**Lab k3d / nhánh `dev-k3d`:** [k3d/DEV-K3D-WORKFLOW.md](../k3d/DEV-K3D-WORKFLOW.md) | [environments/dev-k3d/](./environments/dev-k3d/)

## 1. Sửa placeholder trong repo

Tìm và thay trong `phase9-gitops-platform/`:

| Placeholder | Thay bằng |
|-------------|-----------|
| `https://github.com/YOUR_ORG/banking-demo.git` | URL GitHub thật |
| `harbor.example.com` | Harbor host |
| `main` | Branch GitOps (nếu khác) |

## 2. Bootstrap platform (một lần)

Xem thứ tự đầy đủ trong [bootstrap/BOOTSTRAP.md](./bootstrap/BOOTSTRAP.md):

```bash
# AppProject mở rộng (namespace Phase 5 + platform)
kubectl apply -f phase9-gitops-platform/argocd/project.yaml -n argocd

# Root App of Apps — ArgoCD tự sync infra + banking + platform stubs
kubectl apply -f phase9-gitops-platform/argocd/app-of-apps.yaml -n argocd
```

## 3. Cấu hình Jenkins Shared Library

1. Tạo repo hoặc branch `jenkins-shared-library` (hoặc copy thư mục `jenkins-shared-library/` vào repo Jenkins).
2. Trong Jenkins: **Manage Jenkins → System → Global Pipeline Libraries** → thêm library `banking-demo` trỏ tới repo.
3. Tạo Pipeline job multibranch / webhook GitHub, dùng `jenkins/Jenkinsfile.example`.

## 4. Luồng phát triển

```bash
# Dev push code Phase 8
git push origin main   # paths: phase8-application-v3/**

# Jenkins: build Kaniko → Harbor → commit values-images.yaml
# ArgoCD: sync banking apps → rollout pods
```

## 5. Kiểm tra

```bash
argocd app list | grep banking
kubectl get pods -n banking
curl -s -H "Host: npd-banking.co" http://<ingress-ip>/ | head
```

## Cấu trúc ArgoCD

```
app-of-apps (root)
├── platform-app-of-apps   → jenkins, harbor, vault, external-secrets (wave 0)
├── infra-app-of-apps      → postgres, redis, kong, rabbitmq (wave 0–1)
└── banking-app-of-apps    → namespace, services Phase 8 (wave 1–2)
```

Per-service banking apps dùng:

- `phase2-helm-chart/banking-demo` + `values-phase8.yaml`
- `phase9-gitops-platform/gitops/values-images.yaml` (CI cập nhật tag)
