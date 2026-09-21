#!/usr/bin/env bash
# Install IDOT bằng Helm — key từ Vault/ESO Secret (không commit).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY="${INSTANA_KEY:-}"
if [[ -z "$KEY" ]]; then
  KEY="$(oc -n observability get secret instana-otlp-credentials -o jsonpath='{.data.key}' | base64 -d)"
fi
[[ -n "$KEY" ]] || { echo "ERROR: set INSTANA_KEY or create observability/instana-otlp-credentials" >&2; exit 1; }

helm upgrade --install instana-otel-collector \
  --repo https://instana.github.io/instana-otel-collector \
  instana-otel-collector-chart \
  --namespace instana-otel-collector \
  --create-namespace \
  -f "$ROOT/values-idot-ocp.yaml" \
  --set "instanaKey=${KEY}" \
  --wait --timeout 15m

kubectl -n instana-otel-collector get ds,sts,pods
echo "IDOT OK → https://instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com/"
