#!/bin/bash
# Script: So sánh Applications để tìm tại sao postgres/redis không deploy
# Cách dùng: ./compare-applications.sh

set -e

echo "🔍 So sánh Applications để tìm tại sao postgres/redis không deploy..."
echo ""

# Bước 1: So sánh Application config
echo "📋 Step 1: So sánh Application config..."
echo ""

echo "=== Auth Service (đang chạy) ==="
kubectl get application banking-demo-auth-service -n argocd -o yaml | grep -A 15 "spec:" | head -20
echo ""

echo "=== Postgres (không chạy) ==="
kubectl get application banking-demo-postgres -n argocd -o yaml | grep -A 15 "spec:" | head -20
echo ""

# Bước 2: So sánh status
echo "📋 Step 2: So sánh Application status..."
echo ""

echo "=== Auth Service status ==="
kubectl get application banking-demo-auth-service -n argocd -o jsonpath='{.status}' | jq '.' 2>/dev/null || \
kubectl get application banking-demo-auth-service -n argocd -o yaml | grep -A 30 "status:" | head -35
echo ""

echo "=== Postgres status ==="
kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.status}' | jq '.' 2>/dev/null || \
kubectl get application banking-demo-postgres -n argocd -o yaml | grep -A 30 "status:" | head -35
echo ""

# Bước 3: Kiểm tra resources được quản lý
echo "📋 Step 3: Kiểm tra resources được quản lý..."
echo ""

echo "Auth Service resources:"
AUTH_RESOURCES=$(kubectl get application banking-demo-auth-service -n argocd -o jsonpath='{.status.resources[*].kind}' 2>/dev/null || echo "")
if [ -n "$AUTH_RESOURCES" ]; then
    echo "   ✅ $AUTH_RESOURCES"
    AUTH_COUNT=$(echo "$AUTH_RESOURCES" | wc -w)
    echo "   ✅ Tổng số: $AUTH_COUNT"
else
    echo "   ⚠️  Không có resources"
fi
echo ""

echo "Postgres resources:"
POSTGRES_RESOURCES=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.status.resources[*].kind}' 2>/dev/null || echo "")
if [ -n "$POSTGRES_RESOURCES" ]; then
    echo "   ✅ $POSTGRES_RESOURCES"
    POSTGRES_COUNT=$(echo "$POSTGRES_RESOURCES" | wc -w)
    echo "   ✅ Tổng số: $POSTGRES_COUNT"
else
    echo "   ❌ Không có resources"
fi
echo ""

# Bước 4: Kiểm tra pods trong cluster
echo "📋 Step 4: Kiểm tra pods trong cluster..."
echo ""

if kubectl get namespace banking &>/dev/null; then
    echo "Tất cả pods trong namespace banking:"
    kubectl get pods -n banking 2>/dev/null || echo "   Không có pods"
    echo ""
    
    echo "Pods theo label:"
    kubectl get pods -n banking -l app.kubernetes.io/name=banking-demo 2>/dev/null || echo "   Không có pods với label này"
    echo ""
    
    echo "Deployments:"
    kubectl get deployments -n banking 2>/dev/null || echo "   Không có deployments"
    echo ""
    
    echo "StatefulSets:"
    kubectl get statefulsets -n banking 2>/dev/null || echo "   Không có statefulsets"
    echo ""
fi

# Bước 5: Kiểm tra Git repo access
echo "📋 Step 5: Kiểm tra Git repo access..."
echo ""

REPO_URL=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.spec.source.repoURL}' 2>/dev/null || echo "")
REVISION=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.spec.source.targetRevision}' 2>/dev/null || echo "")
PATH=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.spec.source.path}' 2>/dev/null || echo "")

echo "Postgres Application repo config:"
echo "   Repo URL: $REPO_URL"
echo "   Revision: $REVISION"
echo "   Path: $PATH"
echo ""

# Kiểm tra xem repo có trong AppProject không
echo "AppProject sourceRepos:"
kubectl get appproject banking-demo -n argocd -o jsonpath='{.spec.sourceRepos[*]}' 2>/dev/null || echo "   Không tìm thấy AppProject"
echo ""

# Bước 6: Kiểm tra conditions
echo "📋 Step 6: Kiểm tra Application conditions..."
echo ""

for app in banking-demo-auth-service banking-demo-postgres banking-demo-redis; do
    echo "$app conditions:"
    CONDITIONS=$(kubectl get application $app -n argocd -o jsonpath='{.status.conditions[*]}' 2>/dev/null || echo "")
    if [ -n "$CONDITIONS" ]; then
        echo "$CONDITIONS" | jq -r '.[] | "\(.type): \(.message)"' 2>/dev/null || echo "$CONDITIONS"
    else
        echo "   Không có conditions"
    fi
    echo ""
done

echo "✨ So sánh hoàn tất!"
echo ""
echo "📝 Phân tích:"
echo "   - Nếu auth-service có resources nhưng postgres không có → Vấn đề với Helm chart của postgres"
echo "   - Nếu cả hai đều không có resources → Vấn đề với Git repo access"
echo "   - Nếu auth-service có pods nhưng postgres không có → Vấn đề với deployment"
