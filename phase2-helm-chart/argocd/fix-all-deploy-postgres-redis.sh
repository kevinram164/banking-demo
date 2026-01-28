#!/bin/bash
# Script: Fix toàn bộ - Đảm bảo postgres và redis được deploy
# Cách dùng: ./fix-all-deploy-postgres-redis.sh

set -e

echo "🔧 Fixing toàn bộ - Đảm bảo postgres và redis được deploy..."
echo ""

# Bước 1: Xóa tất cả Applications cũ
echo "📋 Step 1: Xóa Applications cũ (nếu có)..."
kubectl delete application banking-demo -n argocd --cascade=false 2>/dev/null || true
kubectl delete application banking-demo-postgres -n argocd --cascade=false 2>/dev/null || true
kubectl delete application banking-demo-redis -n argocd --cascade=false 2>/dev/null || true
sleep 2
echo "✅ Đã xóa Applications cũ"
echo ""

# Bước 2: Xóa namespace nếu đang stuck
echo "📋 Step 2: Xóa namespace nếu đang stuck..."
if kubectl get namespace banking &>/dev/null; then
  echo "   Namespace tồn tại, kiểm tra trạng thái..."
  if kubectl get namespace banking -o jsonpath='{.metadata.deletionTimestamp}' 2>/dev/null | grep -q .; then
    echo "   Namespace đang pending deletion, xóa finalizers..."
    kubectl patch namespace banking -p '{"metadata":{"finalizers":[]}}' --type=merge 2>/dev/null || true
    sleep 2
  fi
  
  # Xóa tất cả resources
  kubectl delete all --all -n banking --force --grace-period=0 2>/dev/null || true
  kubectl delete secrets --all -n banking --force --grace-period=0 2>/dev/null || true
  kubectl delete configmaps --all -n banking --force --grace-period=0 2>/dev/null || true
  kubectl delete pvc --all -n banking --force --grace-period=0 2>/dev/null || true
  
  # Xóa namespace
  kubectl delete namespace banking --force --grace-period=0 2>/dev/null || true
  sleep 3
  
  # Đợi namespace bị xóa
  for i in {1..10}; do
    if ! kubectl get namespace banking &>/dev/null; then
      echo "✅ Namespace đã bị xóa"
      break
    fi
    echo "   Đợi namespace bị xóa... ($i/10)"
    sleep 2
  done
else
  echo "✅ Namespace không tồn tại"
fi
echo ""

# Bước 3: Deploy Project
echo "📋 Step 3: Deploying Project..."
kubectl apply -f project.yaml -n argocd
echo "✅ Project deployed"
echo ""

# Bước 4: Deploy namespace Application trước
echo "📋 Step 4: Deploying namespace Application..."
kubectl apply -f applications/namespace.yaml -n argocd
echo "✅ Namespace Application deployed"
echo ""

# Bước 5: Sync namespace và đợi
echo "📋 Step 5: Syncing namespace và đợi namespace được tạo..."
argocd app sync banking-demo-namespace --timeout 300 || echo "⚠️  Sync namespace failed"
sleep 5

# Kiểm tra namespace đã được tạo chưa
for i in {1..30}; do
  if kubectl get namespace banking &>/dev/null; then
    echo "✅ Namespace đã được tạo"
    break
  fi
  echo "   Đợi namespace được tạo... ($i/30)"
  sleep 2
done

if ! kubectl get namespace banking &>/dev/null; then
  echo "❌ Namespace vẫn chưa được tạo sau 60 giây"
  echo "   Kiểm tra Application: argocd app get banking-demo-namespace"
  exit 1
fi
echo ""

# Bước 6: Deploy postgres và redis Applications
echo "📋 Step 6: Deploying postgres và redis Applications..."
kubectl apply -f applications/postgres.yaml -n argocd
kubectl apply -f applications/redis.yaml -n argocd
echo "✅ Postgres và Redis Applications deployed"
echo ""

