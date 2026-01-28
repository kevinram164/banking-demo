#!/bin/bash
# Script: Xử lý namespace đang pending deletion
# Cách dùng: ./fix-namespace-pending-deletion.sh

set -e

NAMESPACE="banking"

echo "🔧 Fixing namespace '${NAMESPACE}' đang pending deletion..."
echo ""

# Bước 1: Kiểm tra trạng thái namespace
echo "📋 Step 1: Checking namespace status..."
kubectl get namespace ${NAMESPACE} -o yaml | grep -E "deletionTimestamp|finalizers" || echo "Namespace không tồn tại hoặc không có finalizers"
echo ""

# Bước 2: Xóa finalizers để force delete namespace
echo "📋 Step 2: Removing finalizers to force delete namespace..."
kubectl get namespace ${NAMESPACE} -o json | \
  jq '.spec.finalizers = []' | \
  kubectl replace --raw /api/v1/namespaces/${NAMESPACE}/finalize -f - || \
  echo "Không thể xóa finalizers (có thể namespace đã bị xóa)"
echo ""

# Bước 3: Đợi namespace bị xóa hoàn toàn
echo "📋 Step 3: Waiting for namespace to be fully deleted..."
for i in {1..30}; do
  if ! kubectl get namespace ${NAMESPACE} &>/dev/null; then
    echo "✅ Namespace đã bị xóa hoàn toàn"
    break
  fi
  echo "   Đợi... ($i/30)"
  sleep 2
done

# Bước 4: Kiểm tra lại
if kubectl get namespace ${NAMESPACE} &>/dev/null; then
  echo "⚠️  Namespace vẫn còn tồn tại. Có thể có resources đang chặn việc xóa."
  echo "   Thử xóa thủ công: kubectl delete namespace ${NAMESPACE} --force --grace-period=0"
else
  echo "✅ Namespace đã được xóa thành công"
  echo ""
  echo "📝 Next steps:"
  echo "   1. Deploy lại namespace: kubectl apply -f applications/namespace.yaml -n argocd"
  echo "   2. Sync: argocd app sync banking-demo-namespace"
fi
