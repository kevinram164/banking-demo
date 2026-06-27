# Bootstrap — Cài platform lần đầu

Thứ tự triển khai :

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
| 4 | **AppProject** | `kubectl apply -f gitops-platform/project.yaml` | |
| 5 | **GitHub repo** | ArgoCD UI → Connect repo | Branch `dev-k3d` |

---

## Giai đoạn 2 — Platform (ArgoCD sync, chưa deploy app)

```bash
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/platform-app-of-apps.yaml -n argocd
```

| # | Thành phần | Sau sync | Ghi chú |
|---|------------|----------|---------|
| 1 | **Harbor** | UI, project, robot accounts | `ci-push`, `k8s-pull` |
| 2 | **Vault** | seed KV trong pod `vault-0` | `vault kv put secret/banking/*` — xem [vault/README.md](../vault/README.md) |
| 3 | **External Secrets** | ESO + `vault-token` + ClusterSecretStore | **Thứ tự:** seed Vault → `vault-token` → sync config (xem bên dưới) |
| 4 | **Jenkins** | Shared Library, credentials, webhook | Kaniko SA |

**Không** apply `banking-app-of-apps` ở giai đoạn này.

---

## Giai đoạn 3 — Infra (ArgoCD sync, chưa deploy app)

Chỉnh `storageClass: local-path` trên k3d trước khi sync.

> **Bitnami chart:** `infra-postgres` / `infra-redis` dùng `https://charts.bitnami.com/bitnami`.  
> Không dùng OCI Docker Hub (`oci://registry-1.docker.io/bitnamicharts`) — ArgoCD thường lỗi `401 Unauthorized`.

```bash
kubectl apply -f phase9-gitops-platform/environments/dev-k3d/argocd/applications/infra-app-of-apps.yaml -n argocd
```

| # | Thành phần | Ghi chú |
|---|------------|---------|
| 1 | **Postgres, Redis** | Wave 0 — app DB |
| 2 | **RabbitMQ** | Wave 1 — Phase 8 |
| 3 | **Kong HA** | Wave 2 — PreSync chờ PG Ready + tạo DB `kong` (`manifests/kong-prereq/`) |
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
| `secret/platform/jenkins` | `jenkins-platform-credentials` | `platform` |

### External Secrets — thứ tự triển khai (lab)

1. Pod `vault-0` Running → exec vào pod, `vault kv put` seed các path trên
2. Pod ESO Running (`external-secrets` namespace)
3. Tạo `vault-token` **trước** khi ClusterSecretStore reconcile:

```bash
kubectl create secret generic vault-token \
  --from-literal=token=root \
  -n external-secrets
```

4. Tạo namespace `banking`, `rabbit` nếu chưa có
5. Sync / apply `vault/external-secrets/`
6. Verify: `kubectl get externalsecret -A` → `SecretSynced`, `READY True`

Chi tiết CLI, force-sync, xử lý lỗi: [vault/README.md](../vault/README.md).

---

## Rollback

- ArgoCD UI → History → Rollback Application cụ thể.
- Image tag: revert commit trên `gitops/values-images.yaml`.
