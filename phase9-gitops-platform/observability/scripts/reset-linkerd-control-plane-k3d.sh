#!/usr/bin/env bash
# Reset Linkerd control-plane trên k3d — để Helm (externalCA:false) tạo lại TOÀN BỘ secrets.
# Không dùng apply-linkerd-identity-k3d.sh trước bước này (secret thủ công thiếu webhook TLS).
set -euo pipefail

NS=linkerd

echo ">>> Xóa workloads control-plane (giữ namespace + CRDs)"
kubectl delete deployment,replicaset,pod -n "$NS" --all --ignore-not-found --wait=false

echo ">>> Xóa secrets/configmaps do Helm quản lý"
kubectl delete secret,configmap -n "$NS" -l linkerd.io/control-plane-component --ignore-not-found
for name in \
  linkerd-identity-issuer \
  linkerd-identity-trust-roots \
  linkerd-config \
  linkerd-proxy-injector-k8s-tls \
  linkerd-sp-validator-k8s-tls \
  linkerd-policy-validator-k8s-tls; do
  kubectl delete secret -n "$NS" "$name" --ignore-not-found
  kubectl delete configmap -n "$NS" "$name" --ignore-not-found
done

echo ""
echo ">>> Tiếp theo — sync ArgoCD (Helm tạo identity + webhook certs từ values-linkerd-k3d.yaml):"
echo "    argocd app sync observability-linkerd-control-plane --force --replace --grpc-web"
echo ""
echo ">>> Hoặc ArgoCD UI: observability-linkerd-control-plane → Hard Refresh → Sync → Replace"
echo ""
echo ">>> Theo dõi:"
echo "    kubectl get pods -n $NS -w"
