#!/usr/bin/env bash
# Bootstrap ArgoCD GitOps cho nhánh dev-k3d trên cluster k3d-npd
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

echo "==> Apply AppProject"
kubectl apply -f phase9-gitops-platform/argocd/project.yaml -n argocd

echo "==> Apply dev-k3d App of Apps"
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/app-of-apps.yaml -n argocd

echo "Done. Open ArgoCD: https://argocd-npd.co"
echo "Root app: banking-platform-root-dev-k3d"
echo "Branch: dev-k3d (ensure repo connected in ArgoCD)"