# Bước 7: Hard refresh và sync
echo "📋 Step 7: Hard refresh và sync postgres/redis..."
argocd app get banking-demo-postgres --refresh 2>/dev/null || echo "⚠️  Refresh postgres failed"
argocd app get banking-demo-redis --refresh 2>/dev/null || echo "⚠️  Refresh redis failed"
sleep 3

argocd app sync banking-demo-postgres --timeout 300 || echo "⚠️  Sync postgres failed"
argocd app sync banking-demo-redis --timeout 300 || echo "⚠️  Sync redis failed"
echo ""

# Bước 8: Đợi và kiểm tra
echo "📋 Step 8: Đợi và kiểm tra pods..."
sleep 10

echo ""
echo "📊 Kết quả:"
echo ""
echo "Applications:"
kubectl get applications -n argocd -l app.kubernetes.io/name=banking-demo | grep -E "postgres|redis|namespace" || echo "⚠️  Không tìm thấy Applications"
echo ""

echo "Namespace:"
kubectl get namespace banking 2>/dev/null && echo "✅ Namespace tồn tại" || echo "❌ Namespace không tồn tại"
echo ""

echo "Pods:"
kubectl get pods -n banking 2>/dev/null || echo "⚠️  Không có pods"
echo ""

echo "StatefulSets:"
kubectl get statefulsets -n banking 2>/dev/null || echo "⚠️  Không có StatefulSets"
echo ""

echo "Services:"
kubectl get services -n banking 2>/dev/null | grep -E "postgres|redis" || echo "⚠️  Không có Services postgres/redis"
echo ""

# Bước 9: Kiểm tra ArgoCD manifests
echo "📋 Step 9: Kiểm tra ArgoCD rendered manifests..."
echo ""
echo "Postgres manifests (số resources):"
POSTGRES_COUNT=$(argocd app manifests banking-demo-postgres 2>/dev/null | grep -E "^kind:" | wc -l || echo "0")
echo "   $POSTGRES_COUNT resources"
if [ "$POSTGRES_COUNT" -eq "0" ]; then
  echo "   ❌ Không có resources được render!"
  echo "   → Kiểm tra: argocd app get banking-demo-postgres -o yaml"
else
  echo "   ✅ Có resources được render"
fi
echo ""

echo "Redis manifests (số resources):"
REDIS_COUNT=$(argocd app manifests banking-demo-redis 2>/dev/null | grep -E "^kind:" | wc -l || echo "0")
echo "   $REDIS_COUNT resources"
if [ "$REDIS_COUNT" -eq "0" ]; then
  echo "   ❌ Không có resources được render!"
  echo "   → Kiểm tra: argocd app get banking-demo-redis -o yaml"
else
  echo "   ✅ Có resources được render"
fi
echo ""

# Tổng kết
if [ "$POSTGRES_COUNT" -gt "0" ] && [ "$REDIS_COUNT" -gt "0" ]; then
  echo "✅ TỔNG KẾT: Postgres và Redis đã được render thành công!"
  echo ""
  echo "📝 Nếu pods vẫn chưa chạy, kiểm tra:"
  echo "   1. StorageClass 'nfs-client' có tồn tại không: kubectl get storageclass"
  echo "   2. Secret 'banking-db-secret' có tồn tại không: kubectl get secret banking-db-secret -n banking"
  echo "   3. Events: kubectl get events -n banking --sort-by='.lastTimestamp'"
else
  echo "❌ TỔNG KẾT: Postgres hoặc Redis chưa được render!"
  echo ""
  echo "📝 Next steps:"
  echo "   1. Kiểm tra Application status: argocd app get banking-demo-postgres"
  echo "   2. Kiểm tra Application conditions: kubectl get application banking-demo-postgres -n argocd -o yaml | grep -A 20 conditions"
  echo "   3. Hard refresh lại: argocd app get banking-demo-postgres --refresh"
  echo "   4. Sync lại: argocd app sync banking-demo-postgres"
fi
