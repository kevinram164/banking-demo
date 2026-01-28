#!/bin/bash
# Script: Fix SharedResourceWarning - Đảm bảo chỉ namespace.yaml tạo namespace/secret
# Cách dùng: ./fix-shared-resource-warnings.sh

set -e

echo "🔧 Fixing SharedResourceWarning - Đảm bảo chỉ namespace.yaml tạo namespace/secret..."
echo ""

# Bước 0: Kiểm tra và xóa Application banking-demo cũ (nếu có)
echo "📋 Step 0: Kiểm tra Application banking-demo cũ (gây conflict)..."
if kubectl get application banking-demo -n argocd &>/dev/null; then
  echo "   ⚠️  Tìm thấy Application 'banking-demo' cũ - đang xóa..."
  kubectl delete application banking-demo -n argocd --cascade=false 2>/dev/null || true
  echo "   ✅ Đã xóa Application banking-demo cũ"
else
  echo "   ✅ Không có Application banking-demo cũ"
fi
echo ""

# Bước 1: Apply lại tất cả Applications với namespace.enabled=false và secret.enabled=false
echo "📋 Step 1: Applying Applications với namespace.enabled=false và secret.enabled=false..."
kubectl apply -f applications/ -n argocd
echo "✅ Đã apply Applications"
echo ""

# Bước 2: Hard refresh tất cả Applications bằng kubectl patch (không cần ArgoCD CLI)
echo "📋 Step 2: Hard refreshing Applications bằng kubectl..."
for app in banking-demo-namespace banking-demo-postgres banking-demo-redis banking-demo-kong \
           banking-demo-auth-service banking-demo-account-service banking-demo-transfer-service \
           banking-demo-notification-service banking-demo-frontend banking-demo-ingress; do
  if kubectl get application $app -n argocd &>/dev/null; then
    echo "   Refreshing $app..."
    # Trigger refresh bằng cách patch annotation
    kubectl patch application $app -n argocd --type merge \
      -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}' 2>/dev/null || true
    # Xóa annotation để trigger refresh lại lần sau
    kubectl annotate application $app -n argocd argocd.argoproj.io/refresh- 2>/dev/null || true
  else
    echo "   ⚠️  $app không tồn tại"
  fi
done
echo "✅ Đã refresh Applications"
echo ""

# Đợi ArgoCD xử lý refresh
echo "⏳ Đợi ArgoCD xử lý refresh (10 giây)..."
sleep 10
echo ""

# Bước 3: Kiểm tra SharedResourceWarning
echo "📋 Step 3: Kiểm tra SharedResourceWarning..."
echo ""
echo "Application conditions cho banking-demo-namespace:"
CONDITIONS=$(kubectl get application banking-demo-namespace -n argocd -o jsonpath='{.status.conditions}' 2>/dev/null || echo "[]")
if echo "$CONDITIONS" | grep -q "SharedResourceWarning"; then
  echo "   ⚠️  Vẫn còn SharedResourceWarning!"
  echo ""
  echo "   Chi tiết:"
  kubectl get application banking-demo-namespace -n argocd -o yaml | grep -A 5 "SharedResourceWarning" || true
  echo ""
  echo "   🔍 Kiểm tra Applications nào đang quản lý namespace/secret:"
  echo ""
  echo "   Applications quản lý namespace 'banking':"
  kubectl get applications -n argocd -o json | \
    jq -r '.items[] | select(.spec.destination.namespace == "banking" or (.spec.source.helm.parameters[]? | select(.name == "namespace.enabled" and .value == "true"))) | .metadata.name' 2>/dev/null || \
    kubectl get applications -n argocd -o yaml | grep -B 5 -A 5 "namespace.*banking" || echo "   (Không thể parse - cần kiểm tra thủ công)"
  echo ""
else
  echo "   ✅ Không có SharedResourceWarning!"
fi
echo ""

# Bước 4: Kiểm tra parameters của các Applications
echo "📋 Step 4: Kiểm tra parameters của các Applications..."
echo ""
for app in banking-demo-kong banking-demo-auth-service banking-demo-notification-service \
           banking-demo-account-service banking-demo-transfer-service banking-demo-frontend \
           banking-demo-ingress banking-demo-postgres banking-demo-redis; do
  if kubectl get application $app -n argocd &>/dev/null; then
    echo "   $app:"
    NAMESPACE_ENABLED=$(kubectl get application $app -n argocd -o jsonpath='{.spec.source.helm.parameters[?(@.name=="namespace.enabled")].value}' 2>/dev/null || echo "")
    SECRET_ENABLED=$(kubectl get application $app -n argocd -o jsonpath='{.spec.source.helm.parameters[?(@.name=="secret.enabled")].value}' 2>/dev/null || echo "")
    if [ "$NAMESPACE_ENABLED" != "false" ] || [ "$SECRET_ENABLED" != "false" ]; then
      echo "      ❌ namespace.enabled=$NAMESPACE_ENABLED, secret.enabled=$SECRET_ENABLED"
    else
      echo "      ✅ namespace.enabled=false, secret.enabled=false"
    fi
  fi
done
echo ""

echo "✨ Fix hoàn tất!"
echo ""
echo "📝 Kiểm tra trong ArgoCD UI:"
echo "   - Vào Application → Application conditions"
echo "   - Không còn SharedResourceWarning"
echo "   - Namespace chỉ được quản lý bởi banking-demo-namespace"
echo "   - Secret chỉ được quản lý bởi banking-demo-namespace"
echo ""
echo "💡 Nếu vẫn còn SharedResourceWarning sau 1-2 phút:"
echo "   - Vào ArgoCD UI → Refresh từng Application thủ công"
echo "   - Hoặc sync lại: kubectl patch application <app-name> -n argocd --type merge -p '{\"operation\":{\"initiatedBy\":{\"username\":\"admin\"},\"sync\":{\"revision\":\"HEAD\"}}}'"
