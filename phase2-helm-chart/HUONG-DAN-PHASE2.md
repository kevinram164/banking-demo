# Hướng dẫn chi tiết cấu trúc Phase 2 (Helm)

Tài liệu này dành cho người mới: giải thích **cấu trúc folder** phase2, **Helm dùng để làm gì**, và **cách các file liên kết với nhau**.

---

## 1. Phase 2 là gì? Tại sao dùng Helm?

- **Phase 1** (thư mục `phase1-docker-to-k8s`): Bạn có nhiều file YAML Kubernetes (namespace, deployment, service, …). Mỗi lần đổi port, image, env là phải sửa tay trong từng file.
- **Phase 2**: Chuyển toàn bộ sang **Helm chart**. Thay vì viết cứng (hardcode) trong YAML, ta dùng **biến** (values). Muốn đổi cấu hình chỉ cần sửa **values** hoặc truyền **override** khi cài, không cần sửa từng manifest.

**Lợi ích chính:**

- Một lệnh cài: `helm install banking-demo ./banking-demo -n banking` → deploy đủ namespace, database, gateway, các service, frontend, ingress.
- Cấu hình theo môi trường: dev/staging/prod chỉ khác file values hoặc `--set`.
- Dễ bật/tắt từng phần: ví dụ tắt ingress bằng `--set ingress.enabled=false`.

---

## 2. Cấu trúc tổng thể thư mục Phase 2

```
phase2-helm-chart/
├── HUONG-DAN-PHASE2.md    ← Bạn đang đọc
├── PHASE2.md              ← Tóm tắt kỹ thuật, lệnh cài/upgrade
├── helm-quickstart/       ← Ví dụ Helm đơn giản cho người mới (xem mục 8)
└── banking-demo/          ← Chart chính (umbrella) của toàn bộ ứng dụng
    ├── Chart.yaml         ← Metadata của chart (tên, version, mô tả)
    ├── values.yaml        ← Cấu hình mặc định cho TẤT CẢ components
    ├── templates/         ← TẤT CẢ file template (Deployment, Service, …) — chung một chỗ
    │   ├── _helpers.tpl
    │   ├── namespace.yaml
    │   ├── secret.yaml
    │   ├── postgres-*.yaml, redis-*.yaml, kong-*.yaml
    │   ├── *-service-*.yaml (auth, account, transfer, notification)
    │   ├── frontend-*.yaml
    │   ├── ingress.yaml
    │   └── NOTES.txt
    └── charts/            ← Mỗi service: CHỈ có Chart.yaml + values.yaml (không có templates)
        ├── postgres/
        ├── redis/
        ├── kong/
        ├── auth-service/
        ├── account-service/
        ├── transfer-service/
        ├── notification-service/
        └── frontend/
```

**Ý tưởng thiết kế:**

- **Templates tập trung**: Mọi file tạo ra Kubernetes manifest (Deployment, Service, ConfigMap, …) nằm trong **một** thư mục `banking-demo/templates/`. Dễ tìm, dễ sửa đồng bộ.
- **Mỗi service một folder (chỉ values)**: Trong `charts/<tên-service>/` **chỉ có** `Chart.yaml` và `values.yaml`. Folder này **không** chứa file template; dùng để **override** cấu hình (ví dụ image, port, env) khi deploy.

---

## 3. Các phần quan trọng trong `banking-demo/`

### 3.1. `Chart.yaml`

- **Vai trò**: Khai báo chart là gì (tên, mô tả, version, appVersion, …).
- **Người mới cần biết**: Đây là “hộ chiếu” của chart. Helm dùng nó để nhận diện chart; không chứa cấu hình chạy (port, image, …).

```yaml
name: banking-demo
description: Banking Demo - Helm bootstrap chart ...
version: 0.1.0
appVersion: "1"
```

Chart này **không** dùng `dependencies` (subchart). Cấu hình nằm ở `values.yaml` và các file trong `charts/<service>/values.yaml`.

---

### 3.2. `values.yaml` (ở thư mục gốc banking-demo)

- **Vai trò**: File cấu hình **mặc định** cho **toàn bộ** ứng dụng. Mọi template trong `templates/` đều lấy giá trị từ đây (qua `.Values.postgres`, `.Values.redis`, `.Values.kong`, `.Values.auth-service`, …).
- **Người mới cần biết**:
  - Nếu bạn **không** truyền `-f` hoặc `--set`, Helm sẽ dùng **toàn bộ** giá trị trong file này.
  - Khi bạn dùng `-f charts/auth-service/values.yaml` hoặc `--set postgres.storage.size=2Gi`, Helm **merge** (ghép) với file này: chỗ nào bạn override thì dùng giá trị của bạn, chỗ còn lại giữ mặc định.

