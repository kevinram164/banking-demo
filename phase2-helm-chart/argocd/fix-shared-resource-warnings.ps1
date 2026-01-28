# Script: Fix SharedResourceWarning - Đảm bảo chỉ namespace.yaml tạo namespace/secret
# Cách dùng: .\fix-shared-resource-warnings.ps1

$ErrorActionPreference = "Stop"

Write-Host "🔧 Fixing SharedResourceWarning - Đảm bảo chỉ namespace.yaml tạo namespace/secret..." -ForegroundColor Cyan
Write-Host ""

# Bước 1: Apply lại tất cả Applications với namespace.enabled=false và secret.enabled=false
Write-Host "📋 Step 1: Applying Applications với namespace.enabled=false và secret.enabled=false..." -ForegroundColor Yellow
kubectl apply -f applications/ -n argocd
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Lỗi khi apply Applications" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Đã apply Applications" -ForegroundColor Green
Write-Host ""

# Bước 2: Hard refresh tất cả Applications
Write-Host "📋 Step 2: Hard refreshing Applications..." -ForegroundColor Yellow
$apps = @(
    "banking-demo-namespace",
    "banking-demo-postgres",
    "banking-demo-redis",
    "banking-demo-kong",
    "banking-demo-auth-service",
    "banking-demo-account-service",
    "banking-demo-transfer-service",
    "banking-demo-notification-service",
    "banking-demo-frontend",
    "banking-demo-ingress"
)

foreach ($app in $apps) {
    Write-Host "   Refreshing $app..." -ForegroundColor Gray
    $result = argocd app get $app --refresh 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   ⚠️  $app không tồn tại" -ForegroundColor Yellow
    }
}
Write-Host "✅ Đã refresh Applications" -ForegroundColor Green
Write-Host ""

# Bước 3: Sync lại
Write-Host "📋 Step 3: Syncing Applications..." -ForegroundColor Yellow
Write-Host "   Sync namespace (wave -1)..." -ForegroundColor Gray
argocd app sync banking-demo-namespace --timeout 300
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Sync namespace failed" -ForegroundColor Yellow
}
Start-Sleep -Seconds 5

Write-Host "   Sync postgres và redis (wave 0)..." -ForegroundColor Gray
argocd app sync banking-demo-postgres --timeout 300
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Sync postgres failed" -ForegroundColor Yellow
}
argocd app sync banking-demo-redis --timeout 300
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Sync redis failed" -ForegroundColor Yellow
}
Write-Host ""

# Bước 4: Kiểm tra SharedResourceWarning
Write-Host "📋 Step 4: Kiểm tra SharedResourceWarning..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Application conditions:" -ForegroundColor Gray
$conditions = kubectl get application banking-demo-namespace -n argocd -o yaml 2>&1 | Select-String -Pattern "conditions:" -Context 0,10
if ($conditions) {
    Write-Host $conditions
} else {
    Write-Host "⚠️  Không có conditions" -ForegroundColor Yellow
}
Write-Host ""

# Bước 5: Kiểm tra manifests
Write-Host "📋 Step 5: Kiểm tra manifests không có namespace/secret..." -ForegroundColor Yellow
Write-Host ""

Write-Host "Auth Service manifests (không nên có namespace/secret):" -ForegroundColor Gray
$authManifests = argocd app manifests banking-demo-auth-service 2>&1
if ($authManifests -match "kind: Namespace|kind: Secret") {
    Write-Host "   ❌ Vẫn có namespace/secret trong manifests!" -ForegroundColor Red
    Write-Host "   → Cần kiểm tra parameters" -ForegroundColor Yellow
} else {
    Write-Host "   ✅ Không có namespace/secret trong manifests" -ForegroundColor Green
}
Write-Host ""

Write-Host "Notification Service manifests (không nên có namespace/secret):" -ForegroundColor Gray
$notifManifests = argocd app manifests banking-demo-notification-service 2>&1
if ($notifManifests -match "kind: Namespace|kind: Secret") {
    Write-Host "   ❌ Vẫn có namespace/secret trong manifests!" -ForegroundColor Red
    Write-Host "   → Cần kiểm tra parameters" -ForegroundColor Yellow
} else {
    Write-Host "   ✅ Không có namespace/secret trong manifests" -ForegroundColor Green
}
Write-Host ""

Write-Host "✨ Fix hoàn tất!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Kiểm tra trong ArgoCD UI:" -ForegroundColor Cyan
Write-Host "   - Vào Application → Application conditions" -ForegroundColor Gray
Write-Host "   - Không còn SharedResourceWarning" -ForegroundColor Gray
Write-Host "   - Namespace chỉ được quản lý bởi banking-demo-namespace" -ForegroundColor Gray
Write-Host "   - Secret chỉ được quản lý bởi banking-demo-namespace" -ForegroundColor Gray
