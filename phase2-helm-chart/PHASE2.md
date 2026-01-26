# Phase 2: Helm Chart (Bootstrap)

Chuyển đổi manifest từ **phase1-docker-to-k8s** sang Helm theo phong cách **bootstrap**, với hai nguyên tắc chính:

1. **Mỗi service là một folder riêng (chỉ values)**: Trong `charts/<service>/` **chỉ có** `Chart.yaml` và `values.yaml`; không có thư mục `templates` trong từng service.
2. **Templates tập trung**: **Tất cả** file template (deployment, service, configmap, …) nằm **chung** trong `banking-demo/templates/`, dễ chỉnh sửa và thống nhất.
3. **Templates có tính thay đổi cao**: Port, probe, resources, env, paths… đều đi từ values, hạn chế hardcode.

## Cấu trúc

```
phase2-helm-chart/
└── banking-demo/                 # Chart umbrella
    ├── Chart.yaml                # Không dùng dependencies (chart độc lập)
    ├── values.yaml               # Cấu hình mặc định cho MỌI component (postgres, redis, kong, auth-service, …)
    ├── templates/                # TOÀN BỘ templates của mọi service (chung một chỗ)
    │   ├── _helpers.tpl
    │   ├── namespace.yaml
    │   ├── secret.yaml
    │   ├── ingress.yaml
    │   ├── postgres-statefulset.yaml
    │   ├── postgres-service.yaml
    │   ├── redis-statefulset.yaml
    │   ├── redis-service.yaml
    │   ├── kong-configmap.yaml
    │   ├── kong-deployment.yaml
    │   ├── kong-service.yaml
    │   ├── auth-service-deployment.yaml
    │   ├── auth-service-service.yaml
    │   ├── account-service-deployment.yaml
    │   ├── account-service-service.yaml
    │   ├── transfer-service-deployment.yaml
    │   ├── transfer-service-service.yaml
    │   ├── notification-service-deployment.yaml
    │   ├── notification-service-service.yaml
    │   ├── frontend-deployment.yaml
    │   ├── frontend-service.yaml
    │   └── NOTES.txt
    └── charts/                   # Mỗi service: CHỈ Chart.yaml + values.yaml (không có templates)
        ├── postgres/
        │   ├── Chart.yaml
        │   └── values.yaml
        ├── redis/
        │   ├── Chart.yaml
        │   └── values.yaml
        ├── kong/
        │   ├── Chart.yaml
        │   └── values.yaml
        ├── auth-service/
        │   ├── Chart.yaml
        │   └── values.yaml
        ├── account-service/
        ├── transfer-service/
        ├── notification-service/
        └── frontend/
```

- **Parent (`banking-demo`)**: `values.yaml` chứa đủ cấu hình mặc định cho mọi component (key trùng tên: `postgres:`, `redis:`, `kong:`, `auth-service:`, …). Override khi cài: `-f charts/<service>/values.yaml` hoặc `--set …`.
- **Folder từng service (`charts/<service>/`)**: **Chỉ** `Chart.yaml` và `values.yaml`; dùng để override giá trị khi deploy, không chứa template. Toàn bộ manifest được render từ `banking-demo/templates/`.

## Parameter hóa templates

Các giá trị không cố định trong template, mà lấy từ values:

- **Port / service**: `service.port`, `service.portName`, `proxyPort`, `adminPort` (Kong).
- **Probe**: `readinessProbe.enabled`, `path`, `port`, `initialDelaySeconds`, `periodSeconds`, `timeoutSeconds`; postgres/redis dùng `readinessProbe.command` hoặc `user` (pg_isready).
- **Resources**: `resources.requests` / `limits` trong values từng chart.
- **Secret**: `secretRef.name`, `secretRef.keys.*` (tên key trong Secret).
- **Storage**: `storage.storageClassName`, `size`, `volumeName`, `mountPath`.
- **Security**: `securityContext.pod`, `securityContext.container`.
- **Kong**: `backends` (danh sách service, url, routes, paths), `corsOrigins`, `corsMethods`, `corsHeaders`; `env` key-value.
- **Ingress**: `ingress.paths[]` với `path`, `pathType`, `serviceName`, `servicePort`.

