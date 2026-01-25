#!/usr/bin/env bash
# Build và push từng service lên GitLab Container Registry.
# Repo: registry.gitlab.com/kiettt164/banking-demo-payment
# Mỗi service là một image riêng: auth-service, account-service, transfer-service, notification-service, frontend.
#
# Cách dùng:
#   1. Đăng nhập: docker login registry.gitlab.com  (dùng username + Personal Access Token hoặc deploy token)
#   2. Chạy từ thư mục gốc project: ./scripts/push-gitlab.sh [tag]
#      tag mặc định: latest. Ví dụ: ./scripts/push-gitlab.sh v1.0.0

set -e
REGISTRY="registry.gitlab.com/kiettt164/banking-demo-payment"
TAG="${1:-latest}"

echo "Registry: $REGISTRY"
echo "Tag: $TAG"
echo "---"

build_and_push() {
  local name=$1
  local dockerfile=$2
  local context=$3
  echo "Build $name..."
  docker build -t "${REGISTRY}/${name}:${TAG}" -f "$dockerfile" "$context"
  echo "Push ${REGISTRY}/${name}:${TAG}"
  docker push "${REGISTRY}/${name}:${TAG}"
  echo "Done $name"
  echo "---"
}

# Chạy từ repo root
cd "$(dirname "$0")/.."

build_and_push "auth-service"      "services/auth-service/Dockerfile" "."
build_and_push "account-service"   "services/account-service/Dockerfile" "."
build_and_push "transfer-service"  "services/transfer-service/Dockerfile" "."
build_and_push "notification-service" "services/notification-service/Dockerfile" "."
build_and_push "frontend"          "frontend/Dockerfile" "./frontend"

echo "All images pushed to $REGISTRY with tag $TAG"
