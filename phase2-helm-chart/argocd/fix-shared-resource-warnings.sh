#!/bin/bash
# Script: Fix SharedResourceWarning - Đảm bảo chỉ namespace.yaml tạo namespace/secret
# Cách dùng: ./fix-shared-resource-warnings.sh

set -e

echo "🔧 Fixing SharedResourceWarning - Đảm bảo chỉ namespace.yaml tạo namespace/secret..."
echo ""

# Bước 1: Apply lại tất cả Applications với namespace.enabled=false và secret.enabled=false
echo "📋 Step 1: Applying Applications với namespace.enabled=false và secret.enabled=false..."
kubectl apply -f applications/ -n argocd
echo "✅ Đã apply Applications"
echo ""

# Bước 2: Hard refresh tất cả Applications
echo "📋 Step 2: Hard refreshing Applications..."
for app in banking-demo-namespace banking-demo-postgres banking-demo-redis banking-demo-kong \
           banking-demo-auth-service banking-demo-account-service banking-demo-transfer-service \
           banking-demo-notification-service banking-demo-frontend banking-demo-ingress; do
  echo "   Refreshing $app..."
  argocd app get $app --refresh 2>/dev/null || echo "   ⚠️  $app không tồn tại"
done
echo "✅ Đã refresh Applications"
echo ""

# Bước 3: Sync lại
echo "📋 Step 3: Syncing Applications..."
echo "   Sync namespace (wave -1)..."
argocd app sync banking-demo-namespace --timeout 300 || echo "⚠️  Sync namespace failed"
sleep 5

echo "   Sync postgres và redis (wave 0)..."
argocd app sync banking-demo-postgres --timeout 300 || echo "⚠️  Sync postgres failed"
argocd app sync banking-demo-redis --timeout 300 || echo "⚠️  Sync redis failed"
echo ""

# Bước 4: Kiểm tra SharedResourceWarning
echo "📋 Step 4: Kiểm tra SharedResourceWarning..."
echo ""
echo "Application conditions:"
kubectl get application banking-demo-namespace -n argocd -o yaml 2>/dev/null | grep -A 10 "conditions:" || echo "⚠️  Không có conditions"
echo ""

# Bước 5: Kiểm tra manifests
echo "📋 Step 5: Kiểm tra manifests không có namespace/secret..."
echo ""
echo "Auth Service manifests (không nên có namespace/secret):"
AUTH_MANIFESTS=$(argocd app manifests banking-demo-auth-service 2>/dev/null || echo "")
if echo "$AUTH_MANIFESTS" | grep -q "kind: Namespace\|kind: Secret"; then
  echo "   ❌ Vẫn có namespace/secret trong manifests!"
  echo "   → Cần kiểm tra parameters"
else
  echo "   ✅ Không có namespace/secret trong manifests"
fi
echo ""

echo "Notification Service manifests (không nên có namespace/secret):"
NOTIF_MANIFESTS=$(argocd app manifests banking-demo-notification-service 2>/dev/null || echo "")
if echo "$NOTIF_MANIFESTS" | grep -q "kind: Namespace\|kind: Secret"; then
  echo "   ❌ Vẫn có namespace/secret trong manifests!"
  echo "   → Cần kiểm tra parameters"
else
  echo "   ✅ Không có namespace/secret trong manifests"
fi
echo ""

echo "✨ Fix hoàn tất!"
echo ""
echo "📝 Kiểm tra trong ArgoCD UI:"
echo "   - Vào Application → Application conditions"
echo "   - Không còn SharedResourceWarning"
echo "   - Namespace chỉ được quản lý bởi banking-demo-namespace"
echo "   - Secret chỉ được quản lý bởi banking-demo-namespace"
