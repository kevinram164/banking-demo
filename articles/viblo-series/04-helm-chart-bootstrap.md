# Banking Demo: Helm Chart Bootstrap — Gom manifest thành một chart

> **Series**: Banking Demo — Full DevOps với Microservices  
> **Bài 4/11**: Chuyển từ manifest thuần sang Helm theo phong cách bootstrap

---

## Mở đầu

Ở **bài 3**, chúng ta đã deploy Banking Demo lên Kubernetes bằng manifest YAML thuần trong `phase1-docker-to-k8s/`. Mỗi lần đổi port, image, env hay thêm service là phải sửa tay nhiều file, dễ sót và khó quản lý theo môi trường (dev/staging/prod).

**Phase 2** chuyển toàn bộ sang **Helm chart**: cấu hình nằm trong **values**, manifest được **render từ template**. Một lệnh `helm install` hoặc `helm upgrade` deploy/update cả stack; đổi config chỉ cần sửa values hoặc truyền `-f` / `--set`.

Bài này giải thích **Helm chart bootstrap** của Banking Demo: cấu trúc umbrella chart, templates tập trung, values theo từng service, và cách dùng trong thực tế.

---

## Tại sao dùng Helm sau Phase 1?

| Vấn đề Phase 1 (manifest thuần) | Cách Helm xử lý |
|---------------------------------|-----------------|
| Đổi image/port/env phải sửa nhiều file | Một chỗ: values (hoặc `--set`) |
| Dev/staging/prod dùng chung manifest, khác nhau phải copy/sửa | Mỗi env một file values, merge khi install |
| Bật/tắt component (vd tắt notification-service) phải xóa hoặc comment manifest | `enabled: true/false` trong values |
| Khó tái sử dụng (tên release, namespace lặp lại) | Parameter hóa qua `.Values.global.namespace`, helpers |
| Rollback thủ công | `helm rollback <release> <revision>` |

Helm không thay đổi kiến trúc K8s (vẫn Deployment, StatefulSet, Service, Ingress) — nó chỉ **sinh ra** đúng manifest đó từ template + values, nên bạn vẫn hiểu rõ từng resource.

---

## Phong cách “Bootstrap” là gì?

Trong repo Banking Demo, Phase 2 chọn **bootstrap style** với ba nguyên tắc:

1. **Templates tập trung**: Mọi file template (Deployment, Service, ConfigMap, Ingress, …) nằm **chung** trong `banking-demo/templates/`. Không rải template theo từng service.
2. **Mỗi service một folder, chỉ values**: Trong `charts/<service>/` **chỉ có** `Chart.yaml` và `values.yaml`. Không có thư mục `templates` trong từng service. Cấu hình từng component nằm trong values, merge khi cài (vd `-f charts/auth-service/values.yaml`).
3. **Parameter hóa cao**: Port, probe, resources, secretRef, storage, securityContext… đều lấy từ values, hạn chế hardcode trong template.

Lợi ích: một chart “umbrella” deploy cả ứng dụng; sửa template một lần áp dụng cho mọi service; override theo service hoặc theo môi trường bằng file values.

---

## Cấu trúc chart Banking Demo

```
phase2-helm-chart/
└── banking-demo/                    # Chart umbrella
    ├── Chart.yaml                   # Metadata (tên, version, mô tả)
    ├── values.yaml                  # Mặc định (có thể rất ít, thực tế dùng charts/*)
    ├── templates/                   # TOÀN BỘ template — chung một chỗ
    │   ├── _helpers.tpl              # Hàm dùng chung (fullname, labels, selectorLabels)
    │   ├── namespace.yaml
    │   ├── secret.yaml
    │   ├── postgres-statefulset.yaml
    │   ├── postgres-service.yaml
    │   ├── redis-statefulset.yaml
    │   ├── redis-service.yaml
    │   ├── kong-configmap.yaml
    │   ├── kong-deployment.yaml
    │   ├── kong-service.yaml
    │   ├── auth-service-deployment.yaml
    │   ├── auth-service-service.yaml
    │   ├── ... (account, transfer, notification, frontend)
    │   ├── ingress.yaml
    │   └── NOTES.txt
    └── charts/                       # Mỗi service: CHỈ Chart.yaml + values.yaml
        ├── common/                   # Global: namespace, secret, ingress
        │   ├── Chart.yaml
        │   └── values.yaml
        ├── postgres/
        ├── redis/
        ├── kong/
        ├── auth-service/
        ├── account-service/
        ├── transfer-service/
        ├── notification-service/
        └── frontend/
```

- **Parent (`banking-demo`)**: `values.yaml` có thể chỉ chứa comment hoặc mặc định tối thiểu; thực tế ArgoCD/CI merge nhiều file từ `charts/common/values.yaml` và `charts/<service>/values.yaml`.
- **Template** luôn đọc qua `.Values`: ví dụ `.Values.postgres`, `.Values.ingress`, `index .Values "auth-service"` (vì key có dấu gạch ngang).

