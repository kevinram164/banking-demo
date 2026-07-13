#!/usr/bin/env bash
# Load xt_* modules trên mọi node (lab nhanh — không reboot).
# Persist: oc apply -f ../ocp-values/machineconfig/linkerd-xt-modules.yaml
#
#   ./environments/dev-ocp/scripts/linkerd-load-xt-modules.sh
set -euo pipefail

MODULES=(xt_multiport xt_comment xt_REDIRECT xt_owner)

echo "==> modprobe ${MODULES[*]} trên từng node (oc debug)"
for node in $(oc get nodes -o jsonpath='{.items[*].metadata.name}'); do
  echo "---- ${node} ----"
  oc debug "node/${node}" --quiet -- chroot /host bash -c \
    "for m in ${MODULES[*]}; do modprobe \"\$m\" 2>/dev/null || echo WARN: cannot load \$m; done; lsmod | grep -E 'xt_multiport|xt_owner|xt_comment|xt_REDIRECT' || true" \
    || echo "WARN: debug ${node} failed"
done

echo ""
echo "==> Restart linkerd control-plane pods"
oc delete pod -n linkerd --all --force --grace-period=0 2>/dev/null || true
sleep 5
oc get pods -n linkerd

echo ""
echo "Verify init:"
echo "  oc logs -n linkerd deploy/linkerd-proxy-injector -c linkerd-init 2>&1 | head -20"
echo ""
echo "Persist across reboot:"
echo "  oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/machineconfig/linkerd-xt-modules.yaml"
echo "  oc get mcp   # đợi UPDATED=True (worker reboot)"
