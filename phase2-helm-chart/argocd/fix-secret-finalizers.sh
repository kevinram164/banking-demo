#!/bin/bash
# Script: Xóa secret có finalizers đang chặn việc xóa namespace
# Cách dùng: ./fix-secret-finalizers.sh [namespace] [secret-name]
# Ví dụ: ./fix-secret-finalizers.sh banking banking-db-secret

set -e

NAMESPACE=${1:-"banking"}
SECRET_NAME=${2:-"banking-db-secret"}

echo "🔧 Fixing secret '${SECRET_NAME}' trong namespace '${NAMESPACE}'..."
echo ""

# Bước 1: Kiểm tra secret có tồn tại không
if ! kubectl get secret ${SECRET_NAME} -n ${NAMESPACE} &>/dev/null; then
  echo "✅ Secret '${SECRET_NAME}' không tồn tại trong namespace '${NAMESPACE}'"
  exit 0
fi

echo "📋 Step 1: Checking secret status..."
kubectl get secret ${SECRET_NAME} -n ${NAMESPACE} -o yaml | grep -E "finalizers|deletionTimestamp" || echo "Secret không có finalizers"
echo ""

# Bước 2: Xóa finalizers của secret
echo "📋 Step 2: Removing finalizers from secret..."
kubectl patch secret ${SECRET_NAME} -n ${NAMESPACE} -p '{"metadata":{"finalizers":[]}}' --type=merge 2>/dev/null || {
  echo "⚠️  Patch không thành công, thử cách khác..."
  
  # Cách 2: Dùng sed để xóa finalizers từ JSON
  kubectl get secret ${SECRET_NAME} -n ${NAMESPACE} -o json | \
    sed 's/"finalizers": \[[^]]*\]/"finalizers": []/' | \
    kubectl replace -f - 2>/dev/null || \
    echo "⚠️  Không thể xóa finalizers"
}
echo ""

# Bước 3: Xóa secret
echo "📋 Step 3: Deleting secret..."
kubectl delete secret ${SECRET_NAME} -n ${NAMESPACE} --force --grace-period=0 2>/dev/null || {
  echo "⚠️  Delete không thành công, thử cách khác..."
  
  # Cách 2: Xóa qua raw API
  kubectl get secret ${SECRET_NAME} -n ${NAMESPACE} -o json | \
    sed 's/"finalizers": \[[^]]*\]/"finalizers": []/' | \
    kubectl replace --raw /api/v1/namespaces/${NAMESPACE}/secrets/${SECRET_NAME}/finalize -f - 2>/dev/null || \
    echo "⚠️  Không thể xóa secret qua raw API"
}
echo ""

# Bước 4: Kiểm tra lại
if kubectl get secret ${SECRET_NAME} -n ${NAMESPACE} &>/dev/null; then
  echo "⚠️  Secret vẫn còn tồn tại sau khi xóa finalizers"
  echo ""
  echo "📝 Thử các lệnh sau thủ công:"
  echo ""
  echo "   1. Xem finalizers của secret:"
  echo "      kubectl get secret ${SECRET_NAME} -n ${NAMESPACE} -o yaml | grep finalizers"
  echo ""
  echo "   2. Xóa finalizers thủ công:"
  echo "      kubectl patch secret ${SECRET_NAME} -n ${NAMESPACE} -p '{\"metadata\":{\"finalizers\":[]}}' --type=merge"
  echo ""
  echo "   3. Xóa secret với force:"
  echo "      kubectl delete secret ${SECRET_NAME} -n ${NAMESPACE} --force --grace-period=0"
  echo ""
  echo "   4. Nếu vẫn không được, xóa tất cả resources trong namespace:"
  echo "      kubectl delete all --all -n ${NAMESPACE} --force --grace-period=0"
  echo "      kubectl delete secrets --all -n ${NAMESPACE} --force --grace-period=0"
  echo "      kubectl delete configmaps --all -n ${NAMESPACE} --force --grace-period=0"
  exit 1
else
  echo "✅ Secret đã được xóa thành công"
  echo ""
  echo "📝 Bây giờ có thể xóa namespace:"
  echo "   kubectl delete namespace ${NAMESPACE} --force --grace-period=0"
fi
