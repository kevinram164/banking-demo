#!/usr/bin/env bash
# Bootstrap ArgoCD GitOps cho nhánh dev-ocp trên OpenShift
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

# Mặc định: ArgoCD upstream (opensource) ns argocd
# Operator Red Hat: ARGOCD_NS=openshift-gitops (cần trial/subscription)
ARGOCD_NS="${ARGOCD_NS:-argocd}"
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
if [[ "$ARGOCD_NS" == "openshift-gitops" ]]; then
  echo "  ArgoCD UI: https://openshift-gitops-server-openshift-gitops.apps.ocp01.npd.co"
else
  echo "  ArgoCD UI: https://argocd-server-argocd.apps.ocp01.npd.co"
fi
echo "  Console  : https://console-openshift-console.apps.ocp01.npd.co"