Override từ parent hoặc sửa trực tiếp trong `charts/<service>/values.yaml` tùy nhu cầu.

## Thiết kế bootstrap

- **Một release, nhiều subchart**: Cài một lần `helm install banking-demo ./banking-demo -n banking` để deploy namespace, secret, postgres, redis, kong, 4 microservices, frontend và ingress.
- **Bật/tắt từng component**: Mỗi subchart có `enabled: true/false`. Override từ parent: `--set postgres.enabled=false` hoặc trong file values.
- **Global**: `global.namespace`, `global.secretName`, `global.corsOrigins`, `global.imagePullSecrets` (parent); subchart nhận override qua key trùng tên, ví dụ `auth-service.secretRef.name`.
- **Thứ tự deploy (Helm hooks)**: Namespace (-10) → Secret (-8) → Postgres, Redis (-5) → Kong và các service còn lại.

## Cài đặt

**Chuẩn bị:** StorageClass (ví dụ `nfs-client`), imagePullSecrets trong namespace (`dockerhub-registry`, `gitlab-registry`), hoặc override trong values từng chart.

```bash
cd phase2-helm-chart
helm install banking-demo ./banking-demo -n banking --create-namespace
```

**Xem manifest trước khi cài:**

```bash
helm template banking-demo ./banking-demo -n banking
```

**Chỉ deploy một phần (ví dụ chỉ infra):** Override `enabled` cho từng subchart (key trùng tên folder):

```yaml
# values-infra-only.yaml
auth-service:
  enabled: false
account-service:
  enabled: false
transfer-service:
  enabled: false
notification-service:
  enabled: false
frontend:
  enabled: false
kong:
  enabled: false
ingress:
  enabled: false
```

```bash
helm install banking-demo ./banking-demo -n banking -f values-infra-only.yaml
```

## Nâng cấp / override

- Nâng cấp chung: `helm upgrade banking-demo ./banking-demo -n banking`
- Tắt service: `--set notification-service.enabled=false`
- Đổi image một service: `--set auth-service.image.tag=v2` hoặc sửa `charts/auth-service/values.yaml`

## Mapping Phase 1 → Phase 2

| Phase 1 (manifest)   | Phase 2 (Helm) |
|----------------------|----------------|
| namespace.yaml       | templates/namespace.yaml |
| secret.yaml          | templates/secret.yaml |
| postgres             | templates/postgres-*.yaml ; values: values.yaml + charts/postgres/values.yaml |
| redis                | templates/redis-*.yaml ; values: values.yaml + charts/redis/values.yaml |
| kong-configmap + kong | templates/kong-*.yaml ; values: values.yaml + charts/kong/values.yaml |
| auth/account/transfer/notification-service | templates/*-service-*.yaml ; values: charts/<service>/values.yaml |
| frontend              | templates/frontend-*.yaml ; values: charts/frontend/values.yaml |
| ingress.yaml         | templates/ingress.yaml (paths parameterized) |

## Deploy với ArgoCD (GitOps)

Để deploy chart bằng ArgoCD (Git làm nguồn chân lý, sync tự động):

- Cấu hình Application/ApplicationSet trong **`argocd/`** (`application.yaml`, `application-set.yaml`).
- Values theo môi trường: **`banking-demo/values-production.yaml`**, **`banking-demo/values-staging.yaml`** (override khi dùng ArgoCD).
- Hướng dẫn chi tiết: **`argocd/ARGOCD.md`**.

## Lưu ý

- **Mật khẩu:** Dùng cho demo trong values; prod nên dùng `--set secret.postgresPassword=...` hoặc file values không commit / external secrets.
- **Ingress:** Host, class, paths cấu hình trong `values.ingress`; backend `serviceName`/`servicePort` trùng với `fullnameOverride` và port của từng subchart.
- **Sửa một service:** Chỉnh `charts/<service>/values.yaml` (override) hoặc parent `values.yaml`. Template của mọi service nằm trong `banking-demo/templates/`, không nằm trong folder từng service.
- **ArgoCD:** Deploy qua GitOps theo hướng dẫn trong `argocd/ARGOCD.md`.
