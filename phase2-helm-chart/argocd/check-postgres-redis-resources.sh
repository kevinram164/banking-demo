#!/bin/bash
# Script: Kiểm tra tại sao postgres và redis không được tạo
# Cách dùng: ./check-postgres-redis-resources.sh

set -e

echo "🔍 Kiểm tra tại sao postgres và redis không được tạo..."
echo ""

# Bước 1: Kiểm tra namespace
echo "📋 Step 1: Kiểm tra namespace 'banking'..."
if kubectl get namespace banking &>/dev/null; then
    echo "   ✅ Namespace 'banking' tồn tại"
    NAMESPACE_EXISTS=true
else
    echo "   ❌ Namespace 'banking' KHÔNG tồn tại!"
    echo "   → Cần deploy banking-demo-namespace trước"
    NAMESPACE_EXISTS=false
fi
echo ""

# Bước 2: Kiểm tra Applications
echo "📋 Step 2: Kiểm tra ArgoCD Applications..."
for app in banking-demo-namespace banking-demo-postgres banking-demo-redis; do
    if kubectl get application $app -n argocd &>/dev/null; then
        STATUS=$(kubectl get application $app -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")
        HEALTH=$(kubectl get application $app -n argocd -o jsonpath='{.status.health.status}' 2>/dev/null || echo "Unknown")
        echo "   $app: Sync=$STATUS, Health=$HEALTH"
    else
        echo "   ❌ $app không tồn tại!"
    fi
done
echo ""

# Bước 3: Kiểm tra merged values từ ArgoCD
echo "📋 Step 3: Kiểm tra merged values từ ArgoCD..."
echo ""

echo "Postgres Application - Merged values:"
POSTGRES_VALUES=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.status.sourceType}' 2>/dev/null || echo "")
if [ -n "$POSTGRES_VALUES" ]; then
    echo "   Source type: $POSTGRES_VALUES"
    # Lấy valueFiles
    VALUE_FILES=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.spec.source.helm.valueFiles[*]}' 2>/dev/null || echo "")
    echo "   Value files: $VALUE_FILES"
    # Lấy parameters
    PARAMS=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.spec.source.helm.parameters[*].name}' 2>/dev/null || echo "")
    echo "   Parameters: $PARAMS"
    # Kiểm tra postgres.enabled
    POSTGRES_ENABLED=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.spec.source.helm.parameters[?(@.name=="postgres.enabled")].value}' 2>/dev/null || echo "")
    if [ -z "$POSTGRES_ENABLED" ]; then
        echo "   ⚠️  postgres.enabled không có trong parameters (sẽ dùng từ valueFiles)"
    else
        echo "   postgres.enabled=$POSTGRES_ENABLED"
    fi
else
    echo "   ❌ Không thể lấy thông tin Application"
fi
echo ""

echo "Redis Application - Merged values:"
REDIS_VALUES=$(kubectl get application banking-demo-redis -n argocd -o jsonpath='{.status.sourceType}' 2>/dev/null || echo "")
if [ -n "$REDIS_VALUES" ]; then
    echo "   Source type: $REDIS_VALUES"
    VALUE_FILES=$(kubectl get application banking-demo-redis -n argocd -o jsonpath='{.spec.source.helm.parameters[*].name}' 2>/dev/null || echo "")
    echo "   Parameters: $VALUE_FILES"
    REDIS_ENABLED=$(kubectl get application banking-demo-redis -n argocd -o jsonpath='{.spec.source.helm.parameters[?(@.name=="redis.enabled")].value}' 2>/dev/null || echo "")
    if [ -z "$REDIS_ENABLED" ]; then
        echo "   ⚠️  redis.enabled không có trong parameters (sẽ dùng từ valueFiles)"
    else
        echo "   redis.enabled=$REDIS_ENABLED"
    fi
else
    echo "   ❌ Không thể lấy thông tin Application"
fi
echo ""

# Bước 4: Kiểm tra resources trong cluster
if [ "$NAMESPACE_EXISTS" = true ]; then
    echo "📋 Step 4: Kiểm tra resources trong namespace 'banking'..."
    echo ""
    
    echo "Pods:"
    PODS=$(kubectl get pods -n banking 2>/dev/null | grep -E "postgres|redis" || echo "   Không có postgres/redis pods")
    echo "$PODS"
    echo ""
    
    echo "StatefulSets:"
    STS=$(kubectl get statefulsets -n banking 2>/dev/null | grep -E "postgres|redis" || echo "   Không có postgres/redis statefulsets")
    echo "$STS"
    echo ""
    
    echo "Services:"
    SVCS=$(kubectl get services -n banking 2>/dev/null | grep -E "postgres|redis" || echo "   Không có postgres/redis services")
    echo "$SVCS"
    echo ""
    
    echo "PVCs:"
    PVCS=$(kubectl get pvc -n banking 2>/dev/null | grep -E "postgres|redis" || echo "   Không có postgres/redis PVCs")
    echo "$PVCS"
    echo ""
