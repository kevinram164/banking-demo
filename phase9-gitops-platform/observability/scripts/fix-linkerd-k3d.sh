#!/usr/bin/env bash
# Fix Linkerd k3d — chạy MỘT LẦN sau git pull.
set -euo pipefail

NS=linkerd
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

echo ">>> 1/4 Identity bootstrap (kubernetes.io/tls + ca-bundle.crt)"
kubectl apply -k "${REPO_ROOT}/phase9-gitops-platform/observability/manifests/linkerd-identity-k3d/"

echo ">>> Kiểm tra:"
kubectl get configmap linkerd-identity-trust-roots -n "$NS" -o jsonpath='{.data}' | grep -q ca-bundle.crt
kubectl get secret linkerd-identity-issuer -n "$NS" -o jsonpath='{.type}' | grep -q kubernetes.io/tls
echo "    OK: configmap ca-bundle.crt + secret type kubernetes.io/tls"

echo ">>> 2/4 Xóa pod cũ"
kubectl delete pods -n "$NS" --all --ignore-not-found --wait=false

echo ">>> 3/4 ArgoCD Replace control-plane (Helm tạo linkerd-config + webhook TLS)"
echo "    Chạy trên UI: observability-linkerd-control-plane → Sync → Replace"
echo "    Hoặc: argocd app sync observability-linkerd-control-plane --force --replace --grpc-web"

echo ">>> 4/4 Sau khi có configmap/linkerd-config:"
echo "    kubectl delete pods -n $NS --all"
echo "    kubectl get pods -n $NS -w"
echo ""
echo "Mong đợi: destination 2/2 (policy tắt), identity 2/2, proxy-injector 2/2"
