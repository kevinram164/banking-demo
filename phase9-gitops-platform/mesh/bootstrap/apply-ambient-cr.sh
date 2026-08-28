#!/usr/bin/env bash
# Bootstrap IstioCNI + ZTunnel ambient — chạy trên bastion SAU mesh-operator Ready.
# Argo KHÔNG sync được spec.profile (Sail CRD v1) → apply tay, một lần / sau upgrade OSSM.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Apply IstioCNI + ZTunnel (profile: ambient)"
oc apply -f "${SCRIPT_DIR}/istiocni.yaml"
oc apply -f "${SCRIPT_DIR}/ztunnel.yaml"

echo "==> Wait Ready"
oc wait --for=condition=Ready istiocni/default --timeout=5m
oc wait --for=condition=Ready ztunnel/default --timeout=5m

echo "==> Restart node agents"
oc rollout restart ds/istio-cni-node -n istio-cni
oc rollout restart ds/ztunnel -n ztunnel
oc rollout status ds/istio-cni-node -n istio-cni --timeout=5m
oc rollout status ds/ztunnel -n ztunnel --timeout=5m

echo "==> Verify profile on live CR"
echo -n "IstioCNI profile: "
oc get istiocni default -o jsonpath='{.spec.profile}{"\n"}'
echo -n "ZTunnel profile: "
oc get ztunnel default -o jsonpath='{.spec.profile}{"\n"}'

echo "==> Check ztunnel.sock on first worker (đổi NODE nếu cần)"
NODE="${NODE:-$(oc get nodes -l node-role.kubernetes.io/worker -o jsonpath='{.items[0].metadata.name}')}"
CNI="$(oc get pod -n istio-cni -l k8s-app=istio-cni-node \
  --field-selector "spec.nodeName=${NODE}" -o jsonpath='{.items[0].metadata.name}')"
echo "Node=${NODE} CNI pod=${CNI}"
oc exec -n istio-cni "${CNI}" -- ls -la /var/run/ztunnel/ || true

echo "Done. Nếu sock vẫn thiếu: oc logs -n istio-cni ${CNI} --tail=80"
