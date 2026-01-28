#!/bin/bash
# Script: Kiểm tra xem postgres và redis có resources trong cluster không
# Cách dùng: ./check-postgres-redis-resources.sh

set -e

NAMESPACE="banking"

echo "🔍 Checking postgres and redis resources in namespace '${NAMESPACE}'..."
echo ""

# Bước 1: Kiểm tra namespace có tồn tại không
if ! kubectl get namespace ${NAMESPACE} &>/dev/null; then
  echo "❌ Namespace '${NAMESPACE}' không tồn tại"
  echo "   Deploy namespace trước: kubectl apply -f applications/namespace.yaml -n argocd"
  exit 1
fi

echo "✅ Namespace tồn tại"
echo ""

# Bước 2: Kiểm tra pods
echo "📋 Step 1: Checking Pods..."
PODS=$(kubectl get pods -n ${NAMESPACE} 2>/dev/null | grep -E "postgres|redis" || echo "")
if [ -z "$PODS" ]; then
  echo "❌ Không có pods postgres hoặc redis"
else
  echo "✅ Pods:"
  echo "$PODS"
fi
echo ""

# Bước 3: Kiểm tra StatefulSets
echo "📋 Step 2: Checking StatefulSets..."
STS=$(kubectl get statefulsets -n ${NAMESPACE} 2>/dev/null | grep -E "postgres|redis" || echo "")
if [ -z "$STS" ]; then
  echo "❌ Không có StatefulSets postgres hoặc redis"
else
  echo "✅ StatefulSets:"
  echo "$STS"
fi
echo ""

# Bước 4: Kiểm tra Services
echo "📋 Step 3: Checking Services..."
SVC=$(kubectl get services -n ${NAMESPACE} 2>/dev/null | grep -E "postgres|redis" || echo "")
if [ -z "$SVC" ]; then
  echo "❌ Không có Services postgres hoặc redis"
else
  echo "✅ Services:"
  echo "$SVC"
fi
echo ""

# Bước 5: Kiểm tra ArgoCD manifests
echo "📋 Step 4: Checking ArgoCD rendered manifests..."
echo ""
echo "Postgres manifests:"
argocd app manifests banking-demo-postgres 2>/dev/null | grep -E "kind:|name:" | head -20 || echo "⚠️  Không thể lấy manifests (có thể cần login argocd)"
echo ""
echo "Redis manifests:"
argocd app manifests banking-demo-redis 2>/dev/null | grep -E "kind:|name:" | head -20 || echo "⚠️  Không thể lấy manifests (có thể cần login argocd)"
echo ""

# Bước 6: Tổng kết
if [ -z "$PODS" ] && [ -z "$STS" ] && [ -z "$SVC" ]; then
  echo "❌ TỔNG KẾT: Không có resources nào được deploy"
  echo ""
  echo "📝 Giải pháp:"
  echo "   1. Hard refresh Applications:"
  echo "      argocd app get banking-demo-postgres --refresh"
  echo "      argocd app get banking-demo-redis --refresh"
  echo ""
  echo "   2. Sync lại:"
  echo "      argocd app sync banking-demo-postgres"
  echo "      argocd app sync banking-demo-redis"
  echo ""
  echo "   3. Kiểm tra values được merge:"
  echo "      argocd app get banking-demo-postgres -o yaml | grep -A 30 'helm:'"
  exit 1
else
  echo "✅ TỔNG KẾT: Có resources được deploy"
fi
