# PowerShell Script: apply project và tất cả Applications cùng lúc
# Cách dùng: .\deploy-all.ps1

Write-Host "🚀 Deploying banking-demo với ArgoCD..." -ForegroundColor Cyan
Write-Host ""

# Bước 1: Apply Project
Write-Host "📦 Step 1: Applying Project..." -ForegroundColor Yellow
kubectl apply -f project.yaml -n argocd
Write-Host "✅ Project applied" -ForegroundColor Green
Write-Host ""

# Bước 2: Apply tất cả Applications
Write-Host "📦 Step 2: Applying all Applications..." -ForegroundColor Yellow
kubectl apply -f applications/ -n argocd
Write-Host "✅ All Applications applied" -ForegroundColor Green
Write-Host ""

# Bước 3: Hiển thị danh sách Applications
Write-Host "📋 Step 3: Listing Applications..." -ForegroundColor Yellow
kubectl get applications -n argocd -l app.kubernetes.io/name=banking-demo
Write-Host ""

Write-Host "✨ Done! Applications đã được tạo." -ForegroundColor Green
Write-Host ""
Write-Host "📝 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Vào ArgoCD UI để sync từng Application"
Write-Host "   2. Hoặc dùng CLI: argocd app sync -l app.kubernetes.io/name=banking-demo"
Write-Host ""
Write-Host "   Thứ tự sync đề xuất:"
Write-Host "   - banking-demo-namespace (namespace & secret)"
Write-Host "   - banking-demo-postgres, banking-demo-redis (infrastructure)"
Write-Host "   - banking-demo-kong (API Gateway)"
Write-Host "   - banking-demo-auth-service, banking-demo-account-service, ... (microservices)"
Write-Host "   - banking-demo-frontend, banking-demo-ingress (frontend & ingress)"
