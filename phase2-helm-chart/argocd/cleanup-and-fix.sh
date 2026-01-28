#!/bin/bash
# Script: Cleanup và fix toàn bộ phase 2
# Cách dùng: ./cleanup-and-fix.sh

set -e

echo "🧹 Cleaning up phase 2 - Xóa các file không cần thiết và fix conflicts..."
echo ""

# Bước 1: Xóa các file không cần thiết
echo "📋 Step 1: Deleting unnecessary files..."
cd "$(dirname "$0")"

# Xóa Application cũ (nếu đã apply)
echo "   Xóa Application banking-demo (nếu có)..."
kubectl delete application banking-demo -n argocd --cascade=false 2>/dev/null || echo "   Application banking-demo không tồn tại"

# Xóa ApplicationSet cũ (nếu đã apply)
echo "   Xóa ApplicationSet banking-demo-envs (nếu có)..."
kubectl delete applicationset banking-demo-envs -n argocd 2>/dev/null || echo "   ApplicationSet banking-demo-envs không tồn tại"

echo "✅ Đã xóa các Applications/ApplicationSets cũ"
echo ""

# Bước 2: Xóa namespace banking nếu đang pending deletion
echo "📋 Step 2: Cleaning up namespace 'banking' if stuck..."
if kubectl get namespace banking &>/dev/null; then
  echo "   Namespace tồn tại, kiểm tra trạng thái..."
  if kubectl get namespace banking -o jsonpath='{.metadata.deletionTimestamp}' 2>/dev/null | grep -q .; then
    echo "   Namespace đang pending deletion, xóa finalizers..."
    kubectl patch namespace banking -p '{"metadata":{"finalizers":[]}}' --type=merge 2>/dev/null || true
    sleep 2
  fi
  
  # Xóa tất cả resources trong namespace
  echo "   Xóa tất cả resources trong namespace..."
  kubectl delete all --all -n banking --force --grace-period=0 2>/dev/null || true
  kubectl delete secrets --all -n banking --force --grace-period=0 2>/dev/null || true
  kubectl delete configmaps --all -n banking --force --grace-period=0 2>/dev/null || true
  kubectl delete pvc --all -n banking --force --grace-period=0 2>/dev/null || true
  
  # Xóa namespace
  echo "   Xóa namespace..."
  kubectl delete namespace banking --force --grace-period=0 2>/dev/null || true
  sleep 3
fi

# Đợi namespace bị xóa hoàn toàn
for i in {1..10}; do
  if ! kubectl get namespace banking &>/dev/null; then
    echo "✅ Namespace đã bị xóa hoàn toàn"
    break
  fi
  echo "   Đợi namespace bị xóa... ($i/10)"
  sleep 2
done
echo ""

# Bước 3: Deploy lại với per-service Applications
echo "📋 Step 3: Deploying per-service Applications..."
echo "   Apply Project..."
kubectl apply -f project.yaml -n argocd
echo "   Apply Applications..."
kubectl apply -f applications/ -n argocd
echo "✅ Đã deploy Applications"
echo ""

# Bước 4: Sync theo thứ tự
echo "📋 Step 4: Syncing Applications theo sync waves..."
echo "   Sync namespace (wave -1)..."
argocd app sync banking-demo-namespace --timeout 300 || echo "⚠️  Sync namespace failed"
sleep 5

echo "   Sync postgres và redis (wave 0)..."
argocd app sync banking-demo-postgres --timeout 300 || echo "⚠️  Sync postgres failed"
argocd app sync banking-demo-redis --timeout 300 || echo "⚠️  Sync redis failed"
sleep 5

echo "   Sync kong (wave 1)..."
argocd app sync banking-demo-kong --timeout 300 || echo "⚠️  Sync kong failed"
sleep 5

echo "   Sync microservices (wave 2)..."
argocd app sync banking-demo-auth-service --timeout 300 || echo "⚠️  Sync auth-service failed"
argocd app sync banking-demo-account-service --timeout 300 || echo "⚠️  Sync account-service failed"
argocd app sync banking-demo-transfer-service --timeout 300 || echo "⚠️  Sync transfer-service failed"
argocd app sync banking-demo-notification-service --timeout 300 || echo "⚠️  Sync notification-service failed"
sleep 5

echo "   Sync frontend (wave 3)..."
argocd app sync banking-demo-frontend --timeout 300 || echo "⚠️  Sync frontend failed"
sleep 5

echo "   Sync ingress (wave 4)..."
argocd app sync banking-demo-ingress --timeout 300 || echo "⚠️  Sync ingress failed"
echo ""

# Bước 5: Kiểm tra
echo "📋 Step 5: Checking results..."
echo ""
echo "Applications:"
kubectl get applications -n argocd -l app.kubernetes.io/name=banking-demo
echo ""
echo "Namespace:"
kubectl get namespace banking 2>/dev/null && echo "✅ Namespace tồn tại" || echo "❌ Namespace không tồn tại"
echo ""
echo "Pods:"
kubectl get pods -n banking 2>/dev/null || echo "⚠️  Không có pods (namespace có thể chưa được tạo)"
echo ""

echo "✨ Cleanup và deploy hoàn tất!"
echo ""
echo "📝 Next steps:"
echo "   1. Kiểm tra ArgoCD UI để xem status của các Applications"
echo "   2. Nếu có lỗi, xem logs: argocd app get <app-name>"
echo "   3. Kiểm tra pods: kubectl get pods -n banking"
