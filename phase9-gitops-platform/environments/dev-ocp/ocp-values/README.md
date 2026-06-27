# OpenShift value overrides (dev-ocp)

Manifest dùng chung `gitops-platform/applications/` được tune cho **k3d** (`local-path`, Traefik Ingress, `*-npd.co`).

Trước khi sync platform/infra trên OCP, chỉnh các mục sau (tạo PR trên nhánh `dev-ocp` hoặc patch tạm):

| Thành phần | k3d (dev-k3d) | OpenShift (dev-ocp) |
|------------|---------------|---------------------|
| StorageClass | `local-path` | `gp3-csi` / `ocs-storagecluster-ceph-rbd` / `oc get sc` |
| Ingress | Traefik + Nginx ngoài | **Route** (`route.openshift.io/v1`) hoặc Ingress Controller OCP |
| Domain | `*-npd.co` + hosts file | `*.apps.<cluster-domain>` |
| ArgoCD NS | `argocd` | `openshift-gitops` (nếu dùng OpenShift GitOps Operator) |
| SCC | relaxed (k3d) | `anyuid` / `nonroot` — Jenkins, Harbor có thể cần điều chỉnh UID |

## Kiểm tra cluster

```bash
oc get sc
oc get ingresses.config cluster -o jsonpath='{.spec.domain}'; echo
oc get ns openshift-gitops argocd 2>/dev/null
```

## File gợi ý overlay (bổ sung dần)

- `harbor-route.yaml` — Route thay Ingress Harbor
- `jenkins-route.yaml` — Route Jenkins
- `infra-storage.yaml` — `storageClass` cho Postgres/Redis/RabbitMQ
