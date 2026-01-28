# Tại sao các services khác deploy được nhưng postgres/redis không?

## Giải thích

### ArgoCD có 2 cách quản lý Git repos:

1. **Global Repository (Settings → Repositories)**: Repo được register toàn cục, có thể dùng cho nhiều Applications
2. **Inline Repository (trong Application spec)**: Mỗi Application tự khai báo `repoURL` trong spec

### Tại sao các services khác deploy được?

Có thể các services khác:
- **Đã được deploy từ trước** khi repo còn accessible
- **Đang chạy từ cache cũ** của ArgoCD
- **Được deploy bằng cách khác** (không qua ArgoCD)

### Tại sao postgres/redis không deploy được?

Có thể do:
1. **ArgoCD không thể fetch repo mới** để render Helm chart
2. **Helm chart của postgres/redis có vấn đề** khi ArgoCD render
3. **Values không được merge đúng** giữa valueFiles và parameters

## Cách kiểm tra

### 1. Kiểm tra các services khác có thực sự được quản lý bởi ArgoCD không:

```bash
# Kiểm tra pods đang chạy
kubectl get pods -n banking

# Kiểm tra xem pods này được tạo bởi ArgoCD hay không
kubectl get pods -n banking -o yaml | grep -i "argocd\|managed-by"
```

### 2. So sánh Applications:

```bash
chmod +x compare-applications.sh
./compare-applications.sh
```

### 3. Kiểm tra ArgoCD có thể access repo không:

```bash
# Kiểm tra Application conditions
kubectl get application banking-demo-postgres -n argocd -o yaml | grep -A 10 "conditions:"

# Kiểm tra ArgoCD controller logs
ARGOCD_POD=$(kubectl get pods -n argocd -l app.kubernetes.io/name=argocd-application-controller -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n argocd $ARGOCD_POD --tail=100 | grep -i "postgres\|redis\|error\|repo"
```

## Giải pháp

### Cách 1: Connect repo trong ArgoCD UI (Khuyến nghị)

1. Vào ArgoCD UI → **Settings** → **Repositories**
2. Click **+ CONNECT REPO**
3. Điền thông tin:
   - **Type**: Git
   - **Project**: banking-demo (hoặc để trống)
   - **Repository URL**: `https://github.com/kevinram164/banking-demo.git`
   - **Username/Password**: (nếu repo private)
4. Click **CONNECT**

Sau đó hard refresh và sync lại Applications.

### Cách 2: Kiểm tra AppProject có allow repo không

```bash
# Kiểm tra AppProject
kubectl get appproject banking-demo -n argocd -o yaml

# Nếu repo URL không có trong sourceRepos, thêm vào:
kubectl patch appproject banking-demo -n argocd --type merge \
  -p '{"spec":{"sourceRepos":["https://github.com/kevinram164/banking-demo.git"]}}'
```

### Cách 3: Kiểm tra xem các services khác có thực sự được deploy bởi ArgoCD không

Có thể các services đang chạy từ:
- Deployment cũ (trước khi dùng ArgoCD)
- Manual deployment
- Application khác

Nếu vậy, cần xóa và deploy lại qua ArgoCD.

## Kết luận

Nếu ArgoCD không liên kết với repo:
- **Các services đã deploy từ trước** sẽ tiếp tục chạy (vì pods đã được tạo)
- **Services mới (postgres/redis)** sẽ không deploy được vì ArgoCD không thể fetch repo để render Helm chart

**Giải pháp**: Connect repo trong ArgoCD UI hoặc đảm bảo AppProject có repo trong sourceRepos.
