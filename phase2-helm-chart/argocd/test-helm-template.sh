#!/bin/bash
# Script: Test Helm template rendering giống như ArgoCD sẽ làm
# Cách dùng: ./test-helm-template.sh [service]
# Ví dụ: ./test-helm-template.sh postgres

set -e

SERVICE=${1:-"postgres"}
CHART_PATH="banking-demo"

if [ "$SERVICE" = "postgres" ]; then
  VALUE_FILES="charts/common/values.yaml charts/postgres/values.yaml"
  SET_PARAMS="namespace.enabled=false secret.enabled=false redis.enabled=false kong.enabled=false auth-service.enabled=false account-service.enabled=false transfer-service.enabled=false notification-service.enabled=false frontend.enabled=false ingress.enabled=false"
elif [ "$SERVICE" = "redis" ]; then
  VALUE_FILES="charts/common/values.yaml charts/redis/values.yaml"
  SET_PARAMS="namespace.enabled=false secret.enabled=false postgres.enabled=false kong.enabled=false auth-service.enabled=false account-service.enabled=false transfer-service.enabled=false notification-service.enabled=false frontend.enabled=false ingress.enabled=false"
elif [ "$SERVICE" = "namespace" ]; then
  VALUE_FILES="charts/common/values.yaml"
  SET_PARAMS="namespace.enabled=true secret.enabled=true postgres.enabled=false redis.enabled=false kong.enabled=false auth-service.enabled=false account-service.enabled=false transfer-service.enabled=false notification-service.enabled=false frontend.enabled=false ingress.enabled=false"
else
  echo "❌ Service không hợp lệ. Dùng: postgres, redis, hoặc namespace"
  exit 1
fi

echo "🧪 Testing Helm template rendering cho $SERVICE..."
echo ""

cd "$(dirname "$0")/../$CHART_PATH"

echo "Command:"
echo "helm template test . \\"
echo "  --values $VALUE_FILES \\"
echo "  --set $SET_PARAMS"
echo ""

helm template test . \
  --values charts/common/values.yaml \
  $(echo $VALUE_FILES | sed 's/charts\/common\/values.yaml//' | xargs -n1 echo --values) \
  $(echo $SET_PARAMS | xargs -n1 echo --set) \
  --namespace banking

echo ""
echo "✅ Template rendering thành công!"
echo ""
echo "📝 Kiểm tra:"
echo "   - Có resources được render không?"
echo "   - Namespace có đúng là 'banking' không?"
echo "   - Có lỗi gì không?"
