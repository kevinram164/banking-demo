#!/usr/bin/env bash
# Install Instana OTel Collector (IDOT). Key from ESO Secret (Vault).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NS=instana-otel-collector
RELEASE=instana-otel-collector
LABEL="app.kubernetes.io/instance=${RELEASE}"

KEY="${INSTANA_KEY:-}"
if [ -z "$KEY" ]; then
  KEY="$(oc -n observability get secret instana-otlp-credentials -o jsonpath='{.data.key}' | base64 -d 2>/dev/null || true)"
fi
if [ -z "$KEY" ]; then
  echo "ERROR: no key. Seed Vault + apply ExternalSecret first." >&2
  exit 1
fi

if oc -n argocd get app observability-instana-otel-collector >/dev/null 2>&1; then
  oc -n argocd delete app observability-instana-otel-collector --wait=false || true
fi

# Namespace leftovers
if oc get ns "$NS" >/dev/null 2>&1; then
  echo "Deleting namespace $NS..."
  oc delete ns "$NS" --wait=true
fi

# Cluster-scoped leftovers from failed Argo sync (survive ns delete)
echo "Cleaning cluster-scoped orphans named ${RELEASE}-* ..."
for kind in clusterrole clusterrolebinding; do
  oc get "$kind" -o name 2>/dev/null | grep -E "${RELEASE}|instana-otel-collector" | while read -r obj; do
    echo "  delete $obj"
    oc delete "$obj" --wait=false || true
  done
done
# CRDs / operator leftovers if any
oc get crd 2>/dev/null | awk '/instana|opentelemetry.io/ {print $1}' | while read -r crd; do
  case "$crd" in
    *idot*|*instana-otel*) oc delete crd "$crd" --wait=false || true ;;
  esac
done

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
