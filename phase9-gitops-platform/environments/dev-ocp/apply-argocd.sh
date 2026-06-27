#!/usr/bin/env bash
# Bootstrap ArgoCD GitOps cho nhánh dev-ocp trên OpenShift
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

# openshift-gitops (Operator) hoặc argocd (cài thủ công)
ARGOCD_NS="${ARGOCD_NS:-openshift-gitops}"
CLI="${CLI:-oc}"

echo "==> ArgoCD namespace: $ARGOCD_NS"
$CLI get ns "$ARGOCD_NS" >/dev/null 2>&1 || { echo "Namespace $ARGOCD_NS not found"; exit 1; }

echo "==> Apply AppProject"
$CLI apply -f phase9-gitops-platform/environments/dev-ocp/appproject.yaml -n "$ARGOCD_NS"

echo "==> Apply dev-ocp App of Apps"
$CLI apply -f phase9-gitops-platform/environments/dev-ocp/argocd/app-of-apps.yaml -n "$ARGOCD_NS"

echo "Done."
echo "  Root app : banking-platform-root-dev-ocp"
echo "  Branch   : dev-ocp"
echo "  ArgoCD UI: https://openshift-gitops-server-${ARGOCD_NS}.apps.ocp01.npd.co"
echo "  Console  : https://console-openshift-console.apps.ocp01.npd.co"
