# Script: Force deploy postgres và redis - Đảm bảo chúng được tạo
# Cách dùng: .\force-deploy-postgres-redis.ps1

$ErrorActionPreference = "Stop"

Write-Host "🚀 Force deploy postgres và redis..." -ForegroundColor Cyan
Write-Host ""

# Bước 1: Đảm bảo namespace tồn tại
Write-Host "📋 Step 1: Đảm bảo namespace 'banking' tồn tại..." -ForegroundColor Yellow
$namespaceExists = kubectl get namespace banking 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "   ⚠️  Namespace không tồn tại - đang deploy banking-demo-namespace..." -ForegroundColor Yellow
    
    # Apply namespace Application
    $appExists = kubectl get application banking-demo-namespace -n argocd 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   Application banking-demo-namespace tồn tại - đang sync..." -ForegroundColor Gray
        # Hard refresh
        kubectl patch application banking-demo-namespace -n argocd --type merge `
          -p '{\"metadata\":{\"annotations\":{\"argocd.argoproj.io/refresh\":\"hard\"}}}' 2>&1 | Out-Null
        kubectl annotate application banking-demo-namespace -n argocd argocd.argoproj.io/refresh- 2>&1 | Out-Null
        
        # Đợi namespace được tạo
        Write-Host "   Đợi namespace được tạo..." -ForegroundColor Gray
        for ($i = 1; $i -le 30; $i++) {
            $checkNs = kubectl get namespace banking 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "   ✅ Namespace đã được tạo!" -ForegroundColor Green
                break
            }
            Write-Host "   Đợi... ($i/30)" -ForegroundColor Gray
            Start-Sleep -Seconds 2
        }
        
        $finalCheck = kubectl get namespace banking 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "   ❌ Namespace vẫn chưa được tạo sau 60 giây!" -ForegroundColor Red
            Write-Host "   → Kiểm tra Application banking-demo-namespace trong ArgoCD UI" -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-Host "   ❌ Application banking-demo-namespace không tồn tại!" -ForegroundColor Red
        Write-Host "   → Apply namespace.yaml trước: kubectl apply -f applications/namespace.yaml -n argocd" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "   ✅ Namespace đã tồn tại" -ForegroundColor Green
}
Write-Host ""

# Bước 2: Đảm bảo secret tồn tại
Write-Host "📋 Step 2: Kiểm tra secret 'banking-db-secret'..." -ForegroundColor Yellow
$secretExists = kubectl get secret banking-db-secret -n banking 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "   ⚠️  Secret không tồn tại - đang đợi namespace Application sync..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    # Kiểm tra lại
    $secretCheck = kubectl get secret banking-db-secret -n banking 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   ⚠️  Secret vẫn chưa có - có thể namespace Application chưa sync xong" -ForegroundColor Yellow
        Write-Host "   → Sync banking-demo-namespace trong ArgoCD UI" -ForegroundColor Yellow
    } else {
        Write-Host "   ✅ Secret đã được tạo" -ForegroundColor Green
    }
} else {
    Write-Host "   ✅ Secret đã tồn tại" -ForegroundColor Green
}
Write-Host ""

# Bước 3: Hard refresh và sync postgres Application
Write-Host "📋 Step 3: Hard refresh và sync postgres Application..." -ForegroundColor Yellow
$postgresApp = kubectl get application banking-demo-postgres -n argocd 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   Hard refreshing banking-demo-postgres..." -ForegroundColor Gray
    kubectl patch application banking-demo-postgres -n argocd --type merge `
      -p '{\"metadata\":{\"annotations\":{\"argocd.argoproj.io/refresh\":\"hard\"}}}' 2>&1 | Out-Null
    kubectl annotate application banking-demo-postgres -n argocd argocd.argoproj.io/refresh- 2>&1 | Out-Null
    
    Write-Host "   Đợi ArgoCD refresh (5 giây)..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
    
    Write-Host "   Kiểm tra sync status..." -ForegroundColor Gray
    $syncStatus = kubectl get application banking-demo-postgres -n argocd -o jsonpath='{.status.sync.status}' 2>&1
    Write-Host "   Sync Status: $syncStatus" -ForegroundColor Gray
    
    if ($syncStatus -ne "Synced") {
        Write-Host "   ⚠️  Application chưa synced - cần sync thủ công trong ArgoCD UI" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ❌ Application banking-demo-postgres không tồn tại!" -ForegroundColor Red
    Write-Host "   → Apply: kubectl apply -f applications/postgres.yaml -n argocd" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Bước 4: Hard refresh và sync redis Application
Write-Host "📋 Step 4: Hard refresh và sync redis Application..." -ForegroundColor Yellow
$redisApp = kubectl get application banking-demo-redis -n argocd 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   Hard refreshing banking-demo-redis..." -ForegroundColor Gray
    kubectl patch application banking-demo-redis -n argocd --type merge `
      -p '{\"metadata\":{\"annotations\":{\"argocd.argoproj.io/refresh\":\"hard\"}}}' 2>&1 | Out-Null
    kubectl annotate application banking-demo-redis -n argocd argocd.argoproj.io/refresh- 2>&1 | Out-Null
    
    Write-Host "   Đợi ArgoCD refresh (5 giây)..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
    
    Write-Host "   Kiểm tra sync status..." -ForegroundColor Gray
    $syncStatus = kubectl get application banking-demo-redis -n argocd -o jsonpath='{.status.sync.status}' 2>&1
    Write-Host "   Sync Status: $syncStatus" -ForegroundColor Gray
    
    if ($syncStatus -ne "Synced") {
        Write-Host "   ⚠️  Application chưa synced - cần sync thủ công trong ArgoCD UI" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ❌ Application banking-demo-redis không tồn tại!" -ForegroundColor Red
    Write-Host "   → Apply: kubectl apply -f applications/redis.yaml -n argocd" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Bước 5: Kiểm tra resources được tạo
Write-Host "📋 Step 5: Kiểm tra resources được tạo..." -ForegroundColor Yellow
Write-Host ""

Write-Host "Đợi resources được tạo (30 giây)..." -ForegroundColor Gray
Start-Sleep -Seconds 30

Write-Host "Pods:" -ForegroundColor Cyan
kubectl get pods -n banking -l app.kubernetes.io/name=postgres 2>&1 | Out-String
kubectl get pods -n banking -l app.kubernetes.io/name=redis 2>&1 | Out-String
Write-Host ""

Write-Host "StatefulSets:" -ForegroundColor Cyan
kubectl get statefulsets -n banking 2>&1 | Select-String -Pattern "postgres|redis" | Out-String
Write-Host ""

Write-Host "Services:" -ForegroundColor Cyan
kubectl get services -n banking 2>&1 | Select-String -Pattern "postgres|redis" | Out-String
Write-Host ""

# Bước 6: Kiểm tra ArgoCD Application resources
Write-Host "📋 Step 6: Kiểm tra ArgoCD Application resources..." -ForegroundColor Yellow
Write-Host ""

$apps = @("banking-demo-postgres", "banking-demo-redis")
foreach ($app in $apps) {
    Write-Host "$app resources trong ArgoCD:" -ForegroundColor Cyan
    $resources = kubectl get application $app -n argocd -o jsonpath='{.status.resources[*].kind}' 2>&1
    if ($resources -and $resources -ne "") {
        Write-Host "   $resources" -ForegroundColor Gray
        
        # Đếm số resources
        $resourceCount = ($resources -split ' ').Count
        Write-Host "   Tổng số resources: $resourceCount" -ForegroundColor Gray
        
        if ($resourceCount -eq 0) {
            Write-Host "   ⚠️  Application không có resources nào!" -ForegroundColor Yellow
            Write-Host "   → Kiểm tra Helm values và templates" -ForegroundColor Yellow
        }
    } else {
        Write-Host "   ⚠️  Không có resources được liệt kê!" -ForegroundColor Yellow
    }
    Write-Host ""
}

Write-Host "✨ Force deploy hoàn tất!" -ForegroundColor Green
Write-Host ""
Write-Host "📝 Nếu vẫn không có resources:" -ForegroundColor Cyan
Write-Host "   1. Vào ArgoCD UI → Application → Sync" -ForegroundColor Gray
Write-Host "   2. Kiểm tra Application conditions" -ForegroundColor Gray
Write-Host "   3. Xem rendered manifests trong ArgoCD UI" -ForegroundColor Gray
Write-Host "   4. Chạy script debug: .\check-postgres-redis-resources.ps1" -ForegroundColor Gray
