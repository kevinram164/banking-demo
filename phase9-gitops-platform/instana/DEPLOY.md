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

## 2. K8s infra — Instana OTel Collector (Argo)

Chart **bắt buộc** `instanaKey`. Flow: **Vault → ExternalSecret → Secret K8s** → Argo `valuesFrom` (không tạo Secret tay nếu đã seed Vault).

### 2a. Sync từ Vault (đã `vault kv put secret/platform/instana`)

```bash
# Tạo ExternalSecret → Secret:
#   observability/instana-otlp-credentials  (collector app)
#   argocd/instana-idot-helm-values         (Argo helm valuesFrom)
oc apply -f phase9-gitops-platform/instana/externalsecret-otlp-credentials.yaml

# Đợi ESO sync
oc -n argocd get externalsecret instana-idot-helm-values
oc -n argocd get secret instana-idot-helm-values
oc -n observability get secret instana-otlp-credentials

# Lỗi sync? force
oc -n argocd annotate externalsecret instana-idot-helm-values force-sync=$(date +%s) --overwrite
```

### 2b. Apply App + sync

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/appproject.yaml -n argocd
oc apply -f phase9-gitops-platform/gitops-platform/applications/observability/instana-otel-collector.yaml
# Refresh trên Argo UI
```

### 2c. Fallback — Helm CLI (không dùng Argo)

```bash
export INSTANA_KEY='...'   # cùng giá trị trong Vault
./phase9-gitops-platform/instana/scripts/install-idot.sh
```

## 3. Verify trên Instana UI mới

1. Infrastructure → cluster **ocp01** (từ IDOT / K8s sensor).
2. Applications → OpenTelemetry services (`api-producer`, `noli-shop-gateway`, `movie-api`, …).
3. Filter: Call technology = OpenTelemetry; tag `kubernetes.namespace.name`.

## Ghi chú

- Browser báo "Not secure" → collector dùng `tls.insecure_skip_verify: true`.
- Host agent (`instana-agent`) cũ: không bắt buộc cho path UI này; có thể gỡ sau khi APM + infra OK trên TechZone.
- Key lộ trên screenshot chat → nên rotate trên Instana UI nếu cluster public.
