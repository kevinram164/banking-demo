# PowerShell Script: Xóa secret có finalizers đang chặn việc xóa namespace
# Cách dùng: .\fix-secret-finalizers.ps1 [namespace] [secret-name]
# Ví dụ: .\fix-secret-finalizers.ps1 banking banking-db-secret

param(
    [string]$Namespace = "banking",
    [string]$SecretName = "banking-db-secret"
)

Write-Host "🔧 Fixing secret '$SecretName' trong namespace '$Namespace'..." -ForegroundColor Cyan
Write-Host ""

# Bước 1: Kiểm tra secret có tồn tại không
$exists = kubectl get secret $SecretName -n $Namespace 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "✅ Secret '$SecretName' không tồn tại trong namespace '$Namespace'" -ForegroundColor Green
    exit 0
}

Write-Host "📋 Step 1: Checking secret status..." -ForegroundColor Yellow
kubectl get secret $SecretName -n $Namespace -o yaml | Select-String -Pattern "finalizers|deletionTimestamp"
Write-Host ""

# Bước 2: Xóa finalizers của secret
Write-Host "📋 Step 2: Removing finalizers from secret..." -ForegroundColor Yellow
kubectl patch secret $SecretName -n $Namespace -p '{\"metadata\":{\"finalizers\":[]}}' --type=merge 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Patch không thành công, thử cách khác..." -ForegroundColor Yellow
    $secretJson = kubectl get secret $SecretName -n $Namespace -o json | ConvertFrom-Json
    $secretJson.metadata.finalizers = @()
    $secretJson | ConvertTo-Json -Depth 10 | kubectl replace -f - 2>&1 | Out-Null
}
Write-Host ""

# Bước 3: Xóa secret
Write-Host "📋 Step 3: Deleting secret..." -ForegroundColor Yellow
kubectl delete secret $SecretName -n $Namespace --force --grace-period=0 2>&1 | Out-Null
Write-Host ""

# Bước 4: Kiểm tra lại
$exists = kubectl get secret $SecretName -n $Namespace 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "⚠️  Secret vẫn còn tồn tại sau khi xóa finalizers" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "📝 Thử các lệnh sau thủ công:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   1. Xem finalizers của secret:"
    Write-Host "      kubectl get secret $SecretName -n $Namespace -o yaml | grep finalizers"
    Write-Host ""
    Write-Host "   2. Xóa finalizers thủ công:"
    Write-Host "      kubectl patch secret $SecretName -n $Namespace -p '{\"metadata\":{\"finalizers\":[]}}' --type=merge"
    Write-Host ""
    Write-Host "   3. Xóa secret với force:"
    Write-Host "      kubectl delete secret $SecretName -n $Namespace --force --grace-period=0"
    Write-Host ""
    Write-Host "   4. Nếu vẫn không được, xóa tất cả resources trong namespace:"
    Write-Host "      kubectl delete all --all -n $Namespace --force --grace-period=0"
    Write-Host "      kubectl delete secrets --all -n $Namespace --force --grace-period=0"
    Write-Host "      kubectl delete configmaps --all -n $Namespace --force --grace-period=0"
} else {
    Write-Host "✅ Secret đã được xóa thành công" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 Bây giờ có thể xóa namespace:" -ForegroundColor Cyan
    Write-Host "   kubectl delete namespace $Namespace --force --grace-period=0"
}
