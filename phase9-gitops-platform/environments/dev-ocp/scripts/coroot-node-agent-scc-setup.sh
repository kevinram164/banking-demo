#!/usr/bin/env bash
# Coroot node-agent (DaemonSet) trên OCP: cần privileged SCC (hostPID, hostPath, eBPF).
#
#   ./environments/dev-ocp/scripts/coroot-node-agent-scc-setup.sh
#
# Trước đó: sync observability-coroot-ce (values bỏ nodeSelector coroot-node-agent=enabled).
set -euo pipefail

NS="${OBSERVABILITY_NS:-observability}"
WAIT_SEC="${WAIT_SEC:-60}"

echo "==> Namespace ${NS}"
oc create ns "${NS}" --dry-run=client -o yaml | oc apply -f -

DS=""
SA=""
echo "==> Tìm DaemonSet *node-agent* (tối đa ${WAIT_SEC}s)"
elapsed=0
while [[ "${elapsed}" -lt "${WAIT_SEC}" ]]; do
  DS="$(oc get ds -n "${NS}" -o name 2>/dev/null | grep -i node-agent | head -1 | sed 's|daemonset.apps/||' || true)"
  if [[ -n "${DS}" ]]; then
    SA="$(oc get ds "${DS}" -n "${NS}" -o jsonpath='{.spec.template.spec.serviceAccountName}' 2>/dev/null || true)"
    [[ -z "${SA}" ]] && SA="default"
    echo "    ds/${DS} — SA: ${SA}"
    break
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done

if [[ -z "${DS}" ]]; then
  echo "WARN: chưa có DaemonSet *node-agent* — sync ArgoCD observability-coroot-ce rồi chạy lại"
  SA="coroot-node-agent"
  DS="coroot-node-agent"
fi

oc create serviceaccount "${SA}" -n "${NS}" --dry-run=client -o yaml | oc apply -f -

echo "==> Bind privileged SCC → SA ${SA} (ns ${NS})"
oc adm policy add-scc-to-user privileged -z "${SA}" -n "${NS}"

if oc get ds "${DS}" -n "${NS}" &>/dev/null; then
  echo "==> Rollout restart DaemonSet ${DS}"
  oc rollout restart "ds/${DS}" -n "${NS}"
  oc rollout status "ds/${DS}" -n "${NS}" --timeout=180s || true
fi

echo ""
echo "OK — kiểm tra (số READY = số node):"
echo "  oc get ds,pods -n ${NS} | grep -i node-agent"
echo "  oc describe ds ${DS} -n ${NS} | grep -A5 'Events\\|FailedCreate' || true"
echo ""
echo "UI Coroot → Nodes: đợi 1–2 phút sau khi mọi pod node-agent Running."
