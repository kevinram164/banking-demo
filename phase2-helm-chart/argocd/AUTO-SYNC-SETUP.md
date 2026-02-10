# Auto Sync — ArgoCD kiểm tra Git mỗi 5 phút

`application.yaml` đã bật **automated sync** với `ApplyOutOfSyncOnly=true`:
- ArgoCD tự động sync khi phát hiện thay đổi trong Git
- **Chỉ apply resources out-of-sync** → ví dụ đổi image tag auth-service thì chỉ rollout auth-service, không động postgres/redis

---

## Đặt tần suất kiểm tra Git = 5 phút

Mặc định ArgoCD poll repo mỗi **3 phút**. Để đổi thành **5 phút**:

```bash
# Patch argocd-cm
kubectl patch configmap argocd-cm -n argocd --type merge \
  -p '{"data":{"timeout.reconciliation":"300"}}'

# Restart repo-server để áp dụng
kubectl rollout restart deployment argocd-repo-server -n argocd
```

Giá trị `300` = 300 giây = 5 phút.

---

## Luồng hoạt động

1. Bạn commit + push thay đổi (vd: `charts/auth-service/values.yaml` — đổi `image.tag`)
2. ArgoCD (sau tối đa 5 phút) so sánh Git với cluster
3. Chỉ Deployment `auth-service` khác biệt → ArgoCD chỉ apply Deployment đó
4. Postgres, Redis, Kong, transfer-service… không bị chạm

---

## Cấu hình trong application.yaml

```yaml
syncPolicy:
  automated:
    selfHeal: true   # Tự động áp dụng thay đổi
    prune: false     # Không auto xóa resources
  syncOptions:
    - ApplyOutOfSyncOnly=true   # Chỉ sync resources thay đổi
```

---

## Bỏ auto sync (quay về manual)

Trong `application.yaml` đổi `syncPolicy.automated` thành `null` và sync thủ công qua UI/CLI khi cần.
