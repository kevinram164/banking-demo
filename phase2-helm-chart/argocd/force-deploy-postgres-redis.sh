#!/bin/bash
# Script: Force deploy postgres và redis - Đảm bảo chúng được tạo
# Cách dùng: ./force-deploy-postgres-redis.sh

set -e

echo "🚀 Force deploy postgres và redis..."
echo ""

# Bước 1: Đảm bảo namespace tồn tại
echo "📋 Step 1: Đảm bảo namespace 'banking' tồn tại..."
if ! kubectl get namespace banking &>/dev/null; then
    echo "   ⚠️  Namespace không tồn tại - đang deploy banking-demo-namespace..."
    
    # Apply namespace Application
    if kubectl get application banking-demo-namespace -n argocd &>/dev/null; then
        echo "   Application banking-demo-namespace tồn tại - đang sync..."
        # Hard refresh
        kubectl patch application banking-demo-namespace -n argocd --type merge \
          -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}' 2>/dev/null || true
        kubectl annotate application banking-demo-namespace -n argocd argocd.argoproj.io/refresh- 2>/dev/null || true
        
        # Đợi namespace được tạo
        echo "   Đợi namespace được tạo..."
        for i in {1..30}; do
            if kubectl get namespace banking &>/dev/null; then
                echo "   ✅ Namespace đã được tạo!"
                break
            fi
            echo "   Đợi... ($i/30)"
            sleep 2
        done
        
        if ! kubectl get namespace banking &>/dev/null; then
            echo "   ❌ Namespace vẫn chưa được tạo sau 60 giây!"
            echo "   → Kiểm tra Application banking-demo-namespace trong ArgoCD UI"
            exit 1
        fi
    else
        echo "   ❌ Application banking-demo-namespace không tồn tại!"
        echo "   → Apply namespace.yaml trước: kubectl apply -f applications/namespace.yaml -n argocd"
        exit 1
    fi
else
    echo "   ✅ Namespace đã tồn tại"
fi
echo ""

# Bước 2: Đảm bảo secret tồn tại
echo "📋 Step 2: Kiểm tra secret 'banking-db-secret'..."
if ! kubectl get secret banking-db-secret -n banking &>/dev/null; then
    echo "   ⚠️  Secret không tồn tại - đang đợi namespace Application sync..."
    sleep 5
    
    # Kiểm tra lại
    if ! kubectl get secret banking-db-secret -n banking &>/dev/null; then
        echo "   ⚠️  Secret vẫn chưa có - có thể namespace Application chưa sync xong"
        echo "   → Sync banking-demo-namespace trong ArgoCD UI"
    else
        echo "   ✅ Secret đã được tạo"
    fi
else
    echo "   ✅ Secret đã tồn tại"
fi
echo ""

# Bước 3: Hard refresh và sync postgres Application
echo "📋 Step 3: Hard refresh và sync postgres Application..."
if kubectl get application banking-demo-postgres -n argocd &>/dev/null; then
    echo "   Hard refreshing banking-demo-postgres..."
    kubectl patch application banking-demo-postgres -n argocd --type merge \
      -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}' 2>/dev/null || true
    kubectl annotate application banking-demo-postgres -n argocd argocd.argoproj.io/refresh- 2>/dev/null || true
    
    echo "   Đợi ArgoCD refresh (5 giây)..."
    sleep 5
    
    echo "   Kiểm tra sync status..."
    SYNC_STATUS=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")
    echo "   Sync Status: $SYNC_STATUS"
    
    if [ "$SYNC_STATUS" != "Synced" ]; then
        echo "   ⚠️  Application chưa synced - cần sync thủ công trong ArgoCD UI"
    fi
else
    echo "   ❌ Application banking-demo-postgres không tồn tại!"
    echo "   → Apply: kubectl apply -f applications/postgres.yaml -n argocd"
    exit 1
fi
echo ""

# Bước 4: Hard refresh và sync redis Application
echo "📋 Step 4: Hard refresh và sync redis Application..."
if kubectl get application banking-demo-redis -n argocd &>/dev/null; then
    echo "   Hard refreshing banking-demo-redis..."
    kubectl patch application banking-demo-redis -n argocd --type merge \
      -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}' 2>/dev/null || true
    kubectl annotate application banking-demo-redis -n argocd argocd.argoproj.io/refresh- 2>/dev/null || true
    
    echo "   Đợi ArgoCD refresh (5 giây)..."
    sleep 5
    
    echo "   Kiểm tra sync status..."
    SYNC_STATUS=$(kubectl get application banking-demo-redis -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")
    echo "   Sync Status: $SYNC_STATUS"
    
    if [ "$SYNC_STATUS" != "Synced" ]; then
        echo "   ⚠️  Application chưa synced - cần sync thủ công trong ArgoCD UI"
    fi
else
    echo "   ❌ Application banking-demo-redis không tồn tại!"
    echo "   → Apply: kubectl apply -f applications/redis.yaml -n argocd"
    exit 1
fi
echo ""

# Bước 5: Kiểm tra resources được tạo
echo "📋 Step 5: Kiểm tra resources được tạo..."
echo ""

echo "Đợi resources được tạo (30 giây)..."
sleep 30

echo "Pods:"
kubectl get pods -n banking -l app.kubernetes.io/name=postgres 2>/dev/null || echo "   Không có postgres pods"
kubectl get pods -n banking -l app.kubernetes.io/name=redis 2>/dev/null || echo "   Không có redis pods"
echo ""

echo "StatefulSets:"
kubectl get statefulsets -n banking 2>/dev/null | grep -E "postgres|redis" || echo "   Không có postgres/redis statefulsets"
echo ""

echo "Services:"
kubectl get services -n banking 2>/dev/null | grep -E "postgres|redis" || echo "   Không có postgres/redis services"
echo ""

# Bước 6: Kiểm tra ArgoCD Application resources
echo "📋 Step 6: Kiểm tra ArgoCD Application resources..."
echo ""

for app in banking-demo-postgres banking-demo-redis; do
    echo "$app resources trong ArgoCD:"
    RESOURCES=$(kubectl get application $app -n argocd -o jsonpath='{.status.resources[*].kind}' 2>/dev/null || echo "")
    if [ -n "$RESOURCES" ]; then
        echo "   $RESOURCES"
        
        # Đếm số resources
        RESOURCE_COUNT=$(kubectl get application $app -n argocd -o jsonpath='{.status.resources[*].kind}' 2>/dev/null | wc -w || echo "0")
        echo "   Tổng số resources: $RESOURCE_COUNT"
        
        if [ "$RESOURCE_COUNT" -eq "0" ]; then
            echo "   ⚠️  Application không có resources nào!"
            echo "   → Kiểm tra Helm values và templates"
        fi
    else
        echo "   ⚠️  Không có resources được liệt kê!"
    fi
    echo ""
done

echo "✨ Force deploy hoàn tất!"
echo ""
echo "📝 Nếu vẫn không có resources:"
echo "   1. Vào ArgoCD UI → Application → Sync"
echo "   2. Kiểm tra Application conditions"
echo "   3. Xem rendered manifests trong ArgoCD UI"
echo "   4. Chạy script debug: ./check-postgres-redis-resources.sh"
