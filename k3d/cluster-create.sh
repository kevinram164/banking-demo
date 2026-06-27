#!/usr/bin/env bash
# Tạo k3d cluster npd cho lab GitOps (WSL2 + Docker Desktop)
# Usage: ./cluster-create.sh
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-npd}"
AGENTS="${AGENTS:-5}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRIES_FILE="${SCRIPT_DIR}/registries.yaml"

if [[ ! -f "${REGISTRIES_FILE}" ]]; then
  echo "Missing ${REGISTRIES_FILE}"
  exit 1
fi

if k3d cluster list | grep -q "^${CLUSTER_NAME} "; then
  echo "Cluster '${CLUSTER_NAME}' already exists. Delete first: k3d cluster delete ${CLUSTER_NAME}"
  exit 1
fi

k3d cluster create "${CLUSTER_NAME}" \
  --agents "${AGENTS}" \
  -p "9080:80@loadbalancer" \
  -p "9443:443@loadbalancer" \
  --volume "${REGISTRIES_FILE}:/etc/rancher/k3s/registries.yaml@all"

k3d kubeconfig merge "${CLUSTER_NAME}" --kubeconfig-merge-default

echo ""
echo "Cluster created. Verify:"
echo "  docker ps | grep serverlb"
echo "  kubectl get nodes"
echo ""
echo "Next: see phase9-gitops-platform/K3D-DEPLOY-GUIDE.md"
