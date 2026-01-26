# Deploy banking-demo với ArgoCD (GitOps)

Hướng dẫn triển khai chart **banking-demo** bằng ArgoCD theo cách chuyên nghiệp: cấu hình trong Git, sync tự động, tách môi trường (staging/production).

---

## 1. Nguyên tắc GitOps với ArgoCD

- **Nguồn chân lý là Git**: Chart và values nằm trong repo; ArgoCD đọc Git và áp dụng lên cluster.
- **Không cài Helm tay**: `helm install`/`helm upgrade` do ArgoCD thực hiện khi bạn push thay đổi lên Git.
- **Môi trường tách bằng value files**: Mỗi env (staging, production) dùng một file values override trong cùng chart.

**Cấu trúc thư mục liên quan:**

```
phase2-helm-chart/
├── argocd/
│   ├── project.yaml                   # ArgoCD Project (gom nhóm, giới hạn repo/namespace)
│   ├── application.yaml               # Application đơn — deploy cả chart một lần
│   ├── application-set.yaml           # ApplicationSet — nhiều môi trường (staging/prod)
│   ├── application-set-per-service.yaml # ApplicationSet — deploy riêng từng service
│   └── ARGOCD.md                      # File này
└── banking-demo/
    ├── Chart.yaml
    ├── values.yaml                    # Mặc định
    ├── values-production.yaml         # Override production
    ├── values-staging.yaml            # Override staging
    ├── values-infra-only.yaml         # Chỉ infra (namespace, secret, postgres, redis)
    ├── values-kong-only.yaml          # Chỉ Kong
    ├── values-auth-only.yaml          # Chỉ auth-service
    ├── values-*-only.yaml             # Các phần còn lại (account, transfer, notification, frontend, ingress)
    ├── templates/
    └── charts/
```

---

## 2. Chuẩn bị

### 2.1. Cài ArgoCD lên cluster

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
# Đợi pods Running
kubectl wait --for=condition=Ready pods -l app.kubernetes.io/name=argocd-server -n argocd --timeout=120s
```

Lấy mật khẩu admin (để đăng nhập UI):

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

Port-forward UI (hoặc dùng Ingress):

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Mở https://localhost:8080, user: admin, password: (lấy ở trên)
```

### 2.2. Repo Git phải được ArgoCD truy cập được

- Repo **public**: ArgoCD clone không cần cấu hình thêm.
- Repo **private**: Tạo Secret trong `argocd` chứa credential (SSH key hoặc HTTPS user/pass), rồi khai báo trong Application/Project. Xem [ArgoCD Repo](https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories/).

---

## 3. Deploy bằng một Application (một môi trường)

### Bước 1: Sửa Application cho đúng repo

Mở `argocd/application.yaml`, sửa:

- **spec.source.repoURL**: URL repo Git chứa project (vd: `https://github.com/your-org/banking-demo.git`).
- **spec.source.targetRevision**: Branch hoặc tag (vd: `main`, `master`, `v1.0`).
- **spec.source.helm.valueFiles** (tùy chọn):
  - Chỉ `values.yaml`: dùng mặc định.
  - Thêm `values-production.yaml`: dùng override production (đặt trong `banking-demo/`).

Ví dụ dùng production overrides:

```yaml
helm:
  releaseName: banking-demo
  valueFiles:
    - values.yaml
    - values-production.yaml
```

### Bước 2: Áp dụng Application

```bash
kubectl apply -f phase2-helm-chart/argocd/application.yaml -n argocd
```

Hoặc nếu đang ở thư mục `argocd/`:

```bash
kubectl apply -f application.yaml -n argocd
```

### Bước 3: Kiểm tra

- **CLI**: `argocd app get banking-demo` (cần login trước: `argocd login ...`).
- **UI**: Vào ArgoCD UI → Application `banking-demo` → Sync status, Events, Resource tree.
- **Kubernetes**: `kubectl get all -n banking`

Sync mặc định là **automated** (prune + selfHeal). Sau mỗi lần push lên Git, ArgoCD sẽ refresh và cập nhật cluster theo chart/values mới.

---

## 4. Nhiều môi trường với ApplicationSet (tùy chọn)

Để cùng một repo deploy **staging** và **production** (mỗi env một namespace, một value file):