**Cấu trúc trong `values.yaml` (tóm tắt):**

| Phần | Ý nghĩa |
|------|--------|
| `global` | Namespace, tên Secret, CORS, imagePullSecrets — dùng chung |
| `namespace` | Bật/tắt tạo namespace (ví dụ `banking`) |
| `secret` | Bật/tắt và nội dung Secret (DB user/password, URL) |
| `postgres` | Image, port, storage, probe, resources, hook … |
| `redis` | Tương tự postgres |
| `kong` | Image, port, backends, CORS, config … |
| `auth-service`, `account-service`, … | Image, port, env, probe, resources … |
| `frontend` | Image, port, env … |
| `ingress` | Host, class, paths (route đến service nào, port nào) |

Mỗi key (ví dụ `postgres`, `auth-service`) **trùng với tên folder** trong `charts/`. Để override chỉ cho một service, bạn có thể sửa `charts/<service>/values.yaml` và dùng `-f charts/<service>/values.yaml` khi `helm install` hoặc `helm upgrade`.

---

### 3.3. Thư mục `templates/`

- **Vai trò**: Chứa **toàn bộ** file template. Mỗi file là một (hoặc vài) manifest Kubernetes, nhưng có chỗ để **điền biến** (tên, image, port, …) từ `values.yaml`.
- **Người mới cần biết**:
  - Template dùng cú pháp **Go template** (Helm mở rộng): `{{ .Values.postgres.image.tag }}`, `{{ include "banking-demo.postgres.fullname" . }}`, …
  - Helm khi chạy `helm install` hoặc `helm template` sẽ **render**: thay thế các `{{ ... }}` bằng giá trị thực, rồi gửi YAML đã render lên cluster (hoặc in ra màn hình).

**Bảng map: file template ↔ resource Kubernetes**

| File trong templates/ | Tạo ra resource gì |
|------------------------|---------------------|
| `namespace.yaml` | Namespace (ví dụ `banking`) |
| `secret.yaml` | Secret (DB password, URL, …) |
| `postgres-statefulset.yaml` | StatefulSet Postgres |
| `postgres-service.yaml` | Service Postgres |
| `redis-statefulset.yaml` | StatefulSet Redis |
| `redis-service.yaml` | Service Redis |
| `kong-configmap.yaml` | ConfigMap cấu hình Kong |
| `kong-deployment.yaml` | Deployment Kong |
| `kong-service.yaml` | Service Kong |
| `auth-service-deployment.yaml` | Deployment auth-service |
| `auth-service-service.yaml` | Service auth-service |
| (tương tự) `account-service-*`, `transfer-service-*`, `notification-service-*` | Deployment + Service từng service |
| `frontend-deployment.yaml`, `frontend-service.yaml` | Deployment + Service frontend |
| `ingress.yaml` | Ingress (routing HTTP) |
| `_helpers.tpl` | Không tạo resource; chứa hàm dùng chung (fullname, labels, …) cho các template khác |
| `NOTES.txt` | Text in ra sau khi cài xong (hướng dẫn user) |

Ví dụ trong template: `{{ $svc := index .Values "auth-service" }}` và `{{ $svc.image.repository }}` — nghĩa là “lấy phần cấu hình có key `auth-service` trong values, rồi lấy tiếp `image.repository`”. Giá trị đó nằm trong `values.yaml` (parent) hoặc được override bởi `charts/auth-service/values.yaml`.

---

### 3.4. Thư mục `charts/<service>/`

- **Vai trò**: Mỗi service (postgres, redis, kong, auth-service, …) có **một folder**. Trong folder **chỉ có** hai file:
  - `Chart.yaml`: metadata của “subchart” (tên, version) — trong thiết kế hiện tại chart không load dependency nên chỉ để tham chiếu/organize.
  - `values.yaml`: **Giá trị override** cho đúng service đó.
- **Người mới cần biết**:
  - **Không có** thư mục `templates` trong từng `charts/<service>/`. Template thật sự nằm ở `banking-demo/templates/`.
  - Khi bạn chạy:  
    `helm install banking-demo ./banking-demo -n banking -f charts/auth-service/values.yaml`  
    Helm sẽ merge `charts/auth-service/values.yaml` với parent `values.yaml`. Các key trong file override (ví dụ `auth-service.image.tag`) sẽ ghi đè lên cùng key trong parent.

Ví dụ trong `charts/auth-service/values.yaml` bạn có thể đặt:

