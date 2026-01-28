#!/bin/bash
# Script: Fix postgres/redis không có resources mặc dù Application Synced
# Cách dùng: ./fix-postgres-redis-no-resources-v2.sh

set -e

echo "🔧 Fixing postgres/redis không có resources mặc dù Application Synced..."
echo ""

# Bước 1: Kiểm tra và đảm bảo Applications tồn tại
echo "📋 Step 1: Kiểm tra và đảm bảo Applications tồn tại..."
for app in banking-demo-postgres banking-demo-redis; do
    if kubectl get application $app -n argocd &>/dev/null; then
        echo "   ✅ $app tồn tại"
    else
        echo "   ⚠️  $app không tồn tại - đang tạo..."
        if [ "$app" = "banking-demo-postgres" ]; then
            kubectl apply -f applications/postgres.yaml -n argocd
        else
            kubectl apply -f applications/redis.yaml -n argocd
        fi
        sleep 3
    fi
done
echo ""

# Bước 2: Đợi ArgoCD xử lý
echo "📋 Step 2: Đợi ArgoCD xử lý Applications (5 giây)..."
sleep 5
echo ""

# Bước 3: Hard refresh từng Application
echo "📋 Step 3: Hard refresh từng Application..."
for app in banking-demo-postgres banking-demo-redis; do
    echo "   Hard refreshing $app..."
    # Method 1: Patch annotation
    kubectl patch application $app -n argocd --type merge \
      -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}' 2>/dev/null || true
    kubectl annotate application $app -n argocd argocd.argoproj.io/refresh- 2>/dev/null || true
    
    # Method 2: Trigger refresh bằng cách update revision
    CURRENT_REV=$(kubectl get application $app -n argocd -o jsonpath='{.spec.source.targetRevision}' 2>/dev/null || echo "main")
    kubectl patch application $app -n argocd --type merge \
      -p "{\"spec\":{\"source\":{\"targetRevision\":\"$CURRENT_REV\"}}}" 2>/dev/null || true
    
    sleep 3
done
echo "✅ Đã hard refresh Applications"
echo ""

# Bước 4: Đợi ArgoCD render
echo "📋 Step 4: Đợi ArgoCD render manifests (15 giây)..."
sleep 15
echo ""

# Bước 5: Kiểm tra resources trong ArgoCD
echo "📋 Step 5: Kiểm tra resources trong ArgoCD..."
echo ""

for app in banking-demo-postgres banking-demo-redis; do
    echo "$app:"
    
    # Kiểm tra sync status
    SYNC_STATUS=$(kubectl get application $app -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")
    echo "   Sync Status: $SYNC_STATUS"
    
    # Kiểm tra resources
    RESOURCES=$(kubectl get application $app -n argocd -o jsonpath='{.status.resources[*].kind}' 2>/dev/null || echo "")
    if [ -n "$RESOURCES" ]; then
        echo "   ✅ Resources: $RESOURCES"
        RESOURCE_COUNT=$(echo "$RESOURCES" | wc -w)
        echo "   ✅ Tổng số resources: $RESOURCE_COUNT"
    else
        echo "   ❌ Không có resources được liệt kê!"
        
        # Kiểm tra conditions
        CONDITIONS=$(kubectl get application $app -n argocd -o jsonpath='{.status.conditions[*].type}' 2>/dev/null || echo "")
        if [ -n "$CONDITIONS" ]; then
            echo "   Conditions: $CONDITIONS"
        fi
        
        # Kiểm tra sync error
        SYNC_ERROR=$(kubectl get application $app -n argocd -o jsonpath='{.status.conditions[?(@.type=="SyncError")].message}' 2>/dev/null || echo "")
        if [ -n "$SYNC_ERROR" ]; then
            echo "   ❌ Sync Error: $SYNC_ERROR"
        fi
        
        # Kiểm tra comparison error
        COMPARE_ERROR=$(kubectl get application $app -n argocd -o jsonpath='{.status.conditions[?(@.type=="ComparisonError")].message}' 2>/dev/null || echo "")
        if [ -n "$COMPARE_ERROR" ]; then
            echo "   ❌ Comparison Error: $COMPARE_ERROR"
        fi
    fi
    echo ""
done

# Bước 6: Kiểm tra resources trong cluster
echo "📋 Step 6: Kiểm tra resources trong cluster..."
echo ""

if kubectl get namespace banking &>/dev/null; then
    echo "Pods:"
    kubectl get pods -n banking 2>/dev/null | grep -E "postgres|redis" || echo "   Không có postgres/redis pods"
    echo ""
    
    echo "StatefulSets:"
    kubectl get statefulsets -n banking 2>/dev/null | grep -E "postgres|redis" || echo "   Không có postgres/redis statefulsets"
    echo ""
    
    echo "Services:"
    kubectl get services -n banking 2>/dev/null | grep -E "postgres|redis" || echo "   Không có postgres/redis services"
    echo ""
else
    echo "   ⚠️  Namespace 'banking' không tồn tại!"
fi

# Bước 7: Kiểm tra xem có thể render được không
echo "📋 Step 7: Kiểm tra Helm template render..."
echo ""

cd banking-demo 2>/dev/null || cd ../banking-demo || { echo "   ⚠️  Không tìm thấy thư mục banking-demo"; exit 1; }

echo "Testing postgres template:"
POSTGRES_TEST=$(helm template test . \
  --values charts/common/values.yaml \
  --values charts/postgres/values.yaml \
  --set namespace.enabled=false \
  --set secret.enabled=false \
  --set postgres.enabled=true \
  --set redis.enabled=false \
  2>&1)

if echo "$POSTGRES_TEST" | grep -q "kind: StatefulSet"; then
    echo "   ✅ Helm template render thành công"
    RESOURCE_COUNT=$(echo "$POSTGRES_TEST" | grep -c "kind:" || echo "0")
    echo "   ✅ Tổng số resources: $RESOURCE_COUNT"
else
    echo "   ❌ Helm template KHÔNG render!"
    echo "   Output:"
    echo "$POSTGRES_TEST" | head -20
fi
echo ""

# Bước 8: Nếu vẫn không có resources, thử sync thủ công
echo "📋 Step 8: Hướng dẫn sync thủ công..."
echo ""
echo "Nếu vẫn không có resources sau script này:"
echo ""
echo "1. Vào ArgoCD UI → Applications → banking-demo-postgres"
echo "2. Click nút 'REFRESH' (hard refresh)"
echo "3. Đợi 10-15 giây"
echo "4. Click nút 'SYNC'"
echo "5. Chọn 'Synchronize' và đợi sync xong"
echo ""
echo "Lặp lại cho banking-demo-redis"
echo ""

echo "✨ Fix hoàn tất!"
echo ""
echo "💡 Nếu vẫn không có resources:"
echo "   - Chạy script debug: ./debug-argocd-render.sh"
echo "   - Kiểm tra ArgoCD logs: kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller --tail=100"
echo "   - Kiểm tra Git repo có đúng không"
echo "   - Kiểm tra Helm chart có lỗi syntax không"
