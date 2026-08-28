# Istio Ambient — GitOps (cả 4 product)

Control plane **một lần** (repo `banking-demo`). Policy **từng product** (repo tương ứng).

Runbook: [`environments/dev-ocp/INSTALL-ISTIO-AMBIENT.md`](../environments/dev-ocp/INSTALL-ISTIO-AMBIENT.md)

![Bốn product](../environments/dev-ocp/assets/ocp-istio-ambient-four-products.png)

## Đợt B — control plane (banking-demo)

| Path | Việc |
|------|--------|
| `mesh/operator/` | Subscription OSSM 3 + Kiali |
| `mesh/control-plane/` | Namespace + `Istio` ambient + Telemetry/ServiceMonitor (**không** IstioCNI — xem `mesh/bootstrap/`) |
| `mesh/ztunnel/` | PodMonitor ztunnel (**không** ZTunnel CR — bootstrap tay) |
| `mesh/bootstrap/` | **Apply tay:** `IstioCNI` + `ZTunnel` `profile: ambient` |
| `mesh/kiali/` | Kiali CR + Route (**Prometheus = UWM**, không phải platform Thanos) |
| `environments/dev-ocp/argocd/applications/mesh-app-of-apps.yaml` | App of Apps |

```bash
# OVN routingViaHost=true (tay, xem INSTALL)
oc apply -f phase9-gitops-platform/environments/dev-ocp/appproject.yaml -n argocd
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/mesh-app-of-apps.yaml
```

**Không enroll cả ns.** Ambient **theo pod**:

| | Ambient | `dataplane-mode=none` (Route / scrape) |
|--|---------|----------------------------------------|
| Banking | auth, account, transfer, notification, api-producer, shop-bridge | frontend, kong-proxy-bridge |
| Shop | gateway, auth, catalog, order, payment | shop-web |
| Movie | movie-api, media-worker | movie-web, cloudflared |
| Kong / AIOps | — | cả ns; không gắn dataplane ns |

**Không enroll:** `kafka`, `postgres`, `redis`, `rabbit`, `minio`, `aiops-automation`, `openshift-*`.

## Kiali graph — không có traffic (Ambient)

Topology có node nhưng **không có mũi tên** = Prometheus **chưa có** `istio_tcp_*` từ ztunnel.

1. UWM bật (`enableUserWorkload: true` — xem `monitoring/DEPLOY.md`).
2. Sync `mesh-control-plane` (Telemetry + istiod ServiceMonitor) và `mesh-ztunnel` (PodMonitor).
3. Kiali trỏ **Thanos Querier** (`openshift-monitoring:9091`) — gộp UWM, không trỏ thẳng `prometheus-user-workload:9092`.
4. RBAC (một lần): `oc adm policy add-cluster-role-to-user cluster-monitoring-view -z kiali-service-account -n kiali`
5. Verify trên bastion:

```bash
# Target scrape ztunnel
oc -n openshift-user-workload-monitoring get prometheus -o yaml | grep -A2 istio-ztunnel || true
# Metric (sau vài phút + có traffic shop)
oc exec -n openshift-user-workload-monitoring prometheus-user-workload-0 -c prometheus -- \
  wget -qO- --header="Authorization: Bearer $(cat /var/run/secrets/kubernetes.io/serviceaccount/token)" \
  'http://localhost:9090/api/v1/query?query=istio_tcp_received_bytes_total{namespace="npd-shop"}' | head -c 500

curl -sk https://npd-shop.co/ >/dev/null
# Kiali → Display → Traffic: Tcp + ZTunnel; time range 15m
```

Chưa có waypoint → chỉ **L4/TCP** trên graph (đủ thấy gateway → auth/catalog/order). HTTP status/latency cần đợt H (waypoint).

## Kiali — Prometheus disabled / 404

**Không** dùng `prometheus-user-workload:9092` trực tiếp (kube-rbac-proxy → 404). Dùng **Thanos Querier**:

```yaml
url: "https://thanos-querier.openshift-monitoring.svc:9091"
health_check_url: "https://thanos-querier.openshift-monitoring.svc:9091/-/healthy"
thanos_proxy:
  enabled: true
```

RBAC: `cluster-monitoring-view` cho SA `kiali-service-account` + `kiali` trong ns `kiali`.

Verify từ cluster:

```bash
TOKEN=$(oc create token kiali-service-account -n kiali)
oc run promtest --rm -i --restart=Never --image=curlimages/curl -n kiali -- \
  curl -sk -H "Authorization: Bearer $TOKEN" \
  "https://thanos-querier.openshift-monitoring.svc:9091/api/v1/query?query=istio_tcp_received_bytes_total{source_workload_namespace=\"npd-shop\"}" | head -c 400
```

## ztunnel.sock NotFound

Xem [`INSTALL-ISTIO-AMBIENT.md`](../environments/dev-ocp/INSTALL-ISTIO-AMBIENT.md) mục **10.1** — `IstioCNI` + `ZTunnel` phải có `profile: ambient`.

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
