#!/usr/bin/env bash
# Tạo k3d cluster npd cho lab GitOps (WSL2 + Docker Desktop)
# Usage: ./cluster-create.sh
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-npd}"
AGENTS="${AGENTS:-5}"

if k3d cluster list | grep -q "^${CLUSTER_NAME} "; then
  echo "Cluster '${CLUSTER_NAME}' already exists. Delete first: k3d cluster delete ${CLUSTER_NAME}"
  exit 1
fi

k3d cluster create "${CLUSTER_NAME}" \
  --agents "${AGENTS}" \
  -p "9080:80@loadbalancer" \
  -p "9443:443@loadbalancer"

k3d kubeconfig merge "${CLUSTER_NAME}" --kubeconfig-merge-default

echo ""
echo "Cluster created. Verify:"
echo "  docker ps | grep serverlb"
echo "  kubectl get nodes"
echo ""
echo "Next: see phase9-gitops-platform/K3D-DEPLOY-GUIDE.md"