1. Cài [ApplicationSet controller](https://argo-cd.readthedocs.io/en/stable/user-guide/application-set/) (có sẵn trên bản ArgoCD mới).
2. Sửa `argocd/application-set.yaml`: đổi `repoURL`, `targetRevision`, và danh sách `elements` (env, namespace, valueFile) cho đúng.
3. Áp dụng:

   ```bash
   kubectl apply -f phase2-helm-chart/argocd/application-set.yaml -n argocd
   ```

Sẽ tạo ra hai Application: `banking-demo-staging`, `banking-demo-production`, tương ứng hai namespace và hai bộ values.

---

## 4a. Deploy riêng từng service (một Application một phần)

Khi muốn **sync/rollout từng phần độc lập** (ví dụ chỉ đổi auth-service mà không đụng postgres): dùng **cùng chart**, **nhiều Application**, mỗi Application có **releaseName** và **valueFiles** khác nhau — chỉ bật đúng một (hoặc một nhóm) component.

### Value files “chỉ một phần”

Trong `banking-demo/` có các file chỉ bật một phần, phần còn lại `enabled: false`:

| File | Phần được deploy |
|------|-------------------|
| `values-infra-only.yaml` | namespace, secret, postgres, redis |
| `values-kong-only.yaml` | Kong |
| `values-auth-only.yaml` | auth-service |
| `values-account-only.yaml` | account-service |
| `values-transfer-only.yaml` | transfer-service |
| `values-notification-only.yaml` | notification-service |
| `values-frontend-only.yaml` | frontend |
| `values-ingress-only.yaml` | ingress |

### ApplicationSet “per-service”

File **`application-set-per-service.yaml`** tạo **8 Application** (mỗi phần một app):

- `banking-demo-infra`, `banking-demo-kong`, `banking-demo-auth`, `banking-demo-account`, …
- Mỗi app: `releaseName` riêng, `valueFiles: [values.yaml, values-xxx-only.yaml]`, cùng `path` chart.
- Cùng namespace `banking` (có thể đổi trong template nếu cần).

**Áp dụng (sau khi đã có Project và sửa repoURL/targetRevision):**

```bash
kubectl apply -f argocd/application-set-per-service.yaml -n argocd
```

**Thứ tự deploy đề xuất** (vì dependency): deploy/sync **infra** trước (namespace, secret, postgres, redis), rồi **kong**, rồi các microservice (auth → account → transfer → notification), cuối cùng **frontend** và **ingress**. Trong UI có thể sync lần lượt hoặc để automated; app nào chưa đủ dependency sẽ lỗi đến khi infra đã sẵn sàng.

**Chỉ cần một vài service:** Sửa `application-set-per-service.yaml`, xóa bớt phần trong `generators.list.elements` (ví dụ chỉ giữ infra, kong, auth). Hoặc tạo Application thủ công từng cái với `releaseName` và `valueFiles` tương ứng.

---

## 4b. Dùng ArgoCD Project

**Project** (AppProject) dùng để:

- **Gom nhóm** Application theo app/product (trong UI, RBAC).
- **Giới hạn** Application chỉ được trỏ tới repo và namespace trong allow list (bảo mật, đa team).

### Tạo Project

File **`project.yaml`** khai báo Project `banking-demo`:

- **sourceRepos**: Chỉ cho phép deploy từ repo được liệt kê (sửa thành URL repo của bạn).
- **destinations**: Chỉ cho phép deploy tới namespace `banking` (và cluster mặc định). Có thể thêm `banking-staging`, `banking-prod`.
- **clusterResourceWhitelist** / **namespaceResourceWhitelist**: Giới hạn loại resource được tạo (Namespace, Deployment, Service, Ingress, …).

**Áp dụng Project trước khi tạo Application:**

```bash
kubectl apply -f argocd/project.yaml -n argocd
```

Sửa `project.yaml`: thay `https://github.com/YOUR_ORG/banking-demo.git` bằng repo thật. Nếu dùng nhiều repo (vd fork), thêm vào `sourceRepos`.

### Khai báo Application thuộc Project

Trong **application.yaml**, **application-set.yaml**, **application-set-per-service.yaml** đặt:

```yaml
spec:
  project: banking-demo
```

Nếu **chưa** tạo Project, đổi thành `project: default` để Application vẫn chạy. Khi đã apply `project.yaml`, dùng `project: banking-demo` để mọi app banking-demo nằm trong một Project, dễ quản lý và áp RBAC (vd chỉ team banking được sửa app trong project này).

---

## 5. Thực hành chuyên nghiệp

### 5.1. Values theo môi trường

- **values.yaml**: Mặc định (dev/local).
- **values-staging.yaml**: Override cho staging (ít replica, ít tài nguyên, domain staging).
- **values-production.yaml**: Override cho production (replica/resources lớn hơn, domain production).

Tất cả nằm trong `banking-demo/` để ArgoCD đọc được (valueFiles relative to chart path).

### 5.2. Mật khẩu / Secret nhạy cảm

- **Không** commit mật khẩu production vào Git. Có thể:
  - Dùng **ArgoCD Helm parameters** (values inject từ Secret hoặc env của ArgoCD).
  - Dùng **External Secrets Operator** hoặc **Sealed Secrets**: giữ secret được mã hóa trong Git hoặc lấy từ Vault/AWS Secrets Manager.
  - CI/CD: build và apply Application với `helm.parameters` từ biến môi trường.

Ví dụ override password qua parameters trong Application:

```yaml
source:
  helm:
    parameters:
      - name: secret.postgresPassword
        valueFrom:
          secretKeyRef:
            name: banking-demo-secrets
            key: postgres-password
            namespace: argocd
```

(Secret `banking-demo-secrets` tạo tay hoặc từ tool quản lý secret.)

### 5.3. Branch / tag rõ ràng

- **targetRevision**: Dùng branch cố định (vd: `main`) cho auto-deploy khi push; hoặc tag (vd: `v1.2.0`) để deploy đúng version và tránh vỡ.

### 5.4. Sync policy

- **automated.prune: true**: Xóa resource trên cluster khi không còn trong chart (an toàn nếu chart là nguồn chân lý duy nhất).
- **automated.selfHeal: true**: Tự sửa drift (khi có người/kịch bản sửa tay trên cluster).
- Nếu muốn duyệt deploy thủ công: bỏ `syncPolicy.automated`, sync bằng tay qua UI hoặc `argocd app sync`.

### 5.5. Namespace

- **CreateNamespace=true** trong syncOptions: ArgoCD tự tạo namespace đích nếu chưa có (vd: `banking`).
- Chart của banking-demo cũng có thể tạo namespace (trong templates); cần thống nhất một nơi (khuyến nghị: để ArgoCD tạo namespace đích, chart vẫn có thể giữ template namespace với `namespace.enabled`).

### 5.6. Thứ tự cài (Helm hooks)

Chart banking-demo dùng Helm hooks (namespace, secret, postgres/redis trước). ArgoCD khi sync sẽ chạy Helm upgrade/install, đảm bảo thứ tự hooks được tôn trọng.

---

## 6. Lệnh thường dùng

| Việc cần làm | Lệnh / thao tác |
|--------------|------------------|
| Áp dụng Application | `kubectl apply -f argocd/application.yaml -n argocd` |
| Xem trạng thái | ArgoCD UI → banking-demo, hoặc `argocd app get banking-demo` |
| Sync ngay (không đợi refresh) | UI: nút Sync, hoặc `argocd app sync banking-demo` |
| Hard refresh (bỏ cache Git) | `argocd app get banking-demo --refresh` hoặc UI Refresh |
| Xóa deploy | Xóa Application: `kubectl delete application banking-demo -n argocd` (có thể giữ namespace) |

---

## 7. Tóm tắt

- Đặt **chart + values** trong Git; ArgoCD **Application** trỏ tới path chart và valueFiles.
- **Một app cả chart:** dùng `application.yaml` (releaseName `banking-demo`, valueFiles mặc định hoặc production/staging).
- **Deploy riêng từng service:** dùng `application-set-per-service.yaml` (nhiều app, mỗi app một value file `values-*-only.yaml`); sync infra trước rồi Kong, rồi services, frontend, ingress.
- **Nhiều môi trường (staging/prod):** dùng `application-set.yaml` với namespace và value file khác nhau.
- **ArgoCD Project:** áp dụng `project.yaml` rồi đặt `spec.project: banking-demo` trong mọi Application/ApplicationSet để gom nhóm và giới hạn repo/namespace.
- Repo private thì cấu hình credential trong ArgoCD; mật khẩu production không commit vào Git.
- Bật **automated sync** (prune + selfHeal) nếu bạn muốn cluster luôn khớp với Git.

Sau khi chỉnh repoURL, targetRevision, valueFiles và (tuỳ chọn) project, apply Application hoặc ApplicationSet trong `argocd/` để ArgoCD deploy và duy trì banking-demo từ repo của bạn.
