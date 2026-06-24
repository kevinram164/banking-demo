#!/usr/bin/env bash
# Cài Linkerd Viz trên k3d khi ArgoCD sync kẹt (không cần argocd CLI).
set -euo pipefail

NS=linkerd-viz
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

echo ">>> Kiểm tra control-plane (phải Running trước)"
kubectl get pods -n linkerd
kubectl get pods -n linkerd | grep -E 'destination|identity|proxy-injector' | grep -v Running && {
  echo "Control-plane chưa Ready — sync observability-linkerd-control-plane trên ArgoCD UI trước."
  exit 1
} || true

echo ">>> Helm install linkerd-viz"
helm repo add linkerd https://helm.linkerd.io/stable 2>/dev/null || true
helm repo update linkerd

helm upgrade --install linkerd-viz linkerd/linkerd-viz \
  -n "$NS" --create-namespace \
  --version 30.12.11 \
  --set linkerdNamespace=linkerd \
  --set dashboard.enforcedHostRegexp='.*' \
  --set metricsAPI.resources.cpu.request=50m \
  --set metricsAPI.resources.memory.limit=256Mi \
  --set tap.resources.cpu.request=50m \
  --set tap.resources.memory.limit=256Mi \
  --set tapInjector.resources.cpu.request=50m \
  --set tapInjector.resources.memory.limit=128Mi

echo ">>> Ingress UI"
kubectl apply -f "${REPO_ROOT}/k3d/linkerd-viz-ingress.yaml"

echo ">>> Theo dõi pods"
kubectl get pods -n "$NS" -w
