# Instana TechZone — cutover theo UI "Agents → Kubernetes - Helm Chart"
#
# UI: https://instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com/
# OTLP: otlp-grpc.instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com:443
# clusterName: ocp01
#
# Hai lớp (cả hai đều dùng cùng instanaKey):
#   A) Shared collector (observability) — APM từ banking/shop/movie/aiops → Coroot + Instana
#   B) Instana OTel Collector chart (IDOT) — K8s infra (đúng lệnh Helm trên UI)

## 0. Secret (không commit key vào git)

Lấy key từ lệnh Helm trên UI (`--set instanaKey=...`). Chọn **một** trong hai cách dưới.

### Cách A — Vault + ExternalSecret (khuyến nghị)

Path Vault: `secret/platform/instana` · property `key`  
→ ESO tạo K8s Secret `instana-otlp-credentials` (ns `observability`).

```bash
# 1) Seed key vào Vault (trong pod vault-0, token lab thường là root)
oc exec -it vault-0 -n vault -- sh

vault kv put secret/platform/instana \
  key='WUinQgrHRCSVCdvntU5UhA'

# Kiểm tra
vault kv get secret/platform/instana
exit

# 2) ExternalSecret → Secret K8s
oc apply -f phase9-gitops-platform/instana/externalsecret-otlp-credentials.yaml

# 3) Đợi sync
oc -n observability get externalsecret instana-otlp-credentials
oc -n observability get secret instana-otlp-credentials
```

Đổi key sau này: `vault kv put` lại → ESO refresh (tối đa `refreshInterval: 1h`) hoặc:

```bash
oc -n observability annotate externalsecret instana-otlp-credentials \
  force-sync=$(date +%s) --overwrite
```

### Cách B — Secret K8s trực tiếp (lab nhanh, bỏ qua Vault)

```bash
oc create namespace observability --dry-run=client -o yaml | oc apply -f -
oc -n observability create secret generic instana-otlp-credentials \
  --from-literal=key='WUinQgrHRCSVCdvntU5UhA' \
  --dry-run=client -o yaml | oc apply -f -
```

## 1. App APM — cập nhật shared OTEL collector

Values đã trỏ `otlp/instana` → TechZone OTLP gRPC (không còn local `instana-agent`):

- `observability/values-otel-collector-k3d.yaml`

Sync Argo `observability-otel-collector` (hoặc helm upgrade chart hiện có).

App **không đổi** `OTEL_EXPORTER_OTLP_ENDPOINT` — vẫn gửi collector nội bộ.

```bash
# Verify collector có env INSTANA_KEY
kubectl -n observability set env deploy/opentelemetry-collector --list | grep INSTANA
kubectl -n observability logs deploy/opentelemetry-collector --tail=80
```

## 2. K8s infra — Instana OTel Collector

**Key chỉ ở Vault** (`secret/platform/instana`). Không đưa vào `values-idot-ocp.yaml`.

OCP GitOps multi-source **không** merge Secret/`valuesFrom` vào `helm template` → sau khi apply Application phải patch `helm.parameters` từ Secret ESO (đã sync Vault), hoặc cài bằng Helm CLI.

```bash
# ESO đã sync? (Vault → Secret)
oc -n observability get secret instana-otlp-credentials

# Cách 1 — Argo: patch key từ Vault/ESO rồi sync
oc apply -f phase9-gitops-platform/gitops-platform/applications/observability/instana-otel-collector.yaml
chmod +x phase9-gitops-platform/instana/scripts/sync-idot-key-from-vault.sh
./phase9-gitops-platform/instana/scripts/sync-idot-key-from-vault.sh

# Cách 2 — Helm CLI (không Argo), key cũng từ Vault/ESO
./phase9-gitops-platform/instana/scripts/install-idot.sh

oc -n instana-otel-collector get ds,sts,pods
```

## 3. Verify trên Instana UI mới

1. Infrastructure → cluster **ocp01** (từ IDOT / K8s sensor).
2. Applications → OpenTelemetry services (`api-producer`, `noli-shop-gateway`, `movie-api`, …).
3. Filter: Call technology = OpenTelemetry; tag `kubernetes.namespace.name`.

## Ghi chú

- Browser báo "Not secure" → collector dùng `tls.insecure_skip_verify: true`.
- Host agent (`instana-agent`) cũ: không bắt buộc cho path UI này; có thể gỡ sau khi APM + infra OK trên TechZone.
- Key lộ trên screenshot chat → nên rotate trên Instana UI nếu cluster public.
