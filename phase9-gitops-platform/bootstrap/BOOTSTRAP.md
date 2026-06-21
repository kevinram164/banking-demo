# Bootstrap — Cài platform lần đầu

Một số thành phần **không thể** tự cài từ chính nó (gà/trứng). Thứ tự đúng:

1. **Platform + Infra trước**
2. **Tích hợp CI/CD** (Jenkins → Harbor → Git)
3. **ArgoCD deploy banking app sau cùng**

Chi tiết k3d lab: [K3D-DEPLOY-GUIDE.md](../K3D-DEPLOY-GUIDE.md)

---

## Giai đoạn 1 — Cluster + ArgoCD bootstrap

| # | Thành phần | Cách cài | Ghi chú |
|---|------------|----------|---------|
| 1 | **k3d cluster** | `k3d/cluster-create.sh` | Port map 9080/9443 |
| 2 | **ArgoCD** | `kubectl apply -n argocd -f install.yaml` | Bootstrap thủ công |
| 3 | **Nginx + Ingress** | `k3d/nginx-*.conf`, `argocd-ingress.yaml` | SSL terminate ngoài |
| 4 | **AppProject** | `kubectl apply -f argocd/project.yaml` | |
| 5 | **GitHub repo** | ArgoCD UI → Connect repo | Branch `dev-k3d` |

---

## Giai đoạn 2 — Platform (ArgoCD sync, chưa deploy app)

```bash
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/platform-app-of-apps.yaml -n argocd
```

| # | Thành phần | Sau sync | Ghi chú |
|---|------------|----------|---------|
| 1 | **Harbor** | UI, project, robot accounts | `ci-push`, `k8s-pull` |
| 2 | **Vault** | init/unseal, seed KV | `secret/banking/*` |
| 3 | **External Secrets** | ClusterSecretStore + ExternalSecret | Xem `vault/external-secrets/` |
| 4 | **Jenkins** | Shared Library, credentials, webhook | Kaniko SA |

**Không** apply `banking-app-of-apps` ở giai đoạn này.

---

## Giai đoạn 3 — Infra (ArgoCD sync, chưa deploy app)

Chỉnh `storageClass: local-path` trên k3d trước khi sync.

```bash
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/infra-app-of-apps.yaml -n argocd
```

| # | Thành phần | Ghi chú |
|---|------------|---------|
| 1 | **Postgres, Redis** | Wave 0 — app DB |
| 2 | **RabbitMQ** | Wave 1 — Phase 8 |
| 3 | **Kong HA** | Wave 1 — chưa import routes |
| 4 | **Secrets** | ESO hoặc `kubectl create secret` thủ công |

---

## Giai đoạn 4 — CI/CD hoàn chỉnh

| # | Bước | Công cụ |
|---|------|---------|
| 1 | Push code `phase8-application-v3/**` | GitHub `dev-k3d` |
| 2 | Build + push image | Jenkins + Kaniko → Harbor |
| 3 | Commit tag | Jenkins → `gitops/values-images.yaml` |
| 4 | Verify pipeline green | Jenkins UI + Harbor UI |

**Checkpoint:** Harbor có image; Git có commit tag mới.

---

## Giai đoạn 5 — ArgoCD deploy banking app

```bash
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/banking-app-of-apps.yaml -n argocd
# ArgoCD UI → Sync banking-app-of-apps-dev-k3d
```

Sau banking pods Running:

```bash
kubectl apply -f phase8-application-v3/kong-ha/kong-import-job.yaml
```

(Tùy chọn) Root quản lý tập trung:

```bash
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/app-of-apps.yaml -n argocd
```

---

## Secret cần trong Vault (thay kubectl thủ công)

| Vault path | K8s Secret | Namespace |
|------------|------------|-----------|
| `secret/banking/db` | `banking-db-secret` | `banking` |
| `secret/banking/rabbitmq` | `rabbitmq-connection-secret` | `banking` |
| `secret/rabbitmq/admin` | `rabbitmq-secret` | `rabbit` |
| `secret/platform/harbor` | `harbor-registry` (dockerconfigjson) | `banking`, `platform` |
| `secret/platform/jenkins` | GitHub webhook / git push credential | `platform` |

---

## Rollback

- ArgoCD UI → History → Rollback Application cụ thể.
- Image tag: revert commit trên `gitops/values-images.yaml`.
