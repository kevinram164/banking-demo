# Harbor — Phase 9

Registry nội bộ cho CI (Jenkins Kaniko) và CD (ArgoCD pull image).

## Lab k3d

| | |
|--|--|
| UI | **https://harbor-npd.co** |
| Ingress | Traefik trong cluster + Nginx LB WSL2 (`k3d/nginx-harbor-npd.co.conf`) |
| StorageClass | `local-path` (không dùng `nfs-client` trên k3d) |

## Sau khi sync `platform-harbor`

1. Đăng nhập UI — đổi admin password ngay.
2. Tạo project **`banking-demo`** (public hoặc private).
3. Tạo **Robot Accounts**:
   - `ci-push` — push image → Vault `secret/platform/harbor` (pipeline Kaniko)
   - `k8s-pull` — pull only → Vault `secret/platform/harbor-pull` → ESO `harbor-pull-creds`

## Pull secret (Vault + ESO, không tạo tay)

Seed trong pod `vault-0` (xem [vault/README.md](../vault/README.md) mục 5.5):

```bash
vault kv put secret/platform/harbor-pull \
  registry='harbor-platform.apps.ocp01.npd.co' \
  username='robot$banking-demo+k8s-pull' \
  password='<TOKEN>'
```

ESO (`harbor-pull-external-secret.yaml`) tạo secret `harbor-pull-creds` trong ns `banking` và `platform`. Helm banking đọc qua `values-images.yaml` → `imagePullSecrets`.

```bash
kubectl get externalsecret harbor-pull-creds -n banking
kubectl get secret harbor-pull-creds -n banking
```

## Image naming (khớp values-images.yaml)

```text
harbor-platform.apps.ocp01.npd.co/banking-demo/api-producer:<sha>
harbor-platform.apps.ocp01.npd.co/banking-demo/auth-service:<sha>
...
```

## TLS

**k3d:** Nginx WSL2 terminate SSL; kubelet cần `k3d/registries.yaml` mirror HTTP nội bộ — xem K3D-DEPLOY-GUIDE.

**OCP:** Kubelet pull qua Route TLS; Kaniko/Jenkins dùng `kanikoSkipTlsVerify: true` (lab).
