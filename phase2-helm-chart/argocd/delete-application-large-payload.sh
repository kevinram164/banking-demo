#!/bin/bash
# Script: Xóa Application có payload quá lớn (không thể xóa qua UI)
# Cách dùng: ./delete-application-large-payload.sh <app-name>
# Ví dụ: ./delete-application-large-payload.sh banking-demo-infra

set -e

APP_NAME=${1:-"banking-demo-infra"}
NAMESPACE="argocd"

if [ -z "$1" ]; then
  echo "❌ Usage: $0 <app-name>"
  echo "   Example: $0 banking-demo-infra"
  exit 1
fi

echo "🗑️  Deleting Application '$APP_NAME' (payload too large for UI)..."
echo ""

# Bước 1: Kiểm tra Application có tồn tại không
echo "📋 Step 1: Checking if Application exists..."
if ! kubectl get application $APP_NAME -n $NAMESPACE &>/dev/null; then
  echo "❌ Application '$APP_NAME' không tồn tại"
  exit 1
fi
echo "✅ Application tồn tại"
echo ""

# Bước 2: Xóa với cascade=false (không xóa resources, chỉ xóa Application)
echo "📋 Step 2: Deleting Application with cascade=false (preserve resources)..."
kubectl patch application $APP_NAME -n $NAMESPACE \
  --type json \
  -p='[{"op": "remove", "path": "/metadata/finalizers"}]' || true

kubectl delete application $APP_NAME -n $NAMESPACE \
  --cascade=false \
  --wait=false || echo "⚠️  Application đã được xóa hoặc không thể xóa"

echo ""
echo "✅ Application đã được xóa"
echo ""
echo "📝 Note: Resources trong cluster vẫn còn tồn tại."
echo "   Nếu muốn xóa resources, chạy:"
echo "   kubectl delete all --all -n banking"
echo "   kubectl delete namespace banking"
