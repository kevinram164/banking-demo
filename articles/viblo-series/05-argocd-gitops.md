# Banking Demo: ArgoCD và GitOps — Deploy Helm chart từ Git

> **Series**: Banking Demo — Full DevOps với Microservices  
> **Bài 5/11**: ArgoCD và GitOps — Deploy Helm chart từ Git

---

## Mở đầu

Ở **bài 4**, chúng ta đã chuyển toàn bộ manifest sang Helm chart trong `phase2-helm-chart/banking-demo/`. Cài đặt và nâng cấp đều dùng `helm install` / `helm upgrade` với nhiều file values. Điều đó vẫn đòi hỏi mỗi môi trường phải có người (hoặc script) chạy Helm tay; thay đổi từ Git chưa tự động phản ánh lên cluster.

**GitOps** đưa **Git làm nguồn chân lý**: cấu hình (chart + values) nằm trong repo; một công cụ đọc Git và đồng bộ lên Kubernetes. **ArgoCD** là công cụ phổ biến nhất cho việc này: nó clone repo, render Helm (hoặc Kustomize), so sánh với cluster và apply khi bạn sync.

Bài này giải thích cách deploy chart **banking-demo** bằng ArgoCD: Application trỏ tới repo + path chart, valueFiles theo môi trường, sync policy, sync waves và lưu ý khi dùng Helm hooks.

---

## GitOps và ArgoCD trong một phút

| Khái niệm | Ý nghĩa |
|-----------|----------|
| **GitOps** | Git là nguồn chân lý; mọi thay đổi cấu hình qua Git, không sửa tay trên cluster. |
| **ArgoCD** | Controller đọc Git (Helm/Kustomize/plain YAML), so sánh với cluster, apply khi sync. |
| **Application** | Một resource ArgoCD mô tả “lấy gì từ đâu, deploy vào đâu” (repo, path, namespace). |
| **Sync** | Hành động “áp dụng state từ Git lên cluster” (ArgoCD chạy `helm template` + `kubectl apply`). |

Với Banking Demo: chart và values nằm trong repo; ArgoCD trỏ tới `phase2-helm-chart/banking-demo`, dùng danh sách valueFiles (common + từng service). Khi bạn **sync**, ArgoCD render Helm với các file đó và apply lên namespace `banking`. Không cần cài Helm trên máy hay trong CI; chỉ cần push Git và sync (thủ công hoặc auto).

---

## Hai cách deploy chart với ArgoCD

Trong repo có hai hướng tiếp cận:

| Cách | Mô tả | File | Ưu / Nhược |
|------|--------|------|-------------|
| **Một Application** | Một Application deploy cả chart với đủ valueFiles (common + tất cả services). | `argocd/application.yaml` | Đơn giản, một dashboard; sync/rollback ảnh hưởng cả stack. |
| **Per-service Applications** | Mỗi thành phần (namespace, postgres, redis, kong, từng service, frontend, ingress) một Application riêng. | `argocd/applications/*.yaml` | Dễ quản lý từng phần, sync/rollback độc lập; cần nhiều Application và sync waves. |

Bài này mô tả cả hai; thực tế bạn có thể chọn một trong hai tùy nhu cầu (demo nhanh vs quản lý từng service).

---

## Cấu trúc ArgoCD trong repo

```
phase2-helm-chart/
├── argocd/
│   ├── project.yaml              # AppProject: gom nhóm, giới hạn repo/namespace
│   ├── application.yaml          # Một Application deploy cả chart (đơn giản)
│   ├── applications/            # Per-service (chuyên nghiệp)
│   │   ├── namespace.yaml        # Namespace + Secret (wave -1)
│   │   ├── postgres.yaml
│   │   ├── redis.yaml
│   │   ├── kong.yaml
│   │   ├── auth-service.yaml
│   │   ├── account-service.yaml
│   │   ├── transfer-service.yaml
│   │   ├── notification-service.yaml
│   │   ├── frontend.yaml
│   │   └── ingress.yaml
│   └── ARGOCD.md                 # Hướng dẫn chi tiết, troubleshooting
└── banking-demo/                 # Helm chart (bài 4)
    ├── Chart.yaml
    ├── values.yaml
    ├── templates/
    └── charts/                    # valueFiles trỏ tới đây
```

**AppProject** (`project.yaml`) khai báo project `banking-demo`: cho phép repo nào, deploy vào namespace nào. **Application** (một hoặc nhiều) thuộc project đó, trỏ `source.path` tới `phase2-helm-chart/banking-demo` và dùng `helm.valueFiles` (và có thể `parameters`) để merge values.

---

## Application: repo, path, valueFiles

Một Application ArgoCD cho Helm chart cần:

- **source.repoURL**: URL Git (vd: `https://github.com/kevinram164/banking-demo.git`).
- **source.targetRevision**: Branch hoặc tag (vd: `main`).
- **source.path**: Đường dẫn tới thư mục chứa chart (vd: `phase2-helm-chart/banking-demo`).
- **source.helm.releaseName**: Tên release Helm (hiển thị trong ArgoCD, dùng cho history).
- **source.helm.valueFiles**: Danh sách file values (đường dẫn trong repo), merge theo thứ tự.
- **destination.server**: Cluster (thường `https://kubernetes.default.svc`).
- **destination.namespace**: Namespace đích (vd: `banking`).

Ví dụ **một Application** deploy cả stack (trích từ `application.yaml`):

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: banking-demo
  namespace: argocd
spec:
  project: banking-demo
  source:
    repoURL: https://github.com/kevinram164/banking-demo.git
    targetRevision: main
    path: phase2-helm-chart/banking-demo
    helm:
      releaseName: banking-demo
      valueFiles:
        - charts/common/values.yaml
        - charts/postgres/values.yaml
        - charts/redis/values.yaml
        - charts/kong/values.yaml
        - charts/auth-service/values.yaml
        - charts/account-service/values.yaml
        - charts/transfer-service/values.yaml
        - charts/notification-service/values.yaml
        - charts/frontend/values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: banking
```

ArgoCD sẽ clone repo, vào `path`, chạy tương đương `helm template release-name . -f charts/common/values.yaml -f charts/postgres/values.yaml ...` và apply kết quả lên namespace `banking`. Đổi image, port hay env chỉ cần sửa trong `charts/<service>/values.yaml`, push Git rồi sync Application.

---

## ValueFiles theo môi trường (staging / production)

Cùng một chart, khác môi trường thường chỉ khác **values** (namespace, host ingress, image tag, replica, tài nguyên…). Có hai cách:

### Cách 1: Nhiều file values trong repo, Application chọn danh sách

Trong repo giữ:

- `charts/common/values.yaml` — giá trị chung.
- `charts/<service>/values.yaml` — giá trị mặc định từng service.
- (Tùy chọn) `charts/common/values-staging.yaml`, `charts/common/values-production.yaml` — override theo env.

Application **staging** dùng valueFiles:

```yaml
valueFiles:
  - charts/common/values.yaml
  - charts/common/values-staging.yaml
  - charts/postgres/values.yaml
  # ... các service
```

Application **production** dùng:

```yaml
valueFiles:
  - charts/common/values.yaml
  - charts/common/values-production.yaml
  - charts/postgres/values.yaml
  # ...
```

File sau override file trước; chỉ cần định nghĩa trong `values-staging.yaml` / `values-production.yaml` những key khác (vd `global.namespace`, `ingress.host`, `auth-service.image.tag`).

### Cách 2: ApplicationSet sinh nhiều Application theo môi trường

Dùng **ApplicationSet** (controller riêng, thường cài kèm ArgoCD) để từ một template sinh ra nhiều Application, mỗi env một cái (vd `banking-demo-staging`, `banking-demo-production`). Mỗi Application có `destination.namespace` và valueFiles khác nhau (vd `values-staging.yaml` vs `values-production.yaml`). Chi tiết cấu hình ApplicationSet xem tài liệu ArgoCD; ý tưởng là “một lần khai báo, nhiều môi trường”.

Trong Banking Demo hiện tại, một Application dùng đủ valueFiles (common + từng service); khi cần staging/prod bạn chỉ cần thêm file override và (hoặc) thêm Application/ApplicationSet trỏ tới file đó.

---

## Sync policy: automated, prune, selfHeal, syncOptions

```yaml
syncPolicy:
  automated: null    # Hoặc bỏ; khi null = không auto sync
  syncOptions:
    - CreateNamespace=true
    - ApplyOutOfSyncOnly=true
  retry:
    limit: 3
    backoff:
      duration: 5s
      factor: 2
      maxDuration: 1m
