#!/usr/bin/env bash
# Áp registries.yaml lên cluster k3d đã tạo (fix ImagePullBackOff x509 harbor-npd.co)
# Usage: ./configure-harbor-registry-k3d.sh
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-npd}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REG_FILE="${SCRIPT_DIR}/registries.yaml"

if [[ ! -f "${REG_FILE}" ]]; then
  echo "Missing ${REG_FILE}"
  exit 1
fi

all_nodes="$(docker ps --filter "label=k3d.cluster=${CLUSTER_NAME}" --format '{{.Names}}')"
if [[ -z "${all_nodes}" ]]; then
  echo "No k3d containers for cluster '${CLUSTER_NAME}'. Is the cluster running?"
  exit 1
fi

# Chỉ server/agent — bỏ qua k3d-*-tools (không có /etc/rancher/k3s)
nodes=()
for node in ${all_nodes}; do
  if [[ "${node}" == *-tools ]]; then
    echo "Skipping tools container: ${node}"
    continue
  fi
  if docker exec "${node}" test -d /etc/rancher/k3s 2>/dev/null; then
    nodes+=("${node}")
  else
    echo "Skipping ${node} (no /etc/rancher/k3s)"
  fi
done

if [[ ${#nodes[@]} -eq 0 ]]; then
  echo "No k3s server/agent nodes found for cluster '${CLUSTER_NAME}'."
  exit 1
fi

echo "Applying ${REG_FILE} to cluster '${CLUSTER_NAME}'..."
for node in "${nodes[@]}"; do
  echo "  -> ${node}"
  docker cp "${REG_FILE}" "${node}:/etc/rancher/k3s/registries.yaml"
done

echo "Restarting cluster (k3s reload registries)..."
k3d cluster stop "${CLUSTER_NAME}"
k3d cluster start "${CLUSTER_NAME}"

echo ""
echo "Done. Verify pull secret + restart banking pods:"
echo "  kubectl get secret harbor-pull-creds -n banking"
echo "  kubectl rollout restart deployment -n banking"
