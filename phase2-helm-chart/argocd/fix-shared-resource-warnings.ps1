# Script: Fix SharedResourceWarning - Đảm bảo chỉ namespace.yaml tạo namespace/secret
# Cách dùng: .\fix-shared-resource-warnings.ps1

$ErrorActionPreference = "Stop"

Write-Host "🔧 Fixing SharedResourceWarning - Đảm bảo chỉ namespace.yaml tạo namespace/secret..." -ForegroundColor Cyan
Write-Host ""

# Bước 0: Kiểm tra và xóa Application banking-demo cũ (nếu có)
Write-Host "📋 Step 0: Kiểm tra Application banking-demo cũ (gây conflict)..." -ForegroundColor Yellow
$oldApp = kubectl get application banking-demo -n argocd 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ⚠️  Tìm thấy Application 'banking-demo' cũ - đang xóa..." -ForegroundColor Yellow
    kubectl delete application banking-demo -n argocd --cascade=false 2>&1 | Out-Null
    Write-Host "   ✅ Đã xóa Application banking-demo cũ" -ForegroundColor Green
} else {
    Write-Host "   ✅ Không có Application banking-demo cũ" -ForegroundColor Green
}
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

# Bước 2: Hard refresh tất cả Applications bằng kubectl patch (không cần ArgoCD CLI)
Write-Host "📋 Step 2: Hard refreshing Applications bằng kubectl..." -ForegroundColor Yellow
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
    $appExists = kubectl get application $app -n argocd 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   Refreshing $app..." -ForegroundColor Gray
        # Trigger refresh bằng cách patch annotation
        kubectl patch application $app -n argocd --type merge `
            -p '{\"metadata\":{\"annotations\":{\"argocd.argoproj.io/refresh\":\"hard\"}}}' 2>&1 | Out-Null
        # Xóa annotation để trigger refresh lại lần sau
        kubectl annotate application $app -n argocd argocd.argoproj.io/refresh- 2>&1 | Out-Null
    } else {
        Write-Host "   ⚠️  $app không tồn tại" -ForegroundColor Yellow
    }
}
Write-Host "✅ Đã refresh Applications" -ForegroundColor Green
Write-Host ""

# Đợi ArgoCD xử lý refresh
Write-Host "⏳ Đợi ArgoCD xử lý refresh (10 giây)..." -ForegroundColor Gray
Start-Sleep -Seconds 10
Write-Host ""

# Bước 3: Kiểm tra SharedResourceWarning
Write-Host "📋 Step 3: Kiểm tra SharedResourceWarning..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Application conditions cho banking-demo-namespace:" -ForegroundColor Gray
$conditions = kubectl get application banking-demo-namespace -n argocd -o jsonpath='{.status.conditions}' 2>&1
if ($conditions -match "SharedResourceWarning") {
    Write-Host "   ⚠️  Vẫn còn SharedResourceWarning!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   Chi tiết:" -ForegroundColor Gray
    kubectl get application banking-demo-namespace -n argocd -o yaml | Select-String -Pattern "SharedResourceWarning" -Context 0,5
    Write-Host ""
} else {
    Write-Host "   ✅ Không có SharedResourceWarning!" -ForegroundColor Green
}
Write-Host ""

# Bước 4: Kiểm tra parameters của các Applications
Write-Host "📋 Step 4: Kiểm tra parameters của các Applications..." -ForegroundColor Yellow
Write-Host ""
foreach ($app in $apps) {
    $appExists = kubectl get application $app -n argocd 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   $app:" -ForegroundColor Gray
        $namespaceEnabled = kubectl get application $app -n argocd -o jsonpath='{.spec.source.helm.parameters[?(@.name=="namespace.enabled")].value}' 2>&1
        $secretEnabled = kubectl get application $app -n argocd -o jsonpath='{.spec.source.helm.parameters[?(@.name=="secret.enabled")].value}' 2>&1
        if ($namespaceEnabled -ne "false" -or $secretEnabled -ne "false") {
            Write-Host "      ❌ namespace.enabled=$namespaceEnabled, secret.enabled=$secretEnabled" -ForegroundColor Red
        } else {
            Write-Host "      ✅ namespace.enabled=false, secret.enabled=false" -ForegroundColor Green
        }
    }
}
Write-Host ""

Write-Host "✨ Fix hoàn tất!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Kiểm tra trong ArgoCD UI:" -ForegroundColor Cyan
Write-Host "   - Vào Application → Application conditions" -ForegroundColor Gray
Write-Host "   - Không còn SharedResourceWarning" -ForegroundColor Gray
Write-Host "   - Namespace chỉ được quản lý bởi banking-demo-namespace" -ForegroundColor Gray
Write-Host "   - Secret chỉ được quản lý bởi banking-demo-namespace" -ForegroundColor Gray
Write-Host ""
Write-Host "💡 Nếu vẫn còn SharedResourceWarning sau 1-2 phút:" -ForegroundColor Yellow
Write-Host "   - Vào ArgoCD UI → Refresh từng Application thủ công" -ForegroundColor Gray
Write-Host "   - Hoặc sync lại từng Application trong UI" -ForegroundColor Gray
