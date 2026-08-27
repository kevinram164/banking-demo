# Istio Ambient — GitOps (cả 4 product)

Control plane **một lần** (repo `banking-demo`). Policy **từng product** (repo tương ứng).

Runbook: [`environments/dev-ocp/INSTALL-ISTIO-AMBIENT.md`](../environments/dev-ocp/INSTALL-ISTIO-AMBIENT.md)

![Bốn product](../environments/dev-ocp/assets/ocp-istio-ambient-four-products.png)

## Đợt B — control plane (banking-demo)

| Path | Việc |
|------|--------|
| `mesh/operator/` | Subscription OSSM 3 + Kiali |
| `mesh/control-plane/` | Namespace + `Istio` ambient + `IstioCNI` |
| `mesh/ztunnel/` | `ZTunnel` |
| `mesh/kiali/` | Kiali CR + Route |
| `environments/dev-ocp/argocd/applications/mesh-app-of-apps.yaml` | App of Apps |

```bash
# OVN routingViaHost=true (tay, xem INSTALL)
oc apply -f phase9-gitops-platform/environments/dev-ocp/appproject.yaml -n argocd
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/mesh-app-of-apps.yaml
```

**Không enroll:** `kafka`, `postgres`, `redis`, `rabbit`, `minio`, `aiops-automation`, `openshift-*`.

## Đợt C–G — từng app (đồng cấp, không chỉ shop)

| Product | Namespace | Repo / path | Identity (SA) | Zero-trust |
|---------|-----------|-------------|---------------|------------|
| **Banking** | `npd-banking` + `kong` | `mesh/workloads/` (wave 5 cùng app-of-apps) | Helm `templates/mesh-serviceaccounts.yaml` | Kong → `api-producer:8080`, `notification-service:8004`. **Không** HTTP từ shop. Frontend Route PERMISSIVE. |
| **Shop** | `npd-shop` | `npd-shop/deploy/mesh/` + `deploy/argocd/npd-shop-mesh.yaml` | Helm `charts/shop/templates/serviceaccounts.yaml` | gateway → auth/catalog/order/payment. **Không** HTTP sang banking. |
| **Movie** | `npd-movie` | `movie-web/deploy/mesh/` + `deploy/argocd/cinehome-mesh.yaml` | Helm `charts/movie/templates/serviceaccounts.yaml` | movie-web → movie-api. **Exclude** cloudflared. |
| **AIOps** | `aiops-core` only | `Open-Source-AIOps-Platform/gitops/mesh/` + Application `aiops-mesh` | incident-api / rca-agent / aiops-console / ollama (đã có SA) | PERMISSIVE webhook. **Không** mesh `aiops-automation`. **Không** gọi API app. |

Shop↔bank = **Kafka**. Movie cô lập. AIOps đọc Prometheus/Coroot.

## Đợt H — waypoint (không auto-sync)

`gitops-platform/applications/mesh/waypoint.yaml` — Application `mesh-waypoint` **không** automated. HTTPRoute weight 0/100 trên `api-producer` (banking) và `order-service` (shop).
