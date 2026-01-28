# PowerShell Script: Xóa Application có payload quá lớn (không thể xóa qua UI)
# Cách dùng: .\delete-application-large-payload.ps1 <app-name>
# Ví dụ: .\delete-application-large-payload.ps1 banking-demo-infra

param(
    [Parameter(Mandatory=$true)]
    [string]$AppName
)

$Namespace = "argocd"

Write-Host "🗑️  Deleting Application '$AppName' (payload too large for UI)..." -ForegroundColor Cyan
Write-Host ""

# Bước 1: Kiểm tra Application có tồn tại không
Write-Host "📋 Step 1: Checking if Application exists..." -ForegroundColor Yellow
$exists = kubectl get application $AppName -n $Namespace 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Application '$AppName' không tồn tại" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Application tồn tại" -ForegroundColor Green
Write-Host ""

# Bước 2: Xóa với cascade=false (không xóa resources, chỉ xóa Application)
Write-Host "📋 Step 2: Deleting Application with cascade=false (preserve resources)..." -ForegroundColor Yellow

# Xóa finalizers trước
kubectl patch application $AppName -n $Namespace `
  --type json `
  -p='[{"op": "remove", "path": "/metadata/finalizers"}]' 2>&1 | Out-Null

# Xóa Application
kubectl delete application $AppName -n $Namespace `
  --cascade=false `
  --wait=false 2>&1 | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Application đã được xóa" -ForegroundColor Green
} else {
    Write-Host "⚠️  Application đã được xóa hoặc không thể xóa" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "📝 Note: Resources trong cluster vẫn còn tồn tại." -ForegroundColor Cyan
Write-Host "   Nếu muốn xóa resources, chạy:"
Write-Host "   kubectl delete all --all -n banking"
Write-Host "   kubectl delete namespace banking"
