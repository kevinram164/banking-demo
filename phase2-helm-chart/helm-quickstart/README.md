# Helm Quickstart — Ví dụ Helm cho người mới

Chart này là **ví dụ tối giản** để bạn làm quen với Helm mà không cần hiểu nhiều Kubernetes. Chỉ có **1 Deployment** và **1 Service** (ứng dụng mẫu dùng image `nginx:alpine`).

Sau khi làm xong các bước dưới, bạn sẽ hiểu:

- Chart gồm **Chart.yaml**, **values.yaml** và thư mục **templates/**.
- Helm **render** template bằng values rồi tạo ra manifest Kubernetes.
- Cách **override** cấu hình bằng `--set` và `-f file.yaml`.

---

## 1. Cấu trúc chart

```
helm-quickstart/
├── Chart.yaml          # Metadata chart (tên, version)
├── values.yaml         # Cấu hình mặc định (name, replicas, image, service)
├── templates/
│   ├── _helpers.tpl    # Hàm dùng chung (tên app)
│   ├── deployment.yaml   # Deployment
│   ├── service.yaml   # Service
│   └── NOTES.txt      # Thông báo sau khi cài
└── README.md
```

- **Chart.yaml**: Cho Helm biết chart tên gì, version bao nhiêu. Không chứa cấu hình chạy.
- **values.yaml**: Toàn bộ giá trị mặc định. Template sẽ đọc qua `{{ .Values.name }}`, `{{ .Values.replicas }}`, …
- **templates/**: Mỗi file (trừ `_helpers.tpl` và `NOTES.txt`) sẽ tạo ra **một** resource Kubernetes. Cú pháp `{{ ... }}` là Go template; Helm thay thế bằng giá trị từ values.

---

## 2. Chuẩn bị

- Cài [Helm](https://helm.sh/docs/intro/install/) (ví dụ `choco install kubernetes-helm` trên Windows).
- Có cluster Kubernetes (minikube, kind, hoặc cluster thật) và `kubectl` đã cấu hình.

---

## 3. Xem manifest mà Helm sẽ tạo (không cài lên cluster)

Từ thư mục chứa `helm-quickstart` (ví dụ `phase2-helm-chart`), chạy:

```bash
helm template my-release ./helm-quickstart -n default
```

- `my-release`: tên release (bạn đặt tùy ý).
- `./helm-quickstart`: đường dẫn đến chart.
- `-n default`: namespace (có thể đổi thành `demo`).

Kết quả: Helm in ra **toàn bộ YAML** đã được thay thế biến. Bạn sẽ thấy một Deployment và một Service với tên lấy từ `values.yaml` (mặc định `name: myapp` → tên resource là `myapp`).

**Thử đổi giá trị khi render:**

```bash
helm template my-release ./helm-quickstart -n default --set name=hello --set replicas=3
```

Output sẽ có `replicas: 3` và tên resource là `hello`. Đó chính là **override** bằng `--set`.

---

## 4. Cài chart lên cluster

```bash
# Tạo namespace (nếu muốn tách riêng)
kubectl create namespace demo

# Cài chart
helm install my-release ./helm-quickstart -n demo
```

Sau khi chạy, Helm in ra nội dung `NOTES.txt` (hướng dẫn xem pod/service).

**Kiểm tra:**

```bash
kubectl get pods,svc -n demo
```

Bạn sẽ thấy Pod và Service (tên mặc định `myapp` nếu không override).

---

## 5. Override cấu hình

### 5.1. Dùng `--set` (đổi nhanh 1–2 giá trị)

```bash
helm install my-release ./helm-quickstart -n demo --set name=webapp --set replicas=2
```

Hoặc khi **nâng cấp** (sửa release đã cài):

```bash
helm upgrade my-release ./helm-quickstart -n demo --set replicas=2
```

### 5.2. Dùng file values (override nhiều thứ)

Tạo file `my-values.yaml` (cùng cấp với folder `helm-quickstart`):

```yaml
name: production-app
replicas: 2
image:
  repository: nginx
  tag: "stable"
service:
  port: 80
  type: ClusterIP
```

Cài với file này:

```bash
helm install my-release ./helm-quickstart -n demo -f my-values.yaml
```

Helm sẽ **merge** `my-values.yaml` với `values.yaml` trong chart; giá trị trong `my-values.yaml` ghi đè giá trị mặc định.

---

## 6. Các lệnh Helm hay dùng

| Lệnh | Ý nghĩa |
|------|--------|
| `helm lint ./helm-quickstart` | Kiểm tra chart có lỗi cú pháp không |
| `helm template my-release ./helm-quickstart -n demo` | Xem YAML render, không cài |
| `helm install my-release ./helm-quickstart -n demo` | Cài lần đầu |
| `helm upgrade my-release ./helm-quickstart -n demo` | Cập nhật release |
| `helm list -n demo` | Liệt kê release trong namespace |
| `helm uninstall my-release -n demo` | Gỡ release (xóa resource do chart tạo) |

---

## 7. So sánh với chart banking-demo

| Quickstart (ví dụ này) | banking-demo (Phase 2) |
|------------------------|-------------------------|
| 1 Deployment, 1 Service | Nhiều Deployment, Service, Ingress, ConfigMap, … |
| Một file `values.yaml` | Một `values.yaml` gốc + nhiều `charts/<service>/values.yaml` để override |
| Template đơn giản, ít biến | Template phức tạp hơn, có helper, có điều kiện `enabled` |

Cách hoạt động giống nhau: **values** + **templates** → **manifest Kubernetes**. Banking-demo chỉ nhiều component và tổ chức values theo từng service hơn.

---

## 8. Đọc thêm

- Hướng dẫn chi tiết cấu trúc Phase 2: **`../HUONG-DAN-PHASE2.md`**
- Lệnh cài/nâng cấp chart banking-demo: **`../PHASE2.md`**
- Tài liệu Helm: https://helm.sh/docs/
