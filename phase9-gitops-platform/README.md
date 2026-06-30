# Phase 9 — GitOps Platform (Quick Start — OpenShift `dev-ocp`)

Triển khai **CI (Jenkins + Kaniko + Harbor)** và **CD (ArgoCD App of Apps)** cho banking-demo Phase 8 trên **OpenShift**.

**Hướng dẫn đầy đủ:** **[OCP-DEPLOY-GUIDE.md](./OCP-DEPLOY-GUIDE.md)**

Chi tiết kiến trúc: [PHASE9.md](./PHASE9.md) | [OCP-ARCHITECTURE.md](./OCP-ARCHITECTURE.md)

## Thứ tự triển khai (quan trọng)

| Giai đoạn | Nội dung | Deploy app? |
|-----------|----------|-------------|
| 0 | NFS CSI + StorageClass `nfs-csi` | Không |
| 1 | ArgoCD upstream + SCC + Route | Không |
| 2 | Platform: Harbor, Vault, ESO, Jenkins + Routes | Không |
| 2b | Observability: Coroot, OTEL, Linkerd (tùy chọn) | Không |
| 3 | Infra: Postgres, Redis, RabbitMQ, Kong | Không |
| 4 | CI/CD: Jenkins → Harbor → commit GitOps | Không |
| 5 | ArgoCD sync banking app | **Có** |

## Apply theo giai đoạn (`dev-ocp`)

```bash
export ARGOCD_NS=argocd

# Giai đoạn 1 — sau ArgoCD bootstrap + appproject
oc apply -f phase9-gitops-platform/environments/dev-ocp/appproject.yaml -n $ARGOCD_NS

# Giai đoạn 2 — platform + routes
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/platform-app-of-apps.yaml -n $ARGOCD_NS
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/platform-routes-app-of-apps.yaml -n $ARGOCD_NS

# Giai đoạn 2b — observability (tùy chọn)
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/observability-app-of-apps.yaml -n $ARGOCD_NS

# Giai đoạn 3 — infra
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/infra-app-of-apps.yaml -n $ARGOCD_NS

# Giai đoạn 4 — Jenkins pipeline green

# Giai đoạn 5 — banking app (SAU CI/CD)
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/banking-app-of-apps.yaml -n $ARGOCD_NS
```

## Luồng phát triển hàng ngày

```bash
git push origin dev-ocp   # phase8-application-v3/**
# Jenkins: Kaniko → Harbor → commit values-images.yaml
# ArgoCD: sync banking apps → rollout
```

## Cấu trúc ArgoCD

```
(platform + infra apply trước, banking apply sau CI/CD)

platform-app-of-apps      → harbor, vault, external-secrets, jenkins
platform-routes           → OpenShift Routes (Harbor, Jenkins, Vault, banking)
observability-app-of-apps → coroot, otel-collector, linkerd
infra-app-of-apps         → postgres, redis, rabbitmq, kong
banking-app-of-apps       → namespace, services Phase 8 (ingress Helm tắt — Route thay thế)
```

Per-service banking apps dùng:

- `phase2-helm-chart/banking-demo` + `values-phase8.yaml`
- `phase9-gitops-platform/gitops/values-images.yaml` (CI cập nhật tag)
- `phase9-gitops-platform/gitops/values-observability.yaml` (OTEL + Linkerd)

## Tài liệu môi trường

| Tài liệu | Mục đích |
|----------|----------|
| [environments/dev-ocp/](./environments/dev-ocp/) | Manifest ArgoCD + URL cluster |
| [INSTALL-NFS-CSI.md](./environments/dev-ocp/INSTALL-NFS-CSI.md) | Storage NFS |
| [INSTALL-ARGOCD-UPSTREAM.md](./environments/dev-ocp/INSTALL-ARGOCD-UPSTREAM.md) | Cài ArgoCD + SCC |
