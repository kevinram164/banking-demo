# Instana TechZone — cutover
#
# UI: https://instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com/
# OTLP: otlp-grpc.instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com:443
# clusterName: ocp01
#
# A) Shared collector (observability) — APM apps → Coroot + Instana OTLP
# B) Instana OTel Collector (IDOT) — K8s infra — cài bằng **Helm + key từ ESO**
#    (không Argo: multi-source không inject instanaKey vào helm template)

## 0. Vault → ESO (một lần)

```bash
oc exec -it vault-0 -n vault -- sh
# trong pod:
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN='...'   # lab token
vault kv put secret/platform/instana key='<INSTANA_KEY_FROM_UI>'
exit

oc apply -f phase9-gitops-platform/instana/externalsecret-otlp-credentials.yaml
oc -n observability get secret instana-otlp-credentials
```

## 1. App APM — shared OTEL collector

Values: `observability/values-otel-collector-k3d.yaml` (export `otlp/instana` → TechZone).

Secret `observability/instana-otlp-credentials` → env `INSTANA_KEY` trên collector.
Sync Argo `observability-otel-collector`, rồi restart nếu cần:

```bash
oc -n observability rollout restart deploy/opentelemetry-collector
oc -n observability set env deploy/opentelemetry-collector --list | grep INSTANA
```

## 2. K8s infra — IDOT (Helm, key từ ESO)

```bash
# Xóa Argo app đang ComparisonError (nếu còn)
oc -n argocd delete app observability-instana-otel-collector --wait=false

chmod +x phase9-gitops-platform/instana/scripts/install-idot.sh
./phase9-gitops-platform/instana/scripts/install-idot.sh

oc -n instana-otel-collector get ds,sts,pods
```

Script lấy key từ `secret/instana-otlp-credentials` (ESO ← Vault), `--set instanaKey=...`.
**Không** ghi key vào `values-idot-ocp.yaml`.

## 3. Verify Instana UI

1. Infrastructure → cluster **ocp01**
2. Applications → OpenTelemetry services
3. Filter: Call technology = OpenTelemetry

## Ghi chú

- Browser "Not secure" → shared collector dùng `tls.insecure_skip_verify: true`
- Host agent: xem **[TROUBLESHOOTING-HOST-AGENT.md](./TROUBLESHOOTING-HOST-AGENT.md)** (timeout 1443, 404 NR trên :443, sửa Core `acceptors.agent.port`)
- **ALPN / Not Monitoring:** nếu log có `missing selected ALPN property` → LB TechZone
  không negotiate HTTP/2 cho gRPC. Set `GRPC_ENFORCE_ALPN_ENABLED=false` trên DS/STS
  (đã có trong `values-idot-ocp.yaml`) rồi `helm upgrade` lại.
