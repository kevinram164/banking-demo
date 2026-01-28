# PowerShell Script: Xử lý namespace đang pending deletion
# Cách dùng: .\fix-namespace-pending-deletion.ps1

$NAMESPACE = "banking"

Write-Host "🔧 Fixing namespace '$NAMESPACE' đang pending deletion..." -ForegroundColor Cyan
Write-Host ""

# Bước 1: Kiểm tra trạng thái namespace
Write-Host "📋 Step 1: Checking namespace status..." -ForegroundColor Yellow
kubectl get namespace $NAMESPACE -o yaml | Select-String -Pattern "deletionTimestamp|finalizers"
Write-Host ""

# Bước 2: Xóa finalizers để force delete namespace
Write-Host "📋 Step 2: Removing finalizers to force delete namespace..." -ForegroundColor Yellow

# Cách 1: Dùng kubectl patch (đơn giản nhất)
kubectl patch namespace $NAMESPACE -p '{\"metadata\":{\"finalizers\":[]}}' --type=merge 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Không thể patch namespace (có thể đã bị xóa hoặc không có quyền)" -ForegroundColor Yellow
}

# Cách 2: Nếu cách 1 không work, dùng PowerShell JSON manipulation
$exists = kubectl get namespace $NAMESPACE 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   Thử cách 2: dùng PowerShell JSON manipulation..." -ForegroundColor Yellow
    $namespaceJson = kubectl get namespace $NAMESPACE -o json | ConvertFrom-Json
    $namespaceJson.spec.finalizers = @()
    $namespaceJson | ConvertTo-Json -Depth 10 | kubectl replace --raw "/api/v1/namespaces/$NAMESPACE/finalize" -f - 2>&1 | Out-Null
}
Write-Host ""

# Bước 3: Đợi namespace bị xóa hoàn toàn
Write-Host "📋 Step 3: Waiting for namespace to be fully deleted..." -ForegroundColor Yellow
for ($i = 1; $i -le 30; $i++) {
    $exists = kubectl get namespace $NAMESPACE 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✅ Namespace đã bị xóa hoàn toàn" -ForegroundColor Green
        break
    }
    Write-Host "   Đợi... ($i/30)"
    Start-Sleep -Seconds 2
}

# Bước 4: Kiểm tra lại
$exists = kubectl get namespace $NAMESPACE 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "⚠️  Namespace vẫn còn tồn tại. Có thể có resources đang chặn việc xóa." -ForegroundColor Yellow
    Write-Host "   Thử xóa thủ công: kubectl delete namespace $NAMESPACE --force --grace-period=0"
} else {
    Write-Host "✅ Namespace đã được xóa thành công" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 Next steps:" -ForegroundColor Cyan
    Write-Host "   1. Deploy lại namespace: kubectl apply -f applications/namespace.yaml -n argocd"
    Write-Host "   2. Sync: argocd app sync banking-demo-namespace"
}