```yaml
fullnameOverride: auth-service
image:
  repository: registry.gitlab.com/.../auth-service
  tag: v1
service:
  port: 8001
```

Những gì bạn **không** khai báo ở đây sẽ lấy từ `banking-demo/values.yaml` (phần `auth-service:`).

---

## 4. Luồng hoạt động: values → template → manifest

1. Bạn chạy lệnh Helm, ví dụ:  
   `helm install banking-demo ./banking-demo -n banking`
2. Helm đọc:
   - `values.yaml` (parent),
   - (nếu có) các file `-f file1.yaml -f file2.yaml` và `--set key=value`.
3. Merge tất cả thành một bộ `.Values` (file sau / --set sau ghi đè lên trước).
4. Với **mỗi file** trong `templates/` (trừ file bắt đầu bằng `_`), Helm **render** nội dung: thay `{{ ... }}` bằng giá trị từ `.Values` và các helper.
5. Một số file có điều kiện `{{- if .Values.xxx.enabled }}`. Nếu `enabled: false` thì đoạn manifest đó không được tạo.
6. Kết quả: một bộ YAML Kubernetes đầy đủ. Helm gửi lên cluster (install/upgrade) hoặc in ra (template).

---

## 5. Override cấu hình (người mới hay cần)

- **Override bằng file** (thường dùng cho từng service hoặc từng môi trường):

  ```bash
  helm install banking-demo ./banking-demo -n banking -f charts/auth-service/values.yaml
  ```

  Hoặc dùng file tự đặt tên:

  ```bash
  helm install banking-demo ./banking-demo -n banking -f my-dev-values.yaml
  ```

- **Override một vài giá trị nhanh** (dùng `--set`):

  ```bash
  helm install banking-demo ./banking-demo -n banking --set postgres.storage.size=2Gi
  ```

- **Tắt một component** (ví dụ tắt ingress):

  ```bash
  helm install banking-demo ./banking-demo -n banking --set ingress.enabled=false
  ```

Cấu trúc key phải trùng với trong `values.yaml` (ví dụ `postgres.storage.size`, `ingress.enabled`).

---

## 6. Các lệnh Helm cơ bản (trong thư mục phase2-helm-chart)

- **Kiểm tra chart (lint):**  
  `helm lint ./banking-demo`

- **Xem manifest sẽ được áp dụng (không cài lên cluster):**  
  `helm template banking-demo ./banking-demo -n banking`

- **Cài lần đầu:**  
  `helm install banking-demo ./banking-demo -n banking --create-namespace`

- **Nâng cấp (sau khi sửa values/template):**  
  `helm upgrade banking-demo ./banking-demo -n banking`

- **Xem release đã cài:**  
  `helm list -n banking`

- **Gỡ cài:**  
  `helm uninstall banking-demo -n banking`

---

## 7. Tóm tắt cho người mới

| Bạn muốn… | Làm gì |
|-----------|--------|
| Hiểu “chart này gồm gì” | Xem `Chart.yaml` và cấu trúc `values.yaml` (các key top-level: postgres, redis, kong, auth-service, …). |
| Biết “file YAML nào tạo Deployment/Service X” | Vào `banking-demo/templates/`, tìm tên tương ứng (ví dụ `auth-service-deployment.yaml`). |
| Đổi cấu hình mặc định cho cả chart | Sửa `banking-demo/values.yaml`. |
| Đổi cấu hình chỉ một service (ví dụ auth-service) | Sửa `banking-demo/charts/auth-service/values.yaml` và dùng `-f charts/auth-service/values.yaml` khi install/upgrade. |
| Đổi nhanh 1–2 giá trị khi cài | Dùng `--set postgres.storage.size=2Gi` (ví dụ). |
| Xem YAML thực tế trước khi cài | Chạy `helm template banking-demo ./banking-demo -n banking`. |

---

## 8. Học Helm từ đơn giản: ví dụ `helm-quickstart`

Trong phase2 có thêm thư mục **`helm-quickstart/`**: một chart **rất nhỏ** (ví dụ một Deployment + một Service). Ở đó có:

- Cấu trúc Helm tối thiểu: `Chart.yaml`, `values.yaml`, `templates/` với ít file.
- README hướng dẫn từng bước: `helm template`, `helm install`, `--set`, `-f`, `helm upgrade`.

Bạn nên chạy thử các lệnh trong `helm-quickstart/` trước khi đào sâu vào cấu trúc `banking-demo`. Khi đã quen với cách values + templates tạo ra manifest, bạn sẽ thấy phase2 chỉ là “chart lớn hơn, nhiều service hơn” cùng một cách làm.

Chi tiết xem file: **`helm-quickstart/README.md`**.
