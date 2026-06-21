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
   - `ci-push` — push image (Jenkins credential `harbor-ci-push`)
   - `k8s-pull` — pull only (dockerconfigjson Secret `harbor-registry`)

## K8s pull secret (ns banking, platform)

```bash
kubectl create secret docker-registry harbor-registry \
  --docker-server=harbor-npd.co \
  --docker-username='robot$k8s-pull' \
  --docker-password='<TOKEN>' \
  -n banking

kubectl create secret docker-registry harbor-registry \
  --docker-server=harbor-npd.co \
  --docker-username='robot$k8s-pull' \
  --docker-password='<TOKEN>' \
  -n platform
```

Production: sync từ Vault qua ExternalSecret (`secret/platform/harbor`).

## Image naming (khớp values-images.yaml)

```text
harbor-npd.co/banking-demo/api-producer:<sha>
harbor-npd.co/banking-demo/auth-service:<sha>
...
```

## TLS

Nginx WSL2 terminate SSL; Traefik nhận HTTP (Mô hình SSL 1). Kaniko/Jenkins cần trust cert hoặc cấu hình insecure registry nếu lab dùng self-signed.
