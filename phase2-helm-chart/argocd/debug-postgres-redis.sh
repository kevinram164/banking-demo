#!/bin/bash
# Script: Debug tại sao postgres/redis không deploy được
# Cách dùng: ./debug-postgres-redis.sh

set -e

echo "🔍 Debugging postgres và redis deployment..."
echo ""

# Bước 1: Kiểm tra namespace
echo "📋 Step 1: Checking namespace..."
if kubectl get namespace banking &>/dev/null; then
  echo "✅ Namespace 'banking' tồn tại"
else
  echo "❌ Namespace 'banking' KHÔNG tồn tại"
  echo "   → Cần deploy namespace.yaml trước"
  exit 1
fi
echo ""

# Bước 2: Kiểm tra Applications
echo "📋 Step 2: Checking Applications..."
kubectl get applications -n argocd -l app.kubernetes.io/name=banking-demo
echo ""

# Bước 3: Kiểm tra ArgoCD rendered manifests
echo "📋 Step 3: Checking ArgoCD rendered manifests for postgres..."
POSTGRES_MANIFESTS=$(argocd app manifests banking-demo-postgres 2>/dev/null || echo "")
if [ -z "$POSTGRES_MANIFESTS" ]; then
  echo "❌ Không thể lấy manifests từ ArgoCD"
  echo "   → Có thể cần login: argocd login <argocd-server>"
else
  echo "✅ Có thể lấy manifests"
  echo ""
  echo "Số lượng resources được render:"
  echo "$POSTGRES_MANIFESTS" | grep -E "^kind:" | wc -l
  echo ""
  echo "Các resources được render:"
  echo "$POSTGRES_MANIFESTS" | grep -E "^kind:" | head -10
fi
echo ""

# Bước 4: Kiểm tra values được merge
echo "📋 Step 4: Checking merged values..."
echo "Postgres enabled:"
argocd app get banking-demo-postgres -o yaml 2>/dev/null | grep -A 5 "postgres.enabled" || echo "⚠️  Không tìm thấy postgres.enabled"
echo ""

# Bước 5: Kiểm tra sync status
echo "📋 Step 5: Checking sync status..."
argocd app get banking-demo-postgres 2>/dev/null | grep -E "Sync Status|Health Status" || echo "⚠️  Không thể lấy status"
echo ""

# Bước 6: Kiểm tra events/conditions
echo "📋 Step 6: Checking Application conditions..."
kubectl get application banking-demo-postgres -n argocd -o yaml 2>/dev/null | grep -A 10 "conditions:" || echo "⚠️  Không có conditions"
echo ""

# Bước 7: Tổng kết
echo "📋 Step 7: Summary..."
echo ""
echo "Nếu không có resources được render:"
echo "  1. Hard refresh: argocd app get banking-demo-postgres --refresh"
echo "  2. Sync lại: argocd app sync banking-demo-postgres"
echo "  3. Kiểm tra values: argocd app get banking-demo-postgres -o yaml | grep -A 30 'helm:'"
echo ""
echo "Nếu có resources được render nhưng không deploy:"
echo "  1. Kiểm tra namespace: kubectl get namespace banking"
echo "  2. Kiểm tra secret: kubectl get secret banking-db-secret -n banking"
echo "  3. Kiểm tra events: kubectl get events -n banking --sort-by='.lastTimestamp'"