fi

# Bước 5: Test Helm template render
echo "📋 Step 5: Test Helm template render (local)..."
echo ""
echo "Testing postgres template với values từ charts:"
cd banking-demo 2>/dev/null || cd ../banking-demo || { echo "   ⚠️  Không tìm thấy thư mục banking-demo"; exit 1; }

POSTGRES_OUTPUT=$(helm template test . \
  --values charts/common/values.yaml \
  --values charts/postgres/values.yaml \
  --set namespace.enabled=false \
  --set secret.enabled=false \
  --set postgres.enabled=true \
  --set redis.enabled=false \
  2>&1)

if echo "$POSTGRES_OUTPUT" | grep -q "kind: StatefulSet"; then
    echo "   ✅ Helm template render StatefulSet cho postgres"
    if echo "$POSTGRES_OUTPUT" | grep -q "name: postgres"; then
        echo "   ✅ StatefulSet name đúng: postgres"
    fi
else
    echo "   ❌ Helm template KHÔNG render StatefulSet cho postgres!"
    echo "   Output:"
    echo "$POSTGRES_OUTPUT" | head -20
fi
echo ""

echo "Testing redis template với values từ charts:"
REDIS_OUTPUT=$(helm template test . \
  --values charts/common/values.yaml \
  --values charts/redis/values.yaml \
  --set namespace.enabled=false \
  --set secret.enabled=false \
  --set postgres.enabled=false \
  --set redis.enabled=true \
  2>&1)

if echo "$REDIS_OUTPUT" | grep -q "kind: StatefulSet"; then
    echo "   ✅ Helm template render StatefulSet cho redis"
    if echo "$REDIS_OUTPUT" | grep -q "name: redis"; then
        echo "   ✅ StatefulSet name đúng: redis"
    fi
else
    echo "   ❌ Helm template KHÔNG render StatefulSet cho redis!"
    echo "   Output:"
    echo "$REDIS_OUTPUT" | head -20
fi
echo ""

# Bước 6: Kiểm tra ArgoCD sync status chi tiết
echo "📋 Step 6: Kiểm tra ArgoCD sync status chi tiết..."
echo ""

for app in banking-demo-postgres banking-demo-redis; do
    if kubectl get application $app -n argocd &>/dev/null; then
        echo "$app:"
        # Kiểm tra sync status
        SYNC_STATUS=$(kubectl get application $app -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")
        echo "   Sync Status: $SYNC_STATUS"
        
        # Kiểm tra health
        HEALTH=$(kubectl get application $app -n argocd -o jsonpath='{.status.health.status}' 2>/dev/null || echo "Unknown")
        echo "   Health: $HEALTH"
        
        # Kiểm tra conditions
        CONDITIONS=$(kubectl get application $app -n argocd -o jsonpath='{.status.conditions[*].type}' 2>/dev/null || echo "")
        if [ -n "$CONDITIONS" ]; then
            echo "   Conditions: $CONDITIONS"
        fi
        
        # Kiểm tra resources
        RESOURCES=$(kubectl get application $app -n argocd -o jsonpath='{.status.resources[*].kind}' 2>/dev/null || echo "")
        if [ -n "$RESOURCES" ]; then
            echo "   Resources: $RESOURCES"
        else
            echo "   ⚠️  Không có resources được liệt kê!"
        fi
        
        # Kiểm tra sync error
        SYNC_ERROR=$(kubectl get application $app -n argocd -o jsonpath='{.status.conditions[?(@.type=="SyncError")].message}' 2>/dev/null || echo "")
        if [ -n "$SYNC_ERROR" ]; then
            echo "   ❌ Sync Error: $SYNC_ERROR"
        fi
        echo ""
    fi
done

echo "✨ Kiểm tra hoàn tất!"
echo ""
echo "📝 Tóm tắt:"
echo "   - Nếu namespace không tồn tại → Deploy banking-demo-namespace trước"
echo "   - Nếu Helm template không render → Kiểm tra templates và values"
echo "   - Nếu ArgoCD không sync → Hard refresh và sync lại"
echo "   - Nếu có SyncError → Xem chi tiết trong ArgoCD UI"
