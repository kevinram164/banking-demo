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

Lấy key từ lệnh Helm trên UI (`--set instanaKey=...`).

```bash
# Nhanh — ns observability (collector app)
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -
kubectl -n observability create secret generic instana-otlp-credentials \
  --from-literal=key='<INSTANA_KEY_FROM_UI>' \
  --dry-run=client -o yaml | kubectl apply -f -

# Vault (khuyến nghị)
# vault kv put secret/platform/instana key='<INSTANA_KEY_FROM_UI>'
kubectl apply -f phase9-gitops-platform/instana/externalsecret-otlp-credentials.yaml
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

## 2. K8s infra — đúng lệnh UI (Instana OTel Collector)

```bash
helm upgrade --install instana-otel-collector \
  --repo https://instana.github.io/instana-otel-collector \
  instana-otel-collector-chart \
  --namespace instana-otel-collector \
  --create-namespace \
  --set clusterName=ocp01 \
  --set instanaEndpoint=otlp-grpc.instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com:443 \
  --set instanaKey='<INSTANA_KEY_FROM_UI>'
```

Hoặc values + script:

```bash
export INSTANA_KEY='...'
./phase9-gitops-platform/instana/scripts/install-idot.sh
```

Argo (sau khi AppProject có repo `https://instana.github.io/instana-otel-collector`):

```bash
kubectl apply -f phase9-gitops-platform/gitops-platform/applications/observability/instana-otel-collector.yaml
```

## 3. Verify trên Instana UI mới

1. Infrastructure → cluster **ocp01** (từ IDOT / K8s sensor).
2. Applications → OpenTelemetry services (`api-producer`, `noli-shop-gateway`, `movie-api`, …).
3. Filter: Call technology = OpenTelemetry; tag `kubernetes.namespace.name`.

## Ghi chú

- Browser báo "Not secure" → collector dùng `tls.insecure_skip_verify: true`.
- Host agent (`instana-agent`) cũ: không bắt buộc cho path UI này; có thể gỡ sau khi APM + infra OK trên TechZone.
- Key lộ trên screenshot chat → nên rotate trên Instana UI nếu cluster public.
