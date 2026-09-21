#!/usr/bin/env bash
# CÃ i Instana OTel Collector (IDOT) â€” key láº¥y tá»« ESO Secret (Vault).
# KhÃ´ng dÃ¹ng Argo cho chart nÃ y: OCP GitOps multi-source bá» valuesFrom/parameters
# khi helm template â†’ luÃ´n thiáº¿u instanaKey.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NS=instana-otel-collector

KEY="${INSTANA_KEY:-}"
if [[ -z "$KEY" ]]; then
  KEY="$(oc -n observability get secret instana-otlp-credentials -o jsonpath='{.data.key}' | base64 -d 2>/dev/null || true)"
fi
[[ -n "$KEY" ]] || {
  echo "ERROR: khÃ´ng cÃ³ key. Seed Vault + apply ExternalSecret trÆ°á»›c:" >&2
  echo "  vault kv put secret/platform/instana key='...'" >&2
  echo "  oc apply -f phase9-gitops-platform/instana/externalsecret-otlp-credentials.yaml" >&2
  exit 1
}

# Táº¯t Argo app lá»—i (náº¿u cÃ²n) â€” trÃ¡nh ComparisonError / orphaned
if oc -n argocd get app observability-instana-otel-collector >/dev/null 2>&1; then
  oc -n argocd delete app observability-instana-otel-collector --wait=false || true
  echo "Deleted Argo Application observability-instana-otel-collector (Helm lÃ  source of truth)."
fi

helm repo add instana-otel https://instana.github.io/instana-otel-collector 2>/dev/null || true
helm repo update instana-otel 2>/dev/null || true

helm upgrade --install instana-otel-collector instana-otel/instana-otel-collector-chart \
  --namespace "$NS" \
  --create-namespace \
  -f "$ROOT/values-idot-ocp.yaml" \
  --set "instanaKey=${KEY}" \
  --wait --timeout 15m

echo "---"
oc -n "$NS" get ds,sts,pods
echo "OK â€” key tá»« ESO Secret observability/instana-otlp-credentials"
echo "UI: https://instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com/"
