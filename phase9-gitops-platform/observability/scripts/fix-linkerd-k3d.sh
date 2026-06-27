#!/usr/bin/env bash
# Fix Linkerd k3d — chạy sau git pull.
set -euo pipefail

NS=linkerd
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
IDENTITY_KUSTOMIZE="${REPO_ROOT}/phase9-gitops-platform/observability/manifests/linkerd-identity-k3d"

echo ">>> 1/3 Identity bootstrap"
# Secret type immutable — phải xóa rồi tạo lại nếu đang Opaque
if kubectl get secret linkerd-identity-issuer -n "$NS" &>/dev/null; then
  current_type="$(kubectl get secret linkerd-identity-issuer -n "$NS" -o jsonpath='{.type}')"
  if [[ "$current_type" != "kubernetes.io/tls" ]]; then
    echo "    Xóa secret cũ (type=${current_type}) → tạo kubernetes.io/tls"
    kubectl delete secret linkerd-identity-issuer -n "$NS"
  fi
fi
kubectl apply -k "$IDENTITY_KUSTOMIZE"

kubectl get configmap linkerd-identity-trust-roots -n "$NS" -o jsonpath='{.data}' | grep -q ca-bundle.crt
kubectl get secret linkerd-identity-issuer -n "$NS" -o jsonpath='{.type}' | grep -q kubernetes.io/tls
echo "    OK: ca-bundle.crt + kubernetes.io/tls"

echo ">>> 2/3 Restart pods (linkerd-config đã có từ Helm)"
kubectl delete pods -n "$NS" --all --ignore-not-found --wait=false

echo ">>> 3/3 Theo dõi"
echo "    kubectl get pods -n $NS -w"
echo ""
echo "Nếu linkerd-crds OutOfSync: sync app (enableHttpRoutes=false) — KHÔNG Replace"
echo "Mong đợi: identity 2/2, destination 2/2, proxy-injector 2/2"
