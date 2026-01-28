#!/bin/bash
# Script: apply project và tất cả Applications cùng lúc
# Cách dùng: ./deploy-all.sh

set -e

echo "🚀 Deploying banking-demo với ArgoCD..."
echo ""

# Bước 1: Apply Project
echo "📦 Step 1: Applying Project..."
kubectl apply -f project.yaml -n argocd
echo "✅ Project applied"
echo ""

# Bước 2: Apply tất cả Applications
echo "📦 Step 2: Applying all Applications..."
kubectl apply -f applications/ -n argocd
echo "✅ All Applications applied"
echo ""

# Bước 3: Hiển thị danh sách Applications
echo "📋 Step 3: Listing Applications..."
kubectl get applications -n argocd -l app.kubernetes.io/name=banking-demo
echo ""

echo "✨ Done! Applications đã được tạo."
echo ""
echo "📝 Next steps:"
echo "   1. Vào ArgoCD UI để sync từng Application"
echo "   2. Hoặc dùng CLI: argocd app sync -l app.kubernetes.io/name=banking-demo"
echo ""
echo "   Thứ tự sync đề xuất:"
echo "   - banking-demo-namespace (namespace & secret)"
echo "   - banking-demo-postgres, banking-demo-redis (infrastructure)"
echo "   - banking-demo-kong (API Gateway)"
echo "   - banking-demo-auth-service, banking-demo-account-service, ... (microservices)"
echo "   - banking-demo-frontend, banking-demo-ingress (frontend & ingress)"
