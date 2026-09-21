#!/usr/bin/env bash
# Install Instana OTel Collector (IDOT). Key from ESO Secret (Vault).
# Not Argo: OCP GitOps multi-source drops instanaKey during helm template.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NS=instana-otel-collector
RELEASE=instana-otel-collector

KEY="${INSTANA_KEY:-}"
if [ -z "$KEY" ]; then
  KEY="$(oc -n observability get secret instana-otlp-credentials -o jsonpath='{.data.key}' | base64 -d 2>/dev/null || true)"
fi
if [ -z "$KEY" ]; then
  echo "ERROR: no key. Seed Vault + apply ExternalSecret first." >&2
  exit 1
fi

# Remove broken Argo app if still present
if oc -n argocd get app observability-instana-otel-collector >/dev/null 2>&1; then
  oc -n argocd delete app observability-instana-otel-collector --wait=false || true
fi

# Orphaned resources from failed Argo sync block helm adopt — wipe ns and reinstall
if oc get ns "$NS" >/dev/null 2>&1; then
  echo "Deleting namespace $NS (orphaned non-Helm resources)..."
  oc delete ns "$NS" --wait=true
fi

helm repo add instana-otel https://instana.github.io/instana-otel-collector 2>/dev/null || true
helm repo update instana-otel >/dev/null

helm upgrade --install "$RELEASE" instana-otel/instana-otel-collector-chart \
  --namespace "$NS" \
  --create-namespace \
  -f "$ROOT/values-idot-ocp.yaml" \
  --set "instanaKey=${KEY}" \
  --wait --timeout 15m

echo "---"
oc -n "$NS" get ds,sts,pods
echo "OK — key from ESO secret observability/instana-otlp-credentials"
echo "UI: https://instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com/"