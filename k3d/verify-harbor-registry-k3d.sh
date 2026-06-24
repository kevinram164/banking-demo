#!/usr/bin/env bash
# Kiểm tra registries.yaml trên mọi node k3s (server + agent)
# Usage: ./verify-harbor-registry-k3d.sh
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-npd}"

all_nodes="$(docker ps --filter "label=k3d.cluster=${CLUSTER_NAME}" --format '{{.Names}}' | sort)"
if [[ -z "${all_nodes}" ]]; then
  echo "No k3d containers for cluster '${CLUSTER_NAME}'."
  exit 1
fi

is_k3s_node() {
  local node="$1"
  [[ "${node}" == *-server-* ]] || [[ "${node}" == *-agent-* ]]
}

ok=0
missing=0
for node in ${all_nodes}; do
  [[ "${node}" == *-tools ]] || [[ "${node}" == *-serverlb ]] && continue
  if ! is_k3s_node "${node}"; then
    continue
  fi
  if docker exec "${node}" test -f /etc/rancher/k3s/registries.yaml 2>/dev/null; then
    ok=$((ok + 1))
    echo "OK: ${node}"
  else
    missing=$((missing + 1))
    echo "MISSING: ${node}"
  fi
done

echo ""
echo "Summary: ${ok} OK, ${missing} missing"
if [[ ${missing} -gt 0 ]]; then
  echo "Run: ./k3d/configure-harbor-registry-k3d.sh"
  exit 1
fi

echo ""
echo "Harbor services (platform):"
kubectl get svc -n platform 2>/dev/null | grep harbor || true