```

| Mục | Ý nghĩa |
|-----|----------|
| **automated** | `null` hoặc không khai báo: chỉ sync khi bạn bấm Sync (UI/CLI). Đặt `automated: { prune: true, selfHeal: true }` thì ArgoCD tự sync theo chu kỳ (vd 3 phút). |
| **prune** | `true`: xóa resource trên cluster nếu không còn trong manifest Git. Nguy hiểm nếu nhầm branch/path; nhiều team chọn `false` và prune thủ công. |
| **selfHeal** | `true`: khi có người/script sửa tay trên cluster, ArgoCD sẽ revert theo Git. An toàn “drift = 0” nhưng dễ gây bất ngờ nếu có thay đổi ngoài ý muốn. |
| **CreateNamespace=true** | Tự tạo namespace đích nếu chưa có. Với “một Application” thường bật; với per-service chỉ bật ở Application tạo namespace (wave -1). |
| **ApplyOutOfSyncOnly=true** | Chỉ apply resource đang OutOfSync, giảm restart không cần thiết (vd không động vào Postgres/Redis khi chỉ đổi image app). |
| **retry** | Khi sync lỗi, ArgoCD retry với backoff; hạn chế số lần và thời gian tối đa. |

Trong repo, **application.yaml** (một Application) đặt `automated: null` — sync thủ công. Các Application per-service trong `applications/*.yaml` dùng `prune: false`, `selfHeal: false` để tránh xóa/sửa drift tự động; bạn chủ động sync khi đã kiểm tra.

---

## Sync Waves (khi dùng per-service Applications)

Khi mỗi service một Application, thứ tự deploy quan trọng: namespace và secret trước, sau đó postgres/redis, rồi Kong, microservices, frontend, cuối cùng ingress. ArgoCD hỗ trợ **sync wave** qua annotation:

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
```

Wave **nhỏ hơn** chạy **trước**. Trong repo:

| Wave | Application | Vai trò |
|------|-------------|---------|
| **-1** | banking-demo-namespace | Namespace + Secret — chạy đầu tiên |
| **0** | banking-demo-postgres, banking-demo-redis | Hạ tầng |
| **1** | banking-demo-kong | API Gateway |
| **2** | auth, account, transfer, notification | Microservices (có thể song song) |
| **3** | banking-demo-frontend | Frontend |
| **4** | banking-demo-ingress | Ingress |

Khi bạn sync tất cả Application cùng lúc (vd `argocd app sync -l app.kubernetes.io/name=banking-demo`), ArgoCD sẽ tôn trọng thứ tự wave: wave -1 xong mới tới 0, 0 xong mới tới 1, …

---

## Per-service: valueFiles và parameters

Mỗi Application per-service trỏ cùng **path** (`phase2-helm-chart/banking-demo`) nhưng chỉ bật đúng một thành phần, tắt hết phần còn lại để Helm chỉ render đúng Deployment/Service (và resource liên quan) của service đó.

Ví dụ **auth-service**:

```yaml
source:
  path: phase2-helm-chart/banking-demo
  helm:
    releaseName: banking-demo-auth-service
    valueFiles:
      - charts/common/values.yaml
      - charts/auth-service/values.yaml
    parameters:
      - name: namespace.enabled
        value: "false"
      - name: secret.enabled
        value: "false"
      - name: postgres.enabled
        value: "false"
      - name: redis.enabled
        value: "false"
      - name: kong.enabled
        value: "false"
      - name: auth-service.enabled
        value: "true"
      - name: account-service.enabled
        value: "false"
      # ... tắt hết service khác, frontend, ingress
```

**valueFiles** đưa common + auth-service; **parameters** override `*.enabled` để chỉ có auth-service được render. Namespace và secret không tạo lại (đã có từ Application wave -1), tránh conflict và SharedResourceWarning.

---

## AppProject: gom nhóm và giới hạn

**AppProject** dùng để:

- Gom nhóm Application theo product/app (trong UI, RBAC).
- Giới hạn repo và namespace mà Application trong project được phép dùng.

Ví dụ `project.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: banking-demo
  namespace: argocd
spec:
  description: "Banking Demo - Helm chart and per-service apps"
  sourceRepos:
    - https://github.com/kevinram164/banking-demo.git
  destinations:
    - namespace: banking
      server: https://kubernetes.default.svc
  clusterResourceWhitelist:
    - group: ""
      kind: Namespace
  namespaceResourceWhitelist:
    - group: ""
      kind: "*"
    - group: apps
      kind: "*"
    # ...
```

Application phải có `spec.project: banking-demo` và chỉ được dùng repo trong `sourceRepos`, deploy vào `destination` đã khai báo. Áp dụng Project trước khi tạo Application:

```bash
kubectl apply -f phase2-helm-chart/argocd/project.yaml -n argocd
```

---

## Helm hooks và ArgoCD

Chart banking-demo có thể dùng Helm hooks (vd pre-install cho secret, postgres). Khi ArgoCD sync, nó thực chất chạy Helm (install/upgrade), nên **hooks vẫn được thực thi** theo thứ tự Helm. Lưu ý:

- ArgoCD mặc định không “chờ” hook xong theo cách bạn mong đợi nếu sync nhiều resource cùng lúc; với per-service + sync waves, thứ tự đã được điều khiển (namespace → infra → app) nên thường đủ.
- Nếu dùng hook có Job (vd migration), cần đảm bảo hook weight và wave để Job chạy đúng lúc; xem tài liệu ArgoCD về Helm hooks.

Trong repo, phần lớn thứ tự deploy được giải quyết bằng sync waves và bật/tắt component qua parameters, không phụ thuộc nặng vào hooks.

---

## Thực hành nhanh: từ cài ArgoCD đến sync

### 1. Cài ArgoCD (nếu chưa có)

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=Ready pods -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s
```

Lấy mật khẩu admin: `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d`. Port-forward UI: `kubectl port-forward svc/argocd-server -n argocd 8080:443`, mở https://localhost:8080.

### 2. Sửa repo URL

Sửa `repoURL` (và nếu cần `targetRevision`) trong `argocd/project.yaml` và trong `argocd/application.yaml` hoặc từng file trong `argocd/applications/` thành repo Git của bạn.

### 3. Deploy một Application (cách đơn giản)

```bash
kubectl apply -f phase2-helm-chart/argocd/project.yaml -n argocd
kubectl apply -f phase2-helm-chart/argocd/application.yaml -n argocd
```

Vào ArgoCD UI → Application `banking-demo` → **Sync**. Sau khi Synced & Healthy, kiểm tra: `kubectl get pods -n banking`.

### 4. Hoặc deploy per-service

```bash
kubectl apply -f phase2-helm-chart/argocd/project.yaml -n argocd
kubectl apply -f phase2-helm-chart/argocd/applications/ -n argocd
argocd app sync -l app.kubernetes.io/name=banking-demo
```

ArgoCD sẽ sync theo sync wave; đợi tất cả Synced rồi kiểm tra namespace `banking`.

### 5. Repo private

Nếu repo private: ArgoCD UI → Settings → Repositories → Connect Repo (URL + credential). Hoặc tạo Secret trong `argocd` chứa username/password hoặc SSH key và cấu hình theo tài liệu ArgoCD. Đảm bảo AppProject `sourceRepos` có repo đó.

---

## Mapping nhanh: Helm tay vs ArgoCD

| Helm tay (bài 4) | ArgoCD |
|------------------|--------|
| `helm template ... -f charts/common/values.yaml -f ...` | ArgoCD đọc `source.path` + `helm.valueFiles` và render tương đương |
| `helm install/upgrade` | Sync = ArgoCD apply kết quả render lên cluster |
| Đổi values rồi chạy lại `helm upgrade` | Sửa values trong Git → Sync Application |
| Nhiều env = nhiều file values, gọi helm với `-f` khác nhau | Nhiều Application (hoặc ApplicationSet) với valueFiles/parameters khác nhau |

---

## Lưu ý khi dùng

- **Mật khẩu**: Không commit mật khẩu production vào Git. Có thể dùng ArgoCD Helm parameters trỏ tới Secret, hoặc External Secrets / Sealed Secrets.
- **Sync policy**: Với production nhiều team, nên giữ sync thủ công hoặc auto với `prune: false` / `selfHeal: false` đến khi đã quen quy trình.
- **CreateNamespace**: Chỉ cần một Application có `CreateNamespace=true` (trong repo là banking-demo-namespace); các Application khác không cần để tránh conflict.
- **Shared resource**: Per-service dùng chung chart, mỗi app bật một phần; nhớ tắt namespace/secret ở mọi Application trừ namespace (tránh nhiều app cùng quản lý một Namespace/Secret).

Chi tiết troubleshooting (namespace stuck, postgres/redis không render, Payload Too Large khi xóa app…) xem trong repo: `phase2-helm-chart/argocd/ARGOCD.md`.

---

## Tóm tắt

- **GitOps**: Git là nguồn chân lý; ArgoCD đọc Git (chart + values) và đồng bộ lên cluster khi sync.
- **Application**: Khai báo repo, path chart, valueFiles (và parameters); destination namespace; sync policy.
- **Hai cách**: Một Application deploy cả chart (đơn giản) hoặc per-service Applications với sync waves (dễ quản lý từng phần).
- **ValueFiles**: Merge theo thứ tự; có thể thêm file theo môi trường (staging/production) hoặc dùng ApplicationSet.
- **Sync policy**: automated / prune / selfHeal tùy nhu cầu; CreateNamespace và ApplyOutOfSyncOnly hữu ích cho banking-demo.
- **AppProject**: Gom nhóm và giới hạn repo/namespace cho Application.

Bài tiếp theo sẽ đi vào **CI/CD**: pipeline build image, push registry, và (tùy chọn) cập nhật Helm values hoặc trigger ArgoCD sync khi có tag/commit mới.

---

## Bài tiếp theo

**Bài 6**: *Monitoring và Auto Scale (Phase 3)*

- Prometheus, Grafana, Loki, Tempo
- KEDA: scale theo Prometheus (RPS)
- Load test (k6) kiểm chứng scale

---

*Tags: #argocd #gitops #helm #kubernetes #devops #microservices*
