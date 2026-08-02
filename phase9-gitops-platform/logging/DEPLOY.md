# Logging — OpenSearch (bank + shop + Kafka)

Lab OCP: thu **stdout JSON** từ namespace `npd-banking`, `npd-shop`, `kafka` → **OpenSearch** → **Dashboards**.

```text
Pod logs (CRI) ──► Fluent Bit (DaemonSet) ──► OpenSearch :9200
                                              └── Dashboards :5601
                                                    Route: logs-platform.apps.ocp01.npd.co
```

| Thành phần | Ns | Vai trò |
|------------|-----|---------|
| OpenSearch single-node | `logging` | Index `npd-YYYY.MM.DD` |
| OpenSearch Dashboards | `logging` | UI search |
| Fluent Bit | `logging` | Shipper, filter 3 ns |

**Không thay** Coroot / Instana / Kafka UI — chúng vẫn dùng cho metrics, eBPF, topic browse.

## Deploy (dev-ocp)

### 0. Prerequisite node

OpenSearch cần `vm.max_map_count ≥ 262144` trên worker:

```bash
# kiểm tra
oc debug node/<node> -- chroot /host sysctl vm.max_map_count
# nếu thấp — MachineConfig hoặc tạm:
oc debug node/<node> -- chroot /host sysctl -w vm.max_map_count=262144
```

StorageClass: `nfs-csi` (đã dùng lab).

### 1. AppProject (live apply — git push không đủ)

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/appproject.yaml -n argocd
```

Whitelist thêm: ns `logging`, Helm OpenSearch + Fluent Bit.

### 2. Push nhánh `dev-ocp` rồi apply app-of-apps

```bash
git push origin dev-ocp

oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/logging-app-of-apps.yaml -n argocd
```

Argo tạo: `logging-opensearch` → `logging-opensearch-dashboards` → `logging-fluent-bit` → `logging-routes`.

### 3. Chờ Ready

```bash
oc -n logging get pods,pvc,route
oc -n logging logs deploy/npd-logs-master --tail=50
# curl nội bộ
oc -n logging exec deploy/npd-logs-master -- curl -sS http://127.0.0.1:9200
```

Dashboards: https://logs-platform.apps.ocp01.npd.co

### 4. Index pattern (lần đầu)

Trong Dashboards → Management → Index patterns:

- Pattern: `npd-*`
- Time field: `@timestamp`

Discover → filter:

```
kubernetes.namespace_name: npd-banking
kubernetes.namespace_name: npd-shop
kubernetes.namespace_name: kafka
```

### 5. Verify trước khi chạy ecosystem jobs

```bash
# tạo traffic nhẹ
curl -sk https://npd-banking.co/api/auth/health || true
curl -sk https://npd-shop.co/api/products | head -c 200

# Fluent Bit đang gửi?
oc -n logging logs ds/fluent-bit --tail=30
# OpenSearch có index?
oc -n logging exec deploy/npd-logs-master -- \
  curl -sS 'http://127.0.0.1:9200/_cat/indices/npd-*?v'
```

Khi thấy index `npd-…` và document từ 3 ns → **bắt đầu cron ecosystem** (`scripts/ecosystem/`).

## Monitor checklist (khi chạy job)

| Mục | URL / lệnh |
|-----|------------|
| App logs bank/shop/kafka | https://logs-platform.apps.ocp01.npd.co (`npd-*`) |
| Service map / eBPF | https://coroot-platform.apps.ocp01.npd.co |
| Kafka topics/messages | https://kafka-ui-platform.apps.ocp01.npd.co |
| Job runner logs | `/opt/npd-ecosystem/logs/` trên server cron |

Gợi ý query OpenSearch khi smoke job:

- `kubernetes.labels.app` / `container_name: transfer-service` + `NOLI`
- `container_name: shop-bridge` + `payment`
- `namespace_name: kafka` + `ERROR`

## Files

| Path | Mô tả |
|------|--------|
| `logging/values-opensearch.yaml` | Single-node, PVC 50Gi, security off (lab) |
| `logging/values-opensearch-dashboards.yaml` | UI |
| `logging/values-fluent-bit.yaml` | Filter 3 ns → `npd-YYYY.MM.DD` |
| `logging/manifests/namespace-route.yaml` | Route Dashboards |
| `gitops-platform/applications/logging/*` | Argo Applications |

## Troubleshoot

| Triệu chứng | Xử lý |
|-------------|--------|
| OpenSearch CrashLoop `max virtual memory` | Tăng `vm.max_map_count` trên node |
| PVC Pending | Kiểm tra `nfs-csi` + NFS server |
| Fluent Bit `403` / SCC | `oc adm policy add-scc-to-user fluent-bit-npd -z fluent-bit -n logging` (chart thường tự tạo SCC) |
| Không có log app | Đợi 1–2 phút; kiểm tra grep namespace; pod có stdout |
| Dashboards trống | Tạo index pattern `npd-*`; kiểm tra `_cat/indices` |

## Tài nguyên lab (gợi ý)

| Component | Request | Limit |
|-----------|---------|-------|
| OpenSearch | 0.5 CPU / 2Gi | 2 CPU / 4Gi |
| Dashboards | 0.1 / 512Mi | 1 / 1Gi |
| Fluent Bit / node | 50m / 64Mi | 500m / 256Mi |