---

## Global và cấu hình chung (common)

Cấu hình dùng chung cho toàn chart nằm trong `charts/common/values.yaml`:

```yaml
global:
  namespace: banking
  secretName: banking-db-secret
  corsOrigins: "http://localhost:3000"
  imagePullSecrets:
    dockerhub: dockerhub-registry
    gitlab: gitlab-registry

namespace:
  enabled: true

secret:
  enabled: true
  postgresUser: banking
  postgresPassword: bankingpass
  postgresDb: banking
  databaseUrl: "postgresql://banking:bankingpass@postgres:5432/banking"
  redisUrl: "redis://redis:6379/0"

ingress:
  enabled: true
  className: haproxy
  host: npd-banking.co
  name: banking-ingress
  paths:
    - path: /
      pathType: Prefix
      serviceName: frontend
      servicePort: 80
    - path: /api
      pathType: Prefix
      serviceName: kong
      servicePort: 8000
    - path: /ws
      pathType: Prefix
      serviceName: kong
      servicePort: 8000
```

Template dùng: `{{ .Values.global.namespace }}`, `{{ include "banking-demo.secretName" . }}`, `{{ .Values.ingress.paths }}`… Nhờ đó đổi namespace, secret name hay ingress host chỉ ở một chỗ.

---

## Values theo từng service (ví dụ auth-service)

Mỗi service có một “slice” values trùng tên với key trong template. Ví dụ `charts/auth-service/values.yaml`:

```yaml
auth-service:
  fullnameOverride: auth-service
  enabled: true
  image:
    repository: registry.gitlab.com/.../auth-service
    tag: v1
    pullPolicy: Always
  replicas: 1
  service:
    port: 8001
    portName: http
  secretRef:
    name: banking-db-secret
    keys:
      databaseUrl: DATABASE_URL
      redisUrl: REDIS_URL
  corsOrigins: "http://localhost:3000"
  readinessProbe:
    enabled: true
    path: /health
    port: 8001
    initialDelaySeconds: 10
    periodSeconds: 15
  resources:
    requests: { memory: "128Mi", cpu: "100m" }
    limits:   { memory: "256Mi", cpu: "300m" }
  securityContext:
    pod: { ... }
    container: { ... }
```

Template auth-service đọc qua `$svc := index .Values "auth-service"` rồi dùng `$svc.enabled`, `$svc.image.repository`, `$svc.service.port`… Port, probe, resources, secretRef đều parameter hóa — không hardcode trong template.

---

## Helpers và bật/tắt component

Trong `_helpers.tpl` có các define dùng chung:

- **fullname**: `banking-demo.auth-service.fullname` → dùng làm tên Deployment/Service (có thể override bằng `fullnameOverride`).
- **labels / selectorLabels**: thống nhất label cho chart, release, component.

Template mỗi component thường bắt đầu bằng điều kiện **enabled**:

```yaml
{{- if .Values.postgres.enabled }}
apiVersion: apps/v1
kind: StatefulSet
...
{{- end }}
```

Hoặc với auth-service (key có dấu gạch):

```yaml
{{- $svc := index .Values "auth-service" }}
{{- if $svc.enabled }}
...
{{- end }}
```

Nhờ đó bạn có thể tắt postgres, redis, kong, từng microservice hay ingress bằng cách set `enabled: false` trong values (hoặc `--set postgres.enabled=false`) mà không cần xóa file template.

---

## Parameter hóa chính trong template

| Nội dung | Lấy từ values | Ví dụ |
|----------|----------------|--------|
| Namespace | `global.namespace` | `{{ .Values.global.namespace }}` |
| Secret name | `global.secretName` hoặc helper | `{{ include "banking-demo.secretName" . }}` |
| Image | `image.repository`, `image.tag`, `image.pullPolicy` | Mỗi Deployment |
| Port | `service.port`, `service.portName` | Service + containerPort |
| Probe | `readinessProbe.enabled`, `path`, `port`, `initialDelaySeconds`, … | Postgres: `readinessProbe.user` (pg_isready) |
| Resources | `resources.requests` / `limits` | toYaml trong template |
| Secret ref | `secretRef.name`, `secretRef.keys.*` | env valueFrom secretKeyRef |
| Storage (Postgres/Redis) | `storage.storageClassName`, `size`, `volumeName`, `mountPath` | volumeClaimTemplates + volumeMounts |
| Ingress | `ingress.paths[]` với `path`, `pathType`, `serviceName`, `servicePort` | range trong ingress.yaml |
| Security | `securityContext.pod`, `securityContext.container` | toYaml |

Nhờ vậy một bộ template phục vụ nhiều môi trường; chỉ cần khác file values (hoặc override khi install).

---

## Cài đặt và nâng cấp

### Xem manifest trước khi cài

