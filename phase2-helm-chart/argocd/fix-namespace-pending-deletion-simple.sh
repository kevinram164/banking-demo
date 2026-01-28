#!/bin/bash
# Script đơn giản: Xóa namespace đang pending deletion (không cần jq)
# Cách dùng: ./fix-namespace-pending-deletion-simple.sh [namespace]
# Ví dụ: ./fix-namespace-pending-deletion-simple.sh banking

set -e

NAMESPACE=${1:-"banking"}

echo "🔧 Fixing namespace '${NAMESPACE}' đang pending deletion..."
echo ""

# Bước 1: Kiểm tra namespace có tồn tại không
if ! kubectl get namespace ${NAMESPACE} &>/dev/null; then
  echo "✅ Namespace '${NAMESPACE}' không tồn tại (đã bị xóa)"
  exit 0
fi

echo "📋 Step 1: Checking namespace status..."
kubectl get namespace ${NAMESPACE} -o yaml | grep -E "deletionTimestamp|finalizers" || echo "Namespace không có finalizers"
echo ""

# Bước 2: Xóa finalizers bằng kubectl patch (không cần jq)
echo "📋 Step 2: Removing finalizers using kubectl patch..."
kubectl patch namespace ${NAMESPACE} -p '{"metadata":{"finalizers":[]}}' --type=merge || {
  echo "⚠️  Patch không thành công, thử cách khác..."
  
  # Cách 2: Dùng sed để xóa finalizers từ JSON
  echo "   Thử cách 2: dùng sed..."
  kubectl get namespace ${NAMESPACE} -o json | \
    sed 's/"finalizers": \[[^]]*\]/"finalizers": []/' | \
    kubectl replace --raw /api/v1/namespaces/${NAMESPACE}/finalize -f - || \
    echo "⚠️  Không thể xóa finalizers"
}
echo ""

# Bước 3: Đợi namespace bị xóa hoàn toàn
echo "📋 Step 3: Waiting for namespace to be fully deleted..."
for i in {1..30}; do
  if ! kubectl get namespace ${NAMESPACE} &>/dev/null; then
    echo "✅ Namespace đã bị xóa hoàn toàn"
    exit 0
  fi
  echo "   Đợi... ($i/30)"
  sleep 2
done

# Bước 4: Kiểm tra lại
if kubectl get namespace ${NAMESPACE} &>/dev/null; then
  echo "⚠️  Namespace vẫn còn tồn tại sau 60 giây."
  echo ""
  echo "📝 Có thể có resources đang chặn việc xóa."
  echo "   Thử các lệnh sau:"
  echo ""
  echo "   1. Xóa tất cả resources trong namespace:"
  echo "      kubectl delete all --all -n ${NAMESPACE} --force --grace-period=0"
  echo ""
  echo "   2. Xóa namespace với force:"
  echo "      kubectl delete namespace ${NAMESPACE} --force --grace-period=0"
  echo ""
  echo "   3. Nếu vẫn không được, xóa finalizers thủ công:"
  echo "      kubectl get namespace ${NAMESPACE} -o json | \\"
  echo "        sed 's/\"finalizers\": \\[[^]]*\\]/\"finalizers\": []/' | \\"
  echo "        kubectl replace --raw /api/v1/namespaces/${NAMESPACE}/finalize -f -"
  exit 1
else
  echo "✅ Namespace đã được xóa thành công"
  echo ""
  echo "📝 Next steps:"
  echo "   1. Deploy lại namespace: kubectl apply -f applications/namespace.yaml -n argocd"
  echo "   2. Sync: argocd app sync banking-demo-namespace"
fi
