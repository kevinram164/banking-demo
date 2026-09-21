#!/usr/bin/env bash
# Install Instana OTel Collector (IDOT) — đúng lệnh UI TechZone.
# Usage:
#   export INSTANA_KEY='<from UI --set instanaKey=...>'
#   ./phase9-gitops-platform/instana/scripts/install-idot.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY="${INSTANA_KEY:?set INSTANA_KEY from Instana UI Helm command}"

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