```bash
cd phase2-helm-chart
helm template banking-demo ./banking-demo -n banking \
  -f banking-demo/charts/common/values.yaml \
  -f banking-demo/charts/postgres/values.yaml \
  -f banking-demo/charts/redis/values.yaml \
  -f banking-demo/charts/kong/values.yaml \
  -f banking-demo/charts/auth-service/values.yaml \
  # ... các service còn lại + frontend
```

Trong repo, ArgoCD thường khai báo sẵn danh sách valueFiles (vd `charts/common/values.yaml` + từng `charts/<service>/values.yaml`), nên khi sync ArgoCD sẽ gọi Helm với đủ `-f`. Khi chạy tay, bạn có thể gom hết vào một file values tổng hoặc dùng script/Makefile.

### Install

```bash
helm install banking-demo ./banking-demo -n banking --create-namespace \
  -f banking-demo/charts/common/values.yaml \
  -f banking-demo/charts/postgres/values.yaml \
  # ... (hoặc một file values merge sẵn)
```

### Upgrade (đổi image, scale, config)

```bash
helm upgrade banking-demo ./banking-demo -n banking \
  -f banking-demo/charts/common/values.yaml \
  -f banking-demo/charts/auth-service/values.yaml \
  --set auth-service.image.tag=v2
```

### Chỉ deploy hạ tầng (tắt app + ingress)

Tạo file values (vd `values-infra-only.yaml`) và set các component còn lại `enabled: false`:

```yaml
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

Rồi install/upgrade với `-f values-infra-only.yaml`. Chỉ namespace, secret, postgres, redis được tạo.

---

## Mapping Phase 1 → Phase 2

| Phase 1 (manifest) | Phase 2 (Helm) |
|-------------------|----------------|
| `namespace.yaml` | `templates/namespace.yaml` (điều khiển bởi `namespace.enabled`) |
| `secret.yaml` | `templates/secret.yaml` (điều khiển bởi `secret.enabled`) |
| `postgres.yaml` | `templates/postgres-statefulset.yaml` + `postgres-service.yaml` (values: `charts/postgres/values.yaml`) |
| `redis.yaml` | `templates/redis-statefulset.yaml` + `redis-service.yaml` |
| `kong-configmap.yaml` + `kong.yaml` | `templates/kong-configmap.yaml` + `kong-deployment.yaml` + `kong-service.yaml` |
| `auth-service.yaml` (Deployment+Service) | `templates/auth-service-deployment.yaml` + `auth-service-service.yaml` |
| Tương tự account, transfer, notification, frontend | Cùng pattern, values trong `charts/<service>/values.yaml` |
| `ingress.yaml` | `templates/ingress.yaml` (paths từ `ingress.paths`) |

Logic và resource giống Phase 1; khác là mọi thứ được sinh từ template + values, dễ đổi theo env và dễ bật/tắt từng phần.

---

## Lưu ý khi dùng

- **Mật khẩu**: Trong demo, secret nằm trong values (có thể commit). Production nên dùng `--set secret.postgresPassword=...` hoặc external secrets, không commit mật khẩu.
- **Ingress**: Host và paths phải khớp với HAProxy/Ingress controller; `serviceName`/`servicePort` phải trùng với tên Service và port do chart tạo (fullnameOverride + service.port).
- **Sửa một service**: Chỉnh `charts/<service>/values.yaml` hoặc override khi gọi helm; không cần sửa file trong `templates/` trừ khi đổi logic chung.
- **Helm hooks** (Phase 2 có dùng): Secret/Postgres/Redis có thể gắn hook pre-install/pre-upgrade để thứ tự deploy đúng. Khi dùng ArgoCD cần lưu ý ArgoCD có thể không chạy hook tùy cấu hình — chi tiết xem tài liệu ArgoCD trong repo.

---

## Tóm tắt

- **Phase 2** chuyển toàn bộ manifest Phase 1 sang **một Helm chart umbrella** (banking-demo).
- **Bootstrap style**: templates tập trung trong `templates/`, mỗi service chỉ có `Chart.yaml` + `values.yaml` trong `charts/<service>/`.
- Cấu hình được **parameter hóa** (ports, probes, resources, secret, storage, ingress); bật/tắt component qua **enabled**.
- Cài/upgrade bằng `helm install` / `helm upgrade` với `-f` (và/hoặc `--set`); có thể chỉ deploy hạ tầng bằng cách tắt các component app.

Bài tiếp theo sẽ đi sâu **ArgoCD (GitOps)**: deploy chart này từ Git, sync tự động, và quản lý nhiều môi trường bằng valueFiles.

---

## Bài tiếp theo

**Bài 5**: *ArgoCD và GitOps — Deploy Helm chart từ Git*

- Application / ApplicationSet trỏ tới repo + path chart
- ValueFiles theo môi trường (staging/production)
- Sync policy, auto sync, và cách xử lý khi có hook

---

*Tags: #helm #kubernetes #devops #microservices #bootstrap*
