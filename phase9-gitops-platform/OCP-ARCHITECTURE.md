# Phase 9 — Kiến trúc OpenShift (dev-ocp)

So sánh với lab **k3d** (`dev-k3d`): không dùng **Nginx WSL2** và **Traefik Ingress** — OpenShift expose service bằng **Route** (HAProxy Router built-in).

## Sơ đồ tổng thể

![Phase 9 — OpenShift Architecture](../articles/viblo-series/assets/phase9-architecture-overview-ocp.png)

Nguồn Mermaid (chỉnh sửa / export lại): [`phase9-architecture-overview-ocp.mmd`](../articles/viblo-series/assets/phase9-architecture-overview-ocp.mmd)

## k3d vs OCP — Edge / Ingress

| | dev-k3d | dev-ocp |
|---|---------|---------|
| **TLS** | Nginx WSL2 terminate HTTPS | **Router** terminate TLS (edge) |
| **Routing** | Traefik Ingress (`ingressClassName: traefik`) | **Route** `route.openshift.io/v1` |
| **Domain** | `*-npd.co` + Windows hosts | `*.apps.ocp01.npd.co` |
| **ArgoCD** | NS `argocd`, Ingress | NS `openshift-gitops`, Route |
| **Thành phần bỏ** | Nginx, Traefik, k3d LB :9080 | — |

## Luồng request (runtime)

```text
Browser / oc
    │
    ▼
OpenShift Router (HAProxy) — TLS edge
    │
    ├── harbor-banking.apps.ocp01.npd.co     → Harbor (ns platform)
    ├── jenkins-platform.apps.ocp01.npd.co → Jenkins (ns platform)
    ├── vault-banking.apps.ocp01.npd.co      → Vault (ns vault)
    ├── openshift-gitops-server-openshift-gitops.apps... → ArgoCD UI
    ├── kong.apps.ocp01.npd.co               → Kong proxy (ns kong)
    └── npd-banking.co                       → frontend + /api,/ws → Kong (ns banking)
```

**Không có** tầng Nginx hay Traefik ở giữa.

## Luồng CI/CD (giữ nguyên logic)

```text
Git push dev-ocp
    → Jenkins (Multibranch, branch dev-ocp)
    → Kaniko build in-cluster
    → push harbor-banking.apps.ocp01.npd.co/banking-demo/<svc>:<sha>
    → commit phase9-gitops-platform/gitops/values-images.yaml
    → ArgoCD sync banking apps
```

## Mermaid (copy vào doc / Viblo)

```mermaid
flowchart TB
  subgraph DEV["Developer"]
    GH["GitHub dev-ocp"]
    DEV["Git push"] --> GH
  end

  subgraph OCP["OpenShift Cluster"]
    JEN[Jenkins + Kaniko]
    HAR[Harbor]
    ARGO[ArgoCD / GitOps]
    RT["OpenShift Router\n*.apps.ocp01.npd.co"]

    GH --> JEN
    JEN --> HAR
    JEN -->|commit values-images| GH
    GH --> ARGO
    RT --> HAR & JEN & ARGO
  end

  USER[Browser] --> RT
```

Triển khai: [OCP-DEPLOY-GUIDE.md](./OCP-DEPLOY-GUIDE.md)
