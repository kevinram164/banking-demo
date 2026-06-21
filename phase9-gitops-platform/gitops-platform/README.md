# GitOps Platform — ArgoCD manifests (Phase 9)

## Cấu trúc

```
banking-platform-root (app-of-apps.yaml)
├── platform-app-of-apps.yaml   → applications/platform/*.yaml
├── infra-app-of-apps.yaml      → applications/infra/*.yaml
└── banking-app-of-apps.yaml    → applications/banking/*.yaml
```

## Apply

```bash
# 1. Project (một lần)
kubectl apply -f phase9-gitops-platform/gitops-platform/project.yaml -n argocd

# 2. Root
kubectl apply -f phase9-gitops-platform/gitops-platform/app-of-apps.yaml -n argocd
```

## Sync waves

| Wave | Apps |
|------|------|
| -1 | `banking-namespace` |
| 0 | platform (ESO, Vault), infra postgres/redis |
| 1 | kong, rabbitmq, api-producer |
| 2 | auth, account, transfer, notification, frontend, ingress |

## GitOps values

Banking apps merge thêm:

```yaml
valueFiles:
  - charts/<service>/values.yaml
  - values-phase8.yaml
  - ../../../../phase9-gitops-platform/gitops/values-images.yaml  # relative từ chart path
```

Path trong manifest dùng path tuyệt đối từ repo root qua `helm.valueFiles` — xem `banking/auth-service.yaml`.

## Coexist với Phase 2 ArgoCD

Project **`banking-platform`** (Phase 9) tách khỏi **`banking-demo`** (Phase 2) để tránh conflict khi thử nghiệm. Production: gộp project hoặc xóa apps Phase 2 cũ.
