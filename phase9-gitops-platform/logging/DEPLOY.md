# Logging — OpenSearch (bank / shop / movie / infra)

Lab OCP: thu stdout → Fluent Bit → **4 nhóm index** → Dashboards.

```text
Pod logs ──► Fluent Bit ──► OpenSearch
                              ├── logs-bank-YYYY.MM.DD    (npd-banking)
                              ├── logs-shop-YYYY.MM.DD    (npd-shop)
                              ├── logs-movie-YYYY.MM.DD   (npd-movie)
                              └── logs-infra-YYYY.MM.DD   (kafka, platform, observability, …)
ISM: xóa index sau 7 ngày
```

| Nhóm | Namespaces | Index pattern (Dashboards) |
|------|------------|----------------------------|
| bank | `npd-banking` | `logs-bank-*` |
| shop | `npd-shop` | `logs-shop-*` |
| movie | `npd-movie` | `logs-movie-*` |
| infra | `kafka`, `platform`, `observability`, `logging`, `argocd`, `kong`, `vault`, `postgres`, `redis`, `rabbit`, `minio`, `external-secrets` | `logs-infra-*` |

**Không thay** Coroot / Instana / Kafka UI.

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

### 0b. SCC UID 1000 (bắt buộc trên OCP)

Image OpenSearch/Dashboards chạy `runAsUser: 1000` — `restricted-v2` của ns `logging` không cho phép → `FailedCreate`.

**Sửa ngay (không chờ git):**

```bash
cd D:/Tai-lieu/LPI-DOCKER-K8S/OCP/banking-demo

# Git Bash / WSL / Linux jump host:
bash phase9-gitops-platform/environments/dev-ocp/scripts/opensearch-scc-setup.sh

# hoặc từng lệnh:
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/scc/opensearch-scc.yaml
oc adm policy add-scc-to-user opensearch-uid1000 -z default -n logging
oc adm policy add-scc-to-user opensearch-uid1000 -z opensearch -n logging
oc adm policy add-scc-to-user opensearch-uid1000 -z opensearch-dashboards -n logging
oc -n logging delete pod --all --force --grace-period=0
oc -n logging get pods -w
```

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

### 4. Index patterns (Dashboards)

Management → Index patterns — tạo **4** pattern (time: `@timestamp`):

| Pattern | Dùng cho |
|---------|----------|
| `logs-bank-*` | Banking |
| `logs-shop-*` | Shop |
| `logs-movie-*` | Movie / CineHome |
| `logs-infra-*` | Kafka, Harbor, Jenkins, Coroot, … |

Retention: policy ISM `logs-retention-7d` (Job/CronJob trong `manifests/ism-retention.yaml`) — index > **7 ngày** → delete.

```bash
oc -n logging logs job/opensearch-ism-retention --tail=30
oc -n logging exec sts/npd-logs-master -- \
  curl -sS http://127.0.0.1:9200/_plugins/_ism/policies/logs-retention-7d | head -c 500
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
  curl -sS 'http://127.0.0.1:9200/_cat/indices/logs-.*?v'
```

Khi thấy index `logs-…` và document từ các ns → **bắt đầu cron ecosystem** (`scripts/ecosystem/`).

### Apply ISM 7 ngày ngay (không chờ Argo)

```bash
oc -n logging exec sts/npd-logs-master -- curl -sS -X PUT \
  'http://127.0.0.1:9200/_plugins/_ism/policies/logs-retention-7d' \
  -H 'Content-Type: application/json' \
  -d '{
  "policy": {
    "description": "Delete logs-* after 7 days",
    "default_state": "hot",
    "states": [
      {"name":"hot","actions":[],"transitions":[{"state_name":"delete","conditions":{"min_index_age":"7d"}}]},
      {"name":"delete","actions":[{"delete":{}}],"transitions":[]}
    ],
    "ism_template":[{
      "index_patterns":["logs-bank-*","logs-shop-*","logs-movie-*","logs-infra-*"],
      "priority":100
    }]
  }
}'
```

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
| OpenSearch CrashLoop `initial_master_nodes` + `single-node` | Set `singleNode: true` trong values (đã có); sync Argo `logging-opensearch` rồi `oc -n logging delete pod npd-logs-master-0` |
| Dashboards: `ENOTFOUND npd-logs-master` / "server is not ready yet" | `oc -n logging get svc,pods` — cần Service `npd-logs-master` + pod OpenSearch Running; sync `singleNode` fix; Dashboards host FQDN trong values |
| PVC Pending | Kiểm tra `nfs-csi` + NFS server |
| Fluent Bit CrashLoop `unknown configuration property 'condition'` | Filter `parser` FB 3.2 không có `Condition` — sync Git + sync Argo `logging-fluent-bit` |
| Fluent Bit `filter initialization failed` | `oc -n logging logs ds/fluent-bit` — config filter lỗi |
| Fluent Bit `403` / SCC | `oc adm policy add-scc-to-user fluent-bit-npd -z fluent-bit -n logging` (chart thường tự tạo SCC) |
| Không có log app | Đợi 1–2 phút; kiểm tra grep namespace; pod có stdout |
| Dashboards trống | Tạo index pattern `npd-*`; kiểm tra `_cat/indices` |

## Tài nguyên lab (gợi ý)

| Component | Request | Limit |
|-----------|---------|-------|
| OpenSearch | 0.5 CPU / 2Gi | 2 CPU / 4Gi |
| Dashboards | 0.1 / 512Mi | 1 / 1Gi |
| Fluent Bit / node | 50m / 64Mi | 500m / 256Mi |
