# OpenShift (dev-ocp) — Phase 9 Deploy Guide

Triển khai Phase 9 GitOps trên **OpenShift** — nhánh Git **`dev-ocp`**, fork từ `dev-k3d`.

| | dev-k3d | dev-ocp |
|---|---------|---------|
| Cluster | k3d + WSL + Nginx | OpenShift (OCP) |
| Git branch | `dev-k3d` | **`dev-ocp`** |
| ArgoCD | Cài thủ công, NS `argocd` | **OpenShift GitOps**, NS `openshift-gitops` |
| Expose UI | Ingress Traefik + Nginx `*-npd.co` | **Route** `*.apps.<cluster-domain>` |
| Storage | `local-path` | `gp3-csi` / ODF / `oc get sc` |
| Env manifests | `environments/dev-k3d/` | **`environments/dev-ocp/`** |

Chi tiết k3d lab: [K3D-DEPLOY-GUIDE.md](./K3D-DEPLOY-GUIDE.md)

---

## 0. Chuẩn bị

```bash
oc login --token=... --server=https://api.<cluster>:6443
oc get nodes
oc get sc
export CLUSTER_DOMAIN=$(oc get ingresses.config cluster -o jsonpath='{.spec.domain}')
echo "Cluster domain: $CLUSTER_DOMAIN"
```

Cài **OpenShift GitOps Operator** (nếu chưa có):

```bash
oc get csv -n openshift-gitops
# Route ArgoCD: openshift-gitops-server-openshift-gitops.apps.$CLUSTER_DOMAIN
```

Kết nối repo GitHub trong ArgoCD UI (branch `dev-ocp`).

---

## 1. Clone nhánh dev-ocp

```bash
git clone https://github.com/kevinram164/banking-demo.git
cd banking-demo
git checkout dev-ocp
```

---

## 2. Tùy chỉnh domain (một lần)

Thay placeholder `CLUSTER_DOMAIN` trong manifest:

```bash
chmod +x phase9-gitops-platform/environments/dev-ocp/scripts/customize-cluster-domain.sh
./phase9-gitops-platform/environments/dev-ocp/scripts/customize-cluster-domain.sh "$CLUSTER_DOMAIN"
git diff phase9-gitops-platform/environments/dev-ocp
git commit -am "chore(ocp): set cluster domain $CLUSTER_DOMAIN"
git push origin dev-ocp
```

Hoặc sửa tay `environments/dev-ocp/gitops-env.yaml`.

---

## 3. Thứ tự deploy (giống k3d)

```
Platform (Harbor, Vault, ESO, Jenkins)
  → Observability (tùy chọn)
  → Infra (Postgres, Redis, Rabbit, Kong)
  → CI/CD (Jenkins → Harbor → Git)
  → Banking app (cuối cùng)
```

**Lưu ý OCP:** Manifest platform trong `gitops-platform/applications/platform/` vẫn dùng values k3d (`local-path`, Traefik). Trước sync platform, xem [environments/dev-ocp/ocp-values/README.md](./environments/dev-ocp/ocp-values/README.md) và chỉnh StorageClass / Route.

---

## 4. Bootstrap ArgoCD (dev-ocp)

```bash
# Mặc định: openshift-gitops
export ARGOCD_NS=openshift-gitops
./phase9-gitops-platform/environments/dev-ocp/apply-argocd.sh
```

Apply từng giai đoạn (khuyến nghị):

```bash
ARGOCD_NS=openshift-gitops

oc apply -f phase9-gitops-platform/environments/dev-ocp/appproject.yaml -n $ARGOCD_NS

oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/platform-app-of-apps.yaml -n $ARGOCD_NS
# ArgoCD UI → Sync platform-app-of-apps-dev-ocp

# Sau platform OK + Vault seed + Jenkins credentials:
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/observability-app-of-apps.yaml -n $ARGOCD_NS

oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/infra-app-of-apps.yaml -n $ARGOCD_NS

# Sau CI/CD pipeline green:
oc apply -f phase9-gitops-platform/environments/dev-ocp/argocd/applications/banking-app-of-apps.yaml -n $ARGOCD_NS
```

---

## 5. Khác biệt cần xử lý trên OCP

### StorageClass

```bash
oc get sc
# Sửa trong values Postgres/Redis/Harbor/Jenkins: storageClass → SC mặc định cluster
```

### Route thay Ingress

Harbor, Jenkins, Vault, Banking — expose bằng **Route** thay vì Traefik + Nginx. Ví dụ:

```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: harbor
  namespace: platform
spec:
  host: harbor-banking.apps.<cluster-domain>
  to:
    kind: Service
    name: harbor-portal
  port:
    targetPort: 8080
  tls:
    termination: edge
```

### SCC (Security Context Constraints)

Pod chạy UID cố định (Jenkins 1000, Harbor) có thể cần:

```bash
oc adm policy add-scc-to-user anyuid -z default -n platform
# hoặc tạo SA + SCC riêng cho Jenkins/Harbor
```

### Jenkins CI

- Multibranch job filter: **`dev-ocp`**
- `Jenkinsfile` trên nhánh `dev-ocp` trỏ `harbor-banking.apps.<domain>`
- Credentials: `harbor-ci-push`, `github-gitops-push` (push vào nhánh `dev-ocp`)

---

## 6. Vault + ESO

Giống k3d — dùng Vault CLI, xem mục Vault trong [K3D-DEPLOY-GUIDE.md](./K3D-DEPLOY-GUIDE.md#43-vault--external-secrets).

```bash
export VAULT_ADDR="https://vault-banking.apps.$CLUSTER_DOMAIN"
export VAULT_TOKEN=root
export VAULT_SKIP_VERIFY=true
# vault kv put secret/banking/db ...
```

---

## 7. Checklist

- [ ] `oc login` OK
- [ ] OpenShift GitOps Operator Running
- [ ] Repo `dev-ocp` connected trong ArgoCD
- [ ] `CLUSTER_DOMAIN` đã thay trong manifest
- [ ] StorageClass đã chỉnh cho infra/platform
- [ ] Route Harbor / Jenkins / ArgoCD truy cập được
- [ ] Vault seeded + ESO sync
- [ ] Jenkins pipeline green trên `dev-ocp`
- [ ] `banking-app-of-apps-dev-ocp` sync (cuối cùng)

---

## Cấu trúc nhánh dev-ocp

```text
phase9-gitops-platform/
├── OCP-DEPLOY-GUIDE.md          # File này
├── gitops-platform/             # Application manifests dùng chung (Helm sources)
└── environments/dev-ocp/
    ├── README.md
    ├── gitops-env.yaml          # Domain, Harbor host, branch
    ├── appproject.yaml          # AppProject cho openshift-gitops
    ├── apply-argocd.sh
    ├── ocp-values/              # Ghi chú overlay OCP
    ├── scripts/
    └── argocd/applications/     # App of Apps dev-ocp
```
