#!/bin/bash
# Script: Debug ArgoCD không render resources
# Cách dùng: ./debug-argocd-render.sh

set -e

echo "🔍 Debug ArgoCD không render resources..."
echo ""

# Bước 1: Kiểm tra Application spec
echo "📋 Step 1: Kiểm tra Application spec..."
echo ""

for app in banking-demo-postgres banking-demo-redis; do
    echo "$app spec:"
    echo "---"
    kubectl get application $app -n argocd -o yaml | grep -A 30 "spec:" | head -35
    echo ""
done

# Bước 2: Kiểm tra Application status chi tiết
echo "📋 Step 2: Kiểm tra Application status chi tiết..."
echo ""

for app in banking-demo-postgres banking-demo-redis; do
    echo "$app status:"
    echo "---"
    kubectl get application $app -n argocd -o jsonpath='{.status}' | jq '.' 2>/dev/null || \
    kubectl get application $app -n argocd -o yaml | grep -A 50 "status:" | head -60
    echo ""
done

# Bước 3: Kiểm tra ArgoCD controller logs
echo "📋 Step 3: Kiểm tra ArgoCD controller logs (10 dòng cuối)..."
echo ""

ARGOCD_POD=$(kubectl get pods -n argocd -l app.kubernetes.io/name=argocd-application-controller -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$ARGOCD_POD" ]; then
    echo "ArgoCD Controller Pod: $ARGOCD_POD"
    echo "Logs (tìm postgres/redis):"
    kubectl logs -n argocd $ARGOCD_POD --tail=50 2>&1 | grep -i -E "postgres|redis|error|warning" | tail -20 || echo "   Không có logs liên quan"
else
    echo "   ⚠️  Không tìm thấy ArgoCD controller pod"
fi
echo ""

# Bước 4: Test Helm template với exact values từ ArgoCD
echo "📋 Step 4: Test Helm template với exact values từ ArgoCD..."
echo ""

cd banking-demo 2>/dev/null || cd ../banking-demo || { echo "   ⚠️  Không tìm thấy thư mục banking-demo"; exit 1; }

echo "Testing postgres với exact values từ Application:"
POSTGRES_VALUES=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.spec.source.helm.valueFiles[*]}' 2>/dev/null || echo "")
echo "   Value files: $POSTGRES_VALUES"

# Lấy parameters
PARAMS=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{range .spec.source.helm.parameters[*]}{"--set "}{.name}{"="}{.value}{" "}{end}' 2>/dev/null || echo "")

echo "   Testing với parameters: $PARAMS"
echo ""

# Test render
TEST_OUTPUT=$(helm template test . \
  --values charts/common/values.yaml \
  --values charts/postgres/values.yaml \
  --set namespace.enabled=false \
  --set secret.enabled=false \
  --set redis.enabled=false \
  --set kong.enabled=false \
  --set auth-service.enabled=false \
  --set account-service.enabled=false \
  --set transfer-service.enabled=false \
  --set notification-service.enabled=false \
  --set frontend.enabled=false \
  --set ingress.enabled=false \
  2>&1)

if echo "$TEST_OUTPUT" | grep -q "kind: StatefulSet"; then
    echo "   ✅ Helm template render thành công"
    RESOURCE_COUNT=$(echo "$TEST_OUTPUT" | grep -c "kind:" || echo "0")
    echo "   ✅ Tổng số resources: $RESOURCE_COUNT"
else
    echo "   ❌ Helm template KHÔNG render!"
    echo "   Output:"
    echo "$TEST_OUTPUT" | head -30
fi
echo ""

# Bước 5: Kiểm tra Git repo có accessible không
echo "📋 Step 5: Kiểm tra Git repo có accessible không..."
echo ""

REPO_URL=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.spec.source.repoURL}' 2>/dev/null || echo "")
REVISION=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.spec.source.targetRevision}' 2>/dev/null || echo "")
PATH=$(kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.spec.source.path}' 2>/dev/null || echo "")

echo "Repo URL: $REPO_URL"
echo "Revision: $REVISION"
echo "Path: $PATH"
echo ""

# Bước 6: Kiểm tra Application conditions chi tiết
echo "📋 Step 6: Kiểm tra Application conditions chi tiết..."
echo ""

for app in banking-demo-postgres banking-demo-redis; do
    echo "$app conditions:"
    CONDITIONS=$(kubectl get application $app -n argocd -o jsonpath='{.status.conditions[*]}' 2>/dev/null || echo "")
    if [ -n "$CONDITIONS" ]; then
        echo "$CONDITIONS" | jq '.' 2>/dev/null || echo "$CONDITIONS"
    else
        echo "   Không có conditions"
    fi
    echo ""
done

echo "✨ Debug hoàn tất!"
echo ""
echo "📝 Kiểm tra các điểm sau:"
echo "   1. Application spec có đúng repoURL, path, targetRevision không"
echo "   2. ArgoCD controller logs có lỗi gì không"
echo "   3. Helm template render local có đúng không"
echo "   4. Git repo có accessible không"
echo "   5. Application conditions có lỗi gì không"
