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

# Cách 1: Dùng kubectl patch (không cần jq)
kubectl patch namespace ${NAMESPACE} -p '{"metadata":{"finalizers":[]}}' --type=merge 2>/dev/null || \
  echo "⚠️  Không thể patch namespace (có thể đã bị xóa hoặc không có quyền)"

# Cách 2: Nếu cách 1 không work, dùng kubectl replace với raw API
if kubectl get namespace ${NAMESPACE} &>/dev/null; then
  echo "   Thử cách 2: dùng raw API..."
  kubectl get namespace ${NAMESPACE} -o json | \
    sed 's/"finalizers": \[[^]]*\]/"finalizers": []/' | \
    kubectl replace --raw /api/v1/namespaces/${NAMESPACE}/finalize -f - 2>/dev/null || \
    echo "⚠️  Không thể xóa finalizers qua raw API"
fi
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
  echo ""
  echo "📝 Thử các lệnh sau:"
  echo ""
  echo "   1. Xóa secret có finalizers (nếu có):"
  echo "      ./fix-secret-finalizers.sh ${NAMESPACE} banking-db-secret"
  echo ""
  echo "   2. Xóa tất cả resources trong namespace:"
  echo "      kubectl delete all --all -n ${NAMESPACE} --force --grace-period=0"
  echo "      kubectl delete secrets --all -n ${NAMESPACE} --force --grace-period=0"
  echo ""
  echo "   3. Xóa namespace với force:"
  echo "      kubectl delete namespace ${NAMESPACE} --force --grace-period=0"
else
  echo "✅ Namespace đã được xóa thành công"
  echo ""
  echo "📝 Next steps:"
  echo "   1. Deploy lại namespace: kubectl apply -f applications/namespace.yaml -n argocd"
  echo "   2. Sync: argocd app sync banking-demo-namespace"
fi
