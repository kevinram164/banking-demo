# Phase 9 — GitOps Platform (Quick Start)

Triển khai **CI (Jenkins + Kaniko + Harbor)** và **CD (ArgoCD App of Apps)** cho banking-demo Phase 8 trên nền Phase 5.

## Thứ tự triển khai (quan trọng)

| Giai đoạn | Nội dung | Deploy app? |
|-----------|----------|-------------|
| 1 | k3d + ArgoCD bootstrap | Không |
| 2 | Platform: Harbor, Vault, ESO, Jenkins | Không |
| 2b | Observability: Coroot, OTEL, Linkerd mesh | Không |
| 3 | Infra: Postgres, Redis, RabbitMQ, Kong | Không |
| 4 | CI/CD: Jenkins → Harbor → commit GitOps | Không |
| 5 | ArgoCD sync banking app | **Có** |

**Hướng dẫn đầy đủ:** **[K3D-DEPLOY-GUIDE.md](./K3D-DEPLOY-GUIDE.md)**

Chi tiết kiến trúc: [PHASE9.md](./PHASE9.md) | Bootstrap: [bootstrap/BOOTSTRAP.md](./bootstrap/BOOTSTRAP.md)

**Lab k3d / nhánh `dev-k3d`:** [k3d/DEV-K3D-WORKFLOW.md](../k3d/DEV-K3D-WORKFLOW.md) | [environments/dev-k3d/](./environments/dev-k3d/)

## Apply theo giai đoạn (dev-k3d)

```bash
# Giai đoạn 1 — sau khi ArgoCD bootstrap
kubectl apply -f phase9-gitops-platform/gitops-platform/project.yaml -n argocd

# Giai đoạn 2 — platform
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/platform-app-of-apps.yaml -n argocd

# Giai đoạn 2b — observability (chạy observability/scripts/generate-linkerd-certs.sh trước)
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/observability-app-of-apps.yaml -n argocd

# Giai đoạn 3 — infra (sửa storageClass local-path trước)
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/infra-app-of-apps.yaml -n argocd

# Giai đoạn 4 — cấu hình Jenkins, chạy pipeline, verify Harbor + values-images.yaml

# Giai đoạn 5 — banking app (SAU CI/CD)
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/banking-app-of-apps.yaml -n argocd
```

## Luồng phát triển hàng ngày (sau bootstrap)

```bash
git push origin dev-k3d   # phase8-application-v3/**
# Jenkins: Kaniko → Harbor → commit values-images.yaml
# ArgoCD: sync banking apps → rollout
```

## Cấu trúc ArgoCD

```
(platform + infra apply trước, banking apply sau CI/CD)

platform-app-of-apps      → harbor, vault, external-secrets, jenkins (wave 0–1)
observability-app-of-apps → coroot, otel-collector, linkerd (wave 0–2)
infra-app-of-apps         → postgres, redis, rabbitmq, kong (wave 0–1)
banking-app-of-apps       → namespace, services Phase 8 (wave 10, sync thủ công lần đầu)
```

Per-service banking apps dùng:

- `phase2-helm-chart/banking-demo` + `values-phase8.yaml`
- `phase9-gitops-platform/gitops/values-images.yaml` (CI cập nhật tag)
- `phase9-gitops-platform/gitops/values-observability.yaml` (OTEL + Linkerd inject)
