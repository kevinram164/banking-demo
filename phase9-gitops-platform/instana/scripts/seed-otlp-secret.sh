#!/usr/bin/env bash
# Seed OTLP credentials + restart shared collector (app APM → TechZone).
# Usage:
#   export INSTANA_KEY='...'
#   ./phase9-gitops-platform/instana/scripts/seed-otlp-secret.sh
set -euo pipefail

KEY="${INSTANA_KEY:?set INSTANA_KEY from Instana UI}"

kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -
kubectl -n observability create secret generic instana-otlp-credentials \
  --from-literal=key="$KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# Roll collector nếu đã deploy (lấy key mới)
if kubectl -n observability get deploy opentelemetry-collector >/dev/null 2>&1; then
  kubectl -n observability rollout restart deploy/opentelemetry-collector
  kubectl -n observability rollout status deploy/opentelemetry-collector --timeout=180s
fi

echo "Secret instana-otlp-credentials ready in ns observability"
