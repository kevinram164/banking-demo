#!/usr/bin/env bash
# Reset Linkerd control-plane trên k3d — sync lại bootstrap (wave 0) rồi control-plane (wave 1).
set -euo pipefail

NS=linkerd

echo ">>> Xóa workloads control-plane"
kubectl delete deployment,replicaset,pod -n "$NS" --all --ignore-not-found --wait=false

echo ">>> Xóa secrets/configmaps do Helm tạo (GIỮ identity bootstrap)"
for name in \
  linkerd-config \
  linkerd-proxy-injector-k8s-tls \
  linkerd-sp-validator-k8s-tls \
  linkerd-policy-validator-k8s-tls; do
  kubectl delete secret -n "$NS" "$name" --ignore-not-found
  kubectl delete configmap -n "$NS" "$name" --ignore-not-found
done
kubectl delete secret,configmap -n "$NS" -l linkerd.io/control-plane-component --ignore-not-found

echo ""
echo ">>> ArgoCD sync (theo thứ tự):"
echo "    1. observability-linkerd-identity-bootstrap"
echo "    2. observability-linkerd-control-plane  (--force --replace)"
echo ""
echo ">>> Kiểm tra identity trước khi sync control-plane:"
echo "    kubectl get secret linkerd-identity-issuer -n $NS"
echo "    kubectl get configmap linkerd-identity-trust-roots -n $NS"
echo ""
echo ">>> Theo dõi:"
echo "    kubectl get pods -n $NS -w"
