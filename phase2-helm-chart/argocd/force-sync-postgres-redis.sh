#!/bin/bash
# Script: Force sync postgres và redis - Đảm bảo chúng được deploy
# Cách dùng: ./force-sync-postgres-redis.sh

set -e

echo "🚀 Force sync postgres và redis..."
echo ""

# Bước 1: Kiểm tra Applications tồn tại
echo "📋 Step 1: Kiểm tra Applications tồn tại..."
for app in banking-demo-postgres banking-demo-redis; do
    if kubectl get application $app -n argocd &>/dev/null; then
        echo "   ✅ $app tồn tại"
    else
        echo "   ❌ $app không tồn tại - đang tạo..."
        if [ "$app" = "banking-demo-postgres" ]; then
            kubectl apply -f applications/postgres.yaml -n argocd
        else
            kubectl apply -f applications/redis.yaml -n argocd
        fi
        sleep 3
    fi
done
echo ""

# Bước 2: Hard refresh
echo "📋 Step 2: Hard refresh Applications..."
for app in banking-demo-postgres banking-demo-redis; do
    echo "   Hard refreshing $app..."
    # Method 1: Annotation
    kubectl patch application $app -n argocd --type merge \
      -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}' 2>/dev/null || true
    kubectl annotate application $app -n argocd argocd.argoproj.io/refresh- 2>/dev/null || true
    
    # Method 2: Trigger bằng cách update một field nhỏ
    CURRENT_REV=$(kubectl get application $app -n argocd -o jsonpath='{.spec.source.targetRevision}' 2>/dev/null || echo "main")
    kubectl patch application $app -n argocd --type json \
      -p "[{\"op\":\"replace\",\"path\":\"/spec/source/targetRevision\",\"value\":\"$CURRENT_REV\"}]" 2>/dev/null || true
    
    sleep 2
done
echo "✅ Đã hard refresh"
echo ""

# Bước 3: Đợi ArgoCD refresh
echo "📋 Step 3: Đợi ArgoCD refresh (15 giây)..."
sleep 15
echo ""

# Bước 4: Kiểm tra sync status
echo "📋 Step 4: Kiểm tra sync status..."
for app in banking-demo-postgres banking-demo-redis; do
    SYNC_STATUS=$(kubectl get application $app -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")
    HEALTH=$(kubectl get application $app -n argocd -o jsonpath='{.status.health.status}' 2>/dev/null || echo "Unknown")
    echo "   $app: Sync=$SYNC_STATUS, Health=$HEALTH"
    
    # Kiểm tra resources
    RESOURCES=$(kubectl get application $app -n argocd -o jsonpath='{.status.resources[*].kind}' 2>/dev/null || echo "")
    if [ -n "$RESOURCES" ]; then
        echo "   ✅ Resources: $RESOURCES"
    else
        echo "   ⚠️  Không có resources"
    fi
done
echo ""

# Bước 5: Nếu vẫn không có resources, thử sync operation
echo "📋 Step 5: Trigger sync operation..."
for app in banking-demo-postgres banking-demo-redis; do
    echo "   Triggering sync cho $app..."
    
    # Tạo sync operation
    kubectl patch application $app -n argocd --type merge \
      -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{"revision":"HEAD"}}}' 2>/dev/null || true
    
    sleep 3
done
echo ""

# Bước 6: Đợi sync hoàn tất
echo "📋 Step 6: Đợi sync hoàn tất (20 giây)..."
sleep 20
echo ""

# Bước 7: Kiểm tra lại
echo "📋 Step 7: Kiểm tra lại resources..."
echo ""

for app in banking-demo-postgres banking-demo-redis; do
    echo "$app:"
    
    # Kiểm tra sync status
    SYNC_STATUS=$(kubectl get application $app -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")
    echo "   Sync Status: $SYNC_STATUS"
    
    # Kiểm tra resources trong ArgoCD
    RESOURCES=$(kubectl get application $app -n argocd -o jsonpath='{.status.resources[*].kind}' 2>/dev/null || echo "")
    if [ -n "$RESOURCES" ]; then
        echo "   ✅ ArgoCD Resources: $RESOURCES"
        RESOURCE_COUNT=$(echo "$RESOURCES" | wc -w)
        echo "   ✅ Tổng số: $RESOURCE_COUNT"
    else
        echo "   ❌ Không có resources trong ArgoCD!"
        
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

# Bước 8: Kiểm tra resources trong cluster
echo "📋 Step 8: Kiểm tra resources trong cluster..."
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

echo "✨ Force sync hoàn tất!"
echo ""
echo "📝 Nếu vẫn không có resources:"
echo "   1. Vào ArgoCD UI → Applications → banking-demo-postgres"
echo "   2. Click 'REFRESH' (hard refresh)"
echo "   3. Đợi 10-15 giây"
echo "   4. Click 'SYNC' → 'Synchronize'"
echo "   5. Kiểm tra tab 'MANIFESTS' xem ArgoCD có render được không"
echo ""
echo "   6. Kiểm tra ArgoCD logs:"
echo "      ARGOCD_POD=\$(kubectl get pods -n argocd -l app.kubernetes.io/name=argocd-application-controller -o jsonpath='{.items[0].metadata.name}')"
echo "      kubectl logs -n argocd \$ARGOCD_POD --tail=100 | grep -i postgres"
