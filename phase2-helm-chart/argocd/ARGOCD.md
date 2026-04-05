# Deploy banking-demo với ArgoCD (GitOps)

Hướng dẫn triển khai chart **banking-demo** bằng ArgoCD.

## 🚀 Cách đơn giản nhất (Khuyến nghị cho người mới)

**Chỉ cần 2 files:**
1. `project.yaml` - ArgoCD Project
2. `application.yaml` - ArgoCD Application (deploy tất cả services trong 1 dashboard)

Xem hướng dẫn chi tiết: [SIMPLE-DEPLOY.md](./SIMPLE-DEPLOY.md)

---

## 📋 Cách chuyên nghiệp (Per-service Applications)

Hướng dẫn triển khai chart **banking-demo** bằng ArgoCD theo cách chuyên nghiệp: cấu hình trong Git, sync thủ công, mỗi service một Application riêng để dễ quản lý.

---

## ⚠️ QUAN TRỌNG: ArgoCD phải connect với Git repo

**Nếu ArgoCD không liên kết với repo (Settings → Repositories → "No repositories connected"):**

1. **Vào ArgoCD UI → Settings → Repositories**
2. **Click "+ CONNECT REPO"**
3. **Điền thông tin:**
   - Type: Git
   - Project: banking-demo (hoặc để trống)
   - Repository URL: `https://github.com/kevinram164/banking-demo.git`
   - Username/Password: (nếu repo private)
4. **Click "CONNECT"**

**Hoặc đảm bảo AppProject có repo trong sourceRepos:**

```bash
# Kiểm tra AppProject
kubectl get appproject banking-demo -n argocd -o yaml | grep sourceRepos

# Nếu repo không có, thêm vào:
kubectl patch appproject banking-demo -n argocd --type merge \
  -p '{"spec":{"sourceRepos":["https://github.com/kevinram164/banking-demo.git"]}}'
```

**Lưu ý:** Nếu các services khác deploy được nhưng postgres/redis không, có thể:
- Các services đã được deploy từ trước khi repo bị disconnect
- Cần connect repo và sync lại tất cả Applications


---

## 🚀 Quick Start (Cho người mới)

Nếu bạn chưa biết ArgoCD là gì, làm theo các bước sau:

### Bước 1: Chuẩn bị ArgoCD

**1.1. Cài ArgoCD lên cluster (nếu chưa có):**

```bash
kubectl create namespace argocd
wget https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -n argocd -f install.yaml

# Đợi pods Running (khoảng 1-2 phút)
kubectl wait --for=condition=Ready pods -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s
```

**1.2. Lấy mật khẩu admin:**

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

**1.3. Truy cập ArgoCD UI:**

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Mở browser: `https://localhost:8080`
- User: `admin`
- Password: (lấy từ bước 1.2)

### Bước 2: Sửa repo URL trong các file

**2.1. Sửa Project (`argocd/project.yaml`):**

Mở file `argocd/project.yaml`, tìm dòng:
```yaml
sourceRepos:
  - https://github.com/kevinram164/banking-demo.git   # ← Đổi thành repo của bạn
```

**2.2. Sửa các Application (`argocd/applications/*.yaml`):**

Mở từng file trong `argocd/applications/`, tìm và sửa:
```yaml
source:
  repoURL: https://github.com/kevinram164/banking-demo.git  # ← Đổi thành repo của bạn
  targetRevision: main                                      # ← Đổi branch nếu cần
```

**Lưu ý:** Nếu repo là **private**, bạn cần cấu hình credential trong ArgoCD trước (xem mục 2.2 bên dưới).

### Bước 3: Deploy theo thứ tự

**Cách nhanh nhất (khuyến nghị):**

```bash
cd phase2-helm-chart/argocd

# Áp dụng Project + tất cả Applications cùng lúc
kubectl apply -f project.yaml -n argocd
kubectl apply -f applications/ -n argocd

# Hoặc dùng script (tự động apply project + applications)
# Linux/Mac:
chmod +x deploy-all.sh && ./deploy-all.sh
# Windows PowerShell:
.\deploy-all.ps1
```

**Hoặc từng bước (nếu muốn kiểm soát thứ tự):**

**3.1. Áp dụng Project (bắt buộc):**

```bash
cd phase2-helm-chart/argocd
kubectl apply -f project.yaml -n argocd
```

**3.2. Deploy Namespace và Secret:**

```bash
kubectl apply -f applications/namespace.yaml -n argocd
```

**3.3. Deploy Infrastructure (postgres, redis):**

```bash
kubectl apply -f applications/postgres.yaml -n argocd
kubectl apply -f applications/redis.yaml -n argocd
```

**Đợi infra sẵn sàng:**
- Vào ArgoCD UI → Application `banking-demo-namespace` → đợi status **Synced** và **Healthy**
- Hoặc kiểm tra: `kubectl get pods -n banking | grep -E "postgres|redis"`

**3.4. Deploy Kong API Gateway:**

```bash
kubectl apply -f applications/kong.yaml -n argocd
```

**3.5. Deploy các microservices:**

```bash
kubectl apply -f applications/auth-service.yaml -n argocd
kubectl apply -f applications/account-service.yaml -n argocd
kubectl apply -f applications/transfer-service.yaml -n argocd
kubectl apply -f applications/notification-service.yaml -n argocd
```

**3.6. Deploy Frontend và Ingress:**

```bash
kubectl apply -f applications/frontend.yaml -n argocd
kubectl apply -f applications/ingress.yaml -n argocd
```

**Hoặc apply tất cả cùng lúc (ArgoCD sẽ tự động deploy theo sync waves):**

```bash
kubectl apply -f applications/ -n argocd
```

### Bước 4: Sync từng Application

**Quan trọng:** Sau khi apply, ArgoCD **không tự động sync**. Bạn cần sync thủ công:

**✨ Sync Waves - Deploy tự động theo thứ tự:**

Tất cả Applications đã được cấu hình với **Sync Waves** (`argocd.argoproj.io/sync-wave`), cho phép ArgoCD tự động deploy theo thứ tự khi sync tất cả cùng lúc:

- **Wave -1:** `banking-demo-namespace` (namespace và secret) - Deploy đầu tiên nhất
- **Wave 0:** `banking-demo-postgres`, `banking-demo-redis` (infrastructure) - Deploy sau namespace
- **Wave 1:** `banking-demo-kong` (API Gateway) - Deploy sau infra
- **Wave 2:** Tất cả microservices (auth, account, transfer, notification) - Deploy song song sau kong
- **Wave 3:** `banking-demo-frontend` - Deploy sau microservices
- **Wave 4:** `banking-demo-ingress` - Deploy cuối cùng

**Cách 1: Sync tất cả cùng lúc (ArgoCD tự động deploy theo thứ tự) ⭐ Khuyến nghị**

```bash
# Sync tất cả cùng lúc - ArgoCD sẽ tự động deploy theo sync waves
argocd app sync -l app.kubernetes.io/name=banking-demo

# Hoặc qua UI: chọn tất cả Applications → Sync → Synchronize
```

ArgoCD sẽ tự động:
1. Sync Wave -1 trước (namespace và secret)
2. Đợi Wave -1 xong → Sync Wave 0 (postgres, redis - song song)
3. Đợi Wave 0 xong → Sync Wave 1 (kong)
4. Đợi Wave 1 xong → Sync Wave 2 (microservices - song song)
5. Đợi Wave 2 xong → Sync Wave 3 (frontend)
6. Đợi Wave 3 xong → Sync Wave 4 (ingress)

**Cách 2: Sync từng Application thủ công (nếu muốn kiểm soát chặt chẽ)**

```bash
# Sync từng service theo thứ tự
argocd app sync banking-demo-namespace
argocd app sync banking-demo-kong
argocd app sync banking-demo-auth-service
# ... tiếp tục với các service khác
```

**Cách 3: Qua UI (dễ nhất)**
1. Vào ArgoCD UI → Applications
2. Chọn tất cả Applications (checkbox) → **Sync** → **Synchronize**
3. ArgoCD sẽ tự động deploy theo sync waves

### Bước 5: Xử lý lỗi "namespace already exists"

**Nếu gặp lỗi:** `namespaces "banking" already exists`

**Nguyên nhân:** Nhiều Applications cùng có `CreateNamespace=true`, khiến ArgoCD cố tạo namespace nhiều lần.

**Giải pháp:**

1. **Xóa namespace cũ (nếu không có dữ liệu quan trọng):**
   ```bash
   kubectl delete namespace banking
   ```

2. **Hoặc chỉ giữ `CreateNamespace=true` cho infra:**
   - Chỉ `applications/infra.yaml` (wave 0) có `CreateNamespace=true`
   - Các Applications khác đã được cấu hình để **không** tạo namespace
   - Sync lại: `argocd app sync -l app.kubernetes.io/name=banking-demo`

**Lưu ý:** Sau khi sửa, chỉ Application `banking-demo-namespace` sẽ tạo namespace, các Applications khác sẽ sử dụng namespace đã tồn tại.

### Bước 6: Kiểm tra

**5.1. Kiểm tra trong ArgoCD UI:**
- Vào Applications → bạn sẽ thấy 8 Application riêng
- Mỗi Application có status: **Synced** (màu xanh) = đã deploy thành công

**5.2. Kiểm tra pods:**
```bash
kubectl get pods -n banking
```

Bạn sẽ thấy:
- `postgres-0`, `redis-0` (infra)
- `kong-xxx` (kong)
- `auth-service-xxx`, `account-service-xxx`, ... (microservices)
- `frontend-xxx` (frontend)

**5.3. Kiểm tra ingress:**
```bash
kubectl get ingress -n banking
```

Truy cập ứng dụng qua hostname trong ingress (vd: `npd-banking.co`).

---

## 🎯 Các cách apply một lần (Project + tất cả Applications)

Có **4 cách** để apply Project và tất cả Applications cùng lúc:

### Cách 1: Dùng kubectl apply với thư mục (Đơn giản nhất)

```bash
cd phase2-helm-chart/argocd

# Apply Project
kubectl apply -f project.yaml -n argocd

# Apply tất cả Applications
kubectl apply -f applications/ -n argocd
```

**Ưu điểm:** Đơn giản, không cần tool thêm  
**Nhược điểm:** Phải chạy 2 lệnh

### Cách 2: Dùng Script (Tự động hóa)

**Linux/Mac:**
```bash
cd phase2-helm-chart/argocd
chmod +x deploy-all.sh
./deploy-all.sh
```

**Windows PowerShell:**
```powershell
cd phase2-helm-chart\argocd
.\deploy-all.ps1
```

**Ưu điểm:** Tự động apply project + applications, có thông báo rõ ràng  
**Nhược điểm:** Cần quyền execute script

### Cách 3: Dùng ApplicationSet (Tự động tạo Applications - Tùy chọn)

```bash
cd phase2-helm-chart/argocd

# Sửa repoURL trong application-set-all-services.yaml trước
kubectl apply -f application-set-all-services.yaml -n argocd
```

**Ưu điểm:** Tự động tạo tất cả Applications từ một file, dễ maintain  
**Nhược điểm:** Cần hiểu ApplicationSet syntax

**Lưu ý:** 
- `application.yaml` và `application-set.yaml` đã bị xóa vì gây conflict với per-service Applications
- ApplicationSet sẽ tự động tạo các Applications với Sync Waves đã cấu hình. Khi sync tất cả cùng lúc, ArgoCD sẽ tự động deploy theo thứ tự (namespace → postgres/redis → kong → services → frontend → ingress).

---

## 🔄 Sync Waves - Deploy tự động theo thứ tự

ArgoCD hỗ trợ **Sync Waves** để tự động deploy Applications theo thứ tự phụ thuộc. Mỗi Application có annotation `argocd.argoproj.io/sync-wave` để định nghĩa thứ tự deploy.

### Cách hoạt động

- **Wave số nhỏ hơn** sẽ được sync **trước**
- ArgoCD sẽ **đợi** wave hiện tại hoàn thành trước khi sync wave tiếp theo
- Các Applications cùng wave sẽ được sync **song song**

### Thứ tự Sync Waves trong banking-demo

| Wave | Applications | Mô tả |
|------|-------------|-------|
| **-1** | `banking-demo-namespace` | Namespace và Secret - Deploy đầu tiên nhất |
| **0** | `banking-demo-postgres`<br>`banking-demo-redis` | Infrastructure (postgres, redis) - Deploy song song sau namespace |
| **1** | `banking-demo-kong` | API Gateway - Deploy sau infra |
| **2** | `banking-demo-auth-service`<br>`banking-demo-account-service`<br>`banking-demo-transfer-service`<br>`banking-demo-notification-service` | Microservices - Deploy song song sau kong |
| **3** | `banking-demo-frontend` | Frontend - Deploy sau microservices |
| **4** | `banking-demo-ingress` | Ingress - Deploy cuối cùng |

### Ví dụ sử dụng

**Sync tất cả cùng lúc:**
```bash
argocd app sync -l app.kubernetes.io/name=banking-demo
```

ArgoCD sẽ tự động:
1. ✅ Sync Wave -1 (namespace và secret) → đợi xong
2. ✅ Sync Wave 0 (postgres, redis - song song) → đợi xong
3. ✅ Sync Wave 1 (kong) → đợi xong
4. ✅ Sync Wave 2 (microservices - song song) → đợi xong
5. ✅ Sync Wave 3 (frontend) → đợi xong
6. ✅ Sync Wave 4 (ingress)

**Xem sync waves trong UI:**
- Vào ArgoCD UI → Applications
- Mỗi Application sẽ hiển thị sync wave trong metadata

**Tùy chỉnh sync wave:**
Sửa annotation trong file Application:
```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "2"  # Thay đổi số này
```

---

## 📋 Giải thích chi tiết

### Tại sao deploy riêng từng service?

**Vấn đề với cách cũ (1 Application cho tất cả):**
- ❌ Khó quản lý: tất cả services chung một dashboard
- ❌ Khó troubleshoot: không biết service nào lỗi
- ❌ Sync/rollback ảnh hưởng tất cả services
- ❌ Tự động xóa/tạo lại khi push commit (nếu bật `prune: true`)

**Lợi ích với cách mới (mỗi service một Application):**
- ✅ Dễ quản lý: mỗi service có dashboard riêng
- ✅ Dễ troubleshoot: biết chính xác service nào lỗi
- ✅ Sync/rollback độc lập: chỉ ảnh hưởng service đó
- ✅ An toàn: không tự động xóa/tạo lại (`prune: false`)

### Tại sao phải deploy theo thứ tự?

1. **Infra trước** (postgres, redis): Các service khác cần database và cache
2. **Kong tiếp theo**: API Gateway cần sẵn sàng để route requests
3. **Microservices**: Có thể deploy song song sau khi infra và kong đã sẵn sàng
4. **Frontend và Ingress cuối**: Cần các backend services đã chạy

Nếu deploy không đúng thứ tự, các service sẽ lỗi vì không tìm thấy dependencies.

---

## 📁 Cấu trúc thư mục

```
phase2-helm-chart/
├── argocd/
│   ├── project.yaml                   # ArgoCD Project (gom nhóm, giới hạn repo/namespace)
│   ├── application-set-all-services.yaml # ApplicationSet — tự động tạo tất cả Applications (tùy chọn)
│   ├── cleanup-and-fix.sh             # Script cleanup và fix toàn bộ phase 2
│   ├── cleanup-and-fix.ps1            # Script PowerShell cleanup và fix
│   ├── deploy-all.sh                  # Script bash — apply project + applications
│   ├── deploy-all.ps1                 # Script PowerShell — apply project + applications
│   ├── applications/                  # Applications riêng cho từng service (KHuyẾN NGHỊ)
│   │   ├── namespace.yaml             # Namespace và Secret (wave -1)
│   │   ├── postgres.yaml              # PostgreSQL (wave 0)
│   │   ├── redis.yaml                 # Redis (wave 0)
│   │   ├── kong.yaml                  # Kong API Gateway (wave 1)
│   │   ├── auth-service.yaml          # Auth Service (wave 2)
│   │   ├── account-service.yaml       # Account Service (wave 2)
│   │   ├── transfer-service.yaml      # Transfer Service (wave 2)
│   │   ├── notification-service.yaml  # Notification Service (wave 2)
│   │   ├── frontend.yaml              # Frontend (wave 3)
│   │   └── ingress.yaml              # Ingress (wave 4)
│   ├── scripts/                       # Scripts hỗ trợ (fix, check, delete)
│   │   ├── fix-namespace-pending-deletion.sh
│   │   ├── fix-secret-finalizers.sh
│   │   ├── check-postgres-redis-resources.sh
│   │   └── delete-application-large-payload.sh
│   │   ├── namespace.yaml             # Namespace và Secret
│   │   ├── postgres.yaml              # PostgreSQL Database
│   │   ├── redis.yaml                 # Redis Cache
│   │   ├── kong.yaml                  # Kong API Gateway
│   │   ├── auth-service.yaml          # Auth Service
│   │   ├── account-service.yaml       # Account Service
│   │   ├── transfer-service.yaml      # Transfer Service
│   │   ├── notification-service.yaml  # Notification Service
│   │   ├── frontend.yaml              # Frontend
│   │   ├── ingress.yaml               # Ingress
│   │   └── README.md                  # Hướng dẫn deploy
│   └── ARGOCD.md                      # File này
└── banking-demo/
    ├── Chart.yaml
    ├── values.yaml                    # Không chứa cấu hình (chỉ comment); mọi giá trị trong charts/
    ├── templates/                     # Templates chung cho tất cả services
    └── charts/                        # Values riêng cho từng service
        ├── common/                    # global, namespace, secret, ingress
        │   ├── Chart.yaml
        │   └── values.yaml
        ├── postgres/
        │   ├── Chart.yaml
        │   └── values.yaml
        ├── redis/
        ├── kong/
        ├── auth-service/
        ├── account-service/
        ├── transfer-service/
        ├── notification-service/
        └── frontend/
```

---

## 🔧 Chi tiết từng bước

### 1. Nguyên tắc GitOps với ArgoCD

- **Nguồn chân lý là Git**: Chart và values nằm trong repo; ArgoCD đọc Git và áp dụng lên cluster.
- **Không cài Helm tay**: `helm install`/`helm upgrade` do ArgoCD thực hiện khi bạn sync.
- **Sync thủ công**: Mặc định không tự động sync để tránh xóa/tạo lại không mong muốn.

### 2. Chuẩn bị

#### 2.1. Cài ArgoCD lên cluster

Xem **Bước 1** trong Quick Start ở trên.

#### 2.2. Repo Git phải được ArgoCD truy cập được

**Repo public:**
- ArgoCD clone không cần cấu hình thêm.
- Chỉ cần sửa `repoURL` trong các Application files.

**Repo private:**
1. Tạo Secret chứa credential:

```bash
# Với HTTPS (user/password)
kubectl create secret generic gitlab-repo-cred \
  -n argocd \
  --from-literal=url=https://gitlab.com/kiettt164/banking-demo.git \
  --from-literal=username=YOUR_USERNAME \
  --from-literal=password=YOUR_PASSWORD

# Hoặc với SSH key
kubectl create secret generic gitlab-repo-ssh \
  -n argocd \
  --from-file=sshPrivateKey=/path/to/id_rsa \
  --from-file=known_hosts=/path/to/known_hosts
```

2. Khai báo trong Application:

```yaml
spec:
  source:
    repoURL: https://gitlab.com/kiettt164/banking-demo.git
    # ArgoCD tự động dùng secret nếu tên khớp pattern
```

Xem thêm: [ArgoCD Private Repositories](https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories/)

---

## 3. Deploy riêng từng service (Khuyến nghị)

### 3.1. Các Application files

Trong thư mục `argocd/applications/` có 8 Application files:

| File | Service | Mô tả |
|------|---------|-------|
| `namespace.yaml` | Namespace & Secret | Namespace và Secret |
| `postgres.yaml` | Database | PostgreSQL Database |
| `redis.yaml` | Cache | Redis Cache |
| `kong.yaml` | Kong API Gateway | API Gateway, routing |
| `auth-service.yaml` | Auth Service | Authentication, login/register |
| `account-service.yaml` | Account Service | User account, balance |
| `transfer-service.yaml` | Transfer Service | Money transfer |
| `notification-service.yaml` | Notification Service | Real-time notifications (WebSocket) |
| `frontend.yaml` | Frontend | React UI |
| `ingress.yaml` | Ingress | HAProxy Ingress, external access |

### 3.2. Thứ tự deploy

**Quan trọng:** Phải deploy theo thứ tự này để tránh lỗi dependency:

```bash
# 1. Infrastructure (namespace, secret, postgres, redis)
kubectl apply -f applications/namespace.yaml -n argocd
kubectl apply -f applications/postgres.yaml -n argocd
kubectl apply -f applications/redis.yaml -n argocd
# Đợi sync xong và pods Running

# 2. Kong API Gateway
kubectl apply -f applications/kong.yaml -n argocd
# Đợi sync xong

# 3. Microservices (có thể deploy song song)
kubectl apply -f applications/auth-service.yaml -n argocd
kubectl apply -f applications/account-service.yaml -n argocd
kubectl apply -f applications/transfer-service.yaml -n argocd
kubectl apply -f applications/notification-service.yaml -n argocd

# 4. Frontend và Ingress
kubectl apply -f applications/frontend.yaml -n argocd
kubectl apply -f applications/ingress.yaml -n argocd
```

**Hoặc apply tất cả cùng lúc:**

```bash
# Cách 1: Dùng kubectl apply với thư mục
kubectl apply -f applications/ -n argocd

# Cách 2: Dùng script (Linux/Mac)
chmod +x deploy-all.sh
./deploy-all.sh

# Cách 4: Dùng script (Windows PowerShell)
.\deploy-all.ps1
```

**Hoặc dùng ApplicationSet (tự động tạo tất cả Applications từ một file):**

```bash
# Sửa repoURL trong application-set-all-services.yaml trước
kubectl apply -f application-set-all-services.yaml -n argocd
```

Sau đó vào UI sync từng cái theo thứ tự: infra → kong → services → frontend → ingress.

### 3.3. Sync từng Application

**Qua UI (khuyến nghị):**
1. Vào ArgoCD UI → Applications
2. Click vào Application (vd: `banking-demo-namespace`)
3. Click nút **Sync** (mũi tên tròn)
4. Chọn **Synchronize** → **Synchronize**

**Qua CLI:**
```bash
# Login vào ArgoCD (lần đầu)
argocd login localhost:8080

# Sync từng service
argocd app sync banking-demo-namespace
argocd app sync banking-demo-kong
argocd app sync banking-demo-auth-service
argocd app sync banking-demo-account-service
argocd app sync banking-demo-transfer-service
argocd app sync banking-demo-notification-service
argocd app sync banking-demo-frontend
argocd app sync banking-demo-ingress

# Hoặc sync tất cả cùng lúc (theo label)
argocd app sync -l app.kubernetes.io/name=banking-demo
```

### 3.4. Kiểm tra status

**Trong ArgoCD UI:**
- Status **Synced** (màu xanh) = đã deploy thành công
- Status **OutOfSync** (màu vàng) = cần sync
- Status **Missing** (màu đỏ) = chưa sync hoặc lỗi

**Qua CLI:**
```bash
# Xem tất cả Applications
argocd app list

# Xem chi tiết một Application
argocd app get banking-demo-namespace

# Xem pods trong namespace banking
kubectl get pods -n banking
```

### 3.5. Lợi ích của cách này

- ✅ **Mỗi service có dashboard riêng**: Dễ theo dõi status từng service
- ✅ **Sync/rollback độc lập**: Chỉ ảnh hưởng service đó, không ảnh hưởng service khác
- ✅ **Dễ troubleshoot**: Biết chính xác service nào lỗi
- ✅ **An toàn**: Không tự động xóa/tạo lại khi push commit (`prune: false`, `selfHeal: false`)

---

## 3a. Deploy bằng một Application (Không khuyến nghị)

Nếu bạn muốn deploy tất cả services chung một Application (không khuyến nghị vì khó quản lý):

### Bước 1: Sửa Application cho đúng repo

Mở `argocd/application.yaml`, sửa:
- **spec.source.repoURL**: URL repo Git của bạn
- **spec.source.targetRevision**: Branch hoặc tag (vd: `main`)

### Bước 2: Áp dụng Application

```bash
kubectl apply -f argocd/application.yaml -n argocd
```

### Bước 3: Sync và kiểm tra

```bash
argocd app sync banking-demo
kubectl get pods -n banking
```

**Nhược điểm:**
- ❌ Tất cả services chung một dashboard → khó quản lý
- ❌ Sync/rollback ảnh hưởng tất cả services
- ❌ Khó troubleshoot khi có lỗi

---

## 4. Nhiều môi trường với ApplicationSet (Tùy chọn)

Để cùng một repo deploy **staging** và **production** (mỗi env một namespace):

1. Cài [ApplicationSet controller](https://argo-cd.readthedocs.io/en/stable/user-guide/application-set/) (có sẵn trên bản ArgoCD mới).
2. Sửa `argocd/application-set.yaml`: đổi `repoURL`, `targetRevision`, và danh sách `elements` (env, namespace) cho đúng.
3. Áp dụng:

   ```bash
   kubectl apply -f argocd/application-set.yaml -n argocd
   ```

Sẽ tạo ra hai Application: `banking-demo-staging`, `banking-demo-production`. Cả hai dùng cùng bộ values từ **charts/**; chỉ khác namespace.

---

## 4a. Dùng ArgoCD Project

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

Sửa `project.yaml`: thay `https://github.com/kevinram164/banking-demo.git` bằng repo thật. Nếu dùng nhiều repo (vd fork), thêm vào `sourceRepos`.

### Khai báo Application thuộc Project

Trong tất cả Application files (`applications/*.yaml`) đặt:

```yaml
spec:
  project: banking-demo
```

Nếu **chưa** tạo Project, đổi thành `project: default` để Application vẫn chạy. Khi đã apply `project.yaml`, dùng `project: banking-demo` để mọi app banking-demo nằm trong một Project, dễ quản lý và áp RBAC (vd chỉ team banking được sửa app trong project này).

---

## 5. Thực hành chuyên nghiệp

### 5.1. Values: chỉ dùng charts/ — cập nhật image với ArgoCD

**ArgoCD không dùng `values.yaml` ở folder gốc chart.** Toàn bộ cấu hình nằm trong **charts/**:

- **`charts/common/values.yaml`**: `global`, `namespace`, `secret`, `ingress` (cấu hình dùng chung).
- **`charts/<service>/values.yaml`**: từng component với một top-level key (`postgres:`, `redis:`, `kong:`, `auth-service:`, …).

**Cập nhật image (hoặc cấu hình theo service):**

- **Sửa trong `charts/<service>/values.yaml`**, ví dụ:
  - `charts/auth-service/values.yaml` → `auth-service.image.repository`, `auth-service.image.tag`
  - `charts/account-service/values.yaml` → `account-service.image.tag`
- Đổi namespace, secret, ingress → sửa **`charts/common/values.yaml`**.
- Push lên Git → Vào ArgoCD UI → Sync Application tương ứng → cluster dùng cấu hình mới.

**Cấu trúc file trong `charts/<service>/`:** Mỗi file có **một top-level key** trùng tên component (vd `auth-service:`, `postgres:`) vì template đọc `index .Values "auth-service"`. File `charts/common/values.yaml` chứa các key `global:`, `namespace:`, `secret:`, `ingress:`.

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

Trong các Application files (`applications/*.yaml`), sync policy được cấu hình:

```yaml
syncPolicy:
  automated:
    prune: false      # Không tự động xóa resources
    selfHeal: false   # Không tự động sửa drift
```

**Giải thích:**
- **`prune: false`**: Không tự động xóa resource trên cluster khi không còn trong chart. **An toàn** - tránh xóa nhầm khi push commit.
- **`selfHeal: false`**: Không tự động sửa drift (khi có người/kịch bản sửa tay trên cluster). **An toàn** - bạn kiểm soát khi nào sync.
- **Sync thủ công**: Bạn phải vào UI hoặc dùng CLI để sync khi cần.

Nếu muốn tự động sync khi push commit, đổi thành:
```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

**⚠️ Cảnh báo:** Với `prune: true`, nếu bạn xóa một service trong chart và push lên Git, ArgoCD sẽ **tự động xóa** service đó trên cluster. Chỉ bật khi bạn chắc chắn.

### 5.5. Namespace

- **CreateNamespace=true** trong syncOptions: ArgoCD tự tạo namespace đích nếu chưa có (vd: `banking`).
- Chart của banking-demo cũng có thể tạo namespace (trong templates); cần thống nhất một nơi (khuyến nghị: để ArgoCD tạo namespace đích, chart vẫn có thể giữ template namespace với `namespace.enabled`).

### 5.6. Thứ tự cài (Helm hooks)

Chart banking-demo dùng Helm hooks (namespace, secret, postgres/redis trước). ArgoCD khi sync sẽ chạy Helm upgrade/install, đảm bảo thứ tự hooks được tôn trọng.

---

## 6. Lệnh thường dùng

| Việc cần làm | Lệnh / thao tác |
|--------------|------------------|
| **Áp dụng Project** | `kubectl apply -f argocd/project.yaml -n argocd` |
| **Áp dụng tất cả Applications** | `kubectl apply -f argocd/applications/ -n argocd` |
| **Áp dụng một Application** | `kubectl apply -f argocd/applications/namespace.yaml -n argocd` |
| **Xem danh sách Applications** | `argocd app list` hoặc ArgoCD UI → Applications |
| **Xem trạng thái một Application** | `argocd app get banking-demo-namespace` hoặc ArgoCD UI |
| **Sync một Application** | `argocd app sync banking-demo-namespace` hoặc UI → Sync |
| **Sync tất cả Applications** | `argocd app sync -l app.kubernetes.io/name=banking-demo` |
| **Hard refresh (bỏ cache Git)** | `argocd app get banking-demo-namespace --refresh` hoặc UI Refresh |
| **Xóa một Application** | `kubectl delete application banking-demo-namespace -n argocd` |
| **Xóa Application (payload lớn)** | `kubectl delete application <app-name> -n argocd --cascade=false` hoặc dùng script `delete-application-large-payload.sh` |
| **Xem pods** | `kubectl get pods -n banking` |
| **Xem logs một service** | `kubectl logs -n banking <pod-name>` |

---

## 7. Troubleshooting

### 7.1. Lỗi "namespace already exists"

**Triệu chứng:**
```
SyncError: namespaces "banking" already exists (retried 3 times)
```

**Nguyên nhân:**
- Nhiều Applications cùng có `CreateNamespace=true` trong `syncOptions`
- Khi sync tất cả cùng lúc, các Applications đều cố tạo namespace → conflict

**Giải pháp:**

**Cách 1: Xóa namespace và sync lại (nếu không có dữ liệu quan trọng)**
```bash
kubectl delete namespace banking
argocd app sync -l app.kubernetes.io/name=banking-demo
```

**Cách 2: Chỉ namespace tạo namespace (đã được cấu hình sẵn)**
- Chỉ `applications/namespace.yaml` (wave -1) có `CreateNamespace=true`
- Các Applications khác đã bỏ `CreateNamespace=true`
- Sync lại: `argocd app sync -l app.kubernetes.io/name=banking-demo`

**Kiểm tra:**
```bash
# Xem Applications nào đang có CreateNamespace=true
kubectl get applications -n argocd -o jsonpath='{range .items[*]}{.metadata.name}{": "}{.spec.syncPolicy.syncOptions}{"\n"}{end}'
```

**Lưu ý:** Sau khi sửa, chỉ Application `banking-demo-namespace` sẽ tạo namespace, các Applications khác sẽ sử dụng namespace đã tồn tại.

### 7.2. Namespace đang "Pending deletion"

**Triệu chứng:**
- Namespace hiển thị "Pending deletion" trong ArgoCD UI
- Lỗi: "Resource not found in cluster: undefined/undefined:banking"
- Applications không thể deploy vào namespace này

**Nguyên nhân:**
- Namespace đang bị xóa nhưng bị chặn bởi finalizers
- Có resources đang chặn việc xóa namespace

**Giải pháp:**

**Cách 1: Dùng script tự động (khuyến nghị)**

```bash
# Linux/Mac
chmod +x fix-namespace-pending-deletion.sh
./fix-namespace-pending-deletion.sh

# Windows PowerShell
.\fix-namespace-pending-deletion.ps1
```

**Cách 2: Xử lý thủ công (không cần jq)**

```bash
# Bước 1: Xóa finalizers bằng kubectl patch (đơn giản nhất)
kubectl patch namespace banking -p '{"metadata":{"finalizers":[]}}' --type=merge

# Hoặc dùng sed (nếu patch không work):
kubectl get namespace banking -o json | \
  sed 's/"finalizers": \[[^]]*\]/"finalizers": []/' | \
  kubectl replace --raw /api/v1/namespaces/banking/finalize -f -

# Hoặc dùng PowerShell:
kubectl patch namespace banking -p '{\"metadata\":{\"finalizers\":[]}}' --type=merge

# Bước 2: Đợi namespace bị xóa hoàn toàn
kubectl get namespace banking --watch

# Bước 3: Deploy lại namespace
kubectl apply -f applications/namespace.yaml -n argocd
argocd app sync banking-demo-namespace
```

**Cách 2b: Dùng script đơn giản (không cần jq)**

```bash
# Script mới không cần jq
chmod +x fix-namespace-pending-deletion-simple.sh
./fix-namespace-pending-deletion-simple.sh banking
```

**Cách 3: Xóa secret có finalizers (nếu secret đang chặn)**

Nếu secret `banking-db-secret` vẫn còn và không xóa được:

```bash
# Dùng script tự động
chmod +x fix-secret-finalizers.sh
./fix-secret-finalizers.sh banking banking-db-secret

# Hoặc PowerShell
.\fix-secret-finalizers.ps1 banking banking-db-secret

# Hoặc thủ công
# Bước 1: Xóa finalizers của secret
kubectl patch secret banking-db-secret -n banking -p '{"metadata":{"finalizers":[]}}' --type=merge

# Bước 2: Xóa secret
kubectl delete secret banking-db-secret -n banking --force --grace-period=0

# Bước 3: Xóa tất cả secrets trong namespace (nếu cần)
kubectl delete secrets --all -n banking --force --grace-period=0
```

**Cách 4: Force delete tất cả resources (nếu cách trên không work)**

```bash
# Xóa tất cả resources trong namespace trước
kubectl delete all --all -n banking --force --grace-period=0
kubectl delete secrets --all -n banking --force --grace-period=0
kubectl delete configmaps --all -n banking --force --grace-period=0
kubectl delete pvc --all -n banking --force --grace-period=0

# Sau đó xóa namespace
kubectl delete namespace banking --force --grace-period=0

# Deploy lại
kubectl apply -f applications/namespace.yaml -n argocd
argocd app sync banking-demo-namespace
```

### 7.3. Lỗi "infra.yaml không chạy"

**Triệu chứng:** Không tìm thấy file `infra.yaml` hoặc Application không chạy

**Nguyên nhân:**
- File `infra.yaml` đã được tách thành các file riêng:
  - `namespace.yaml` - Namespace và Secret (wave -1)
  - `postgres.yaml` - PostgreSQL (wave 0)
  - `redis.yaml` - Redis (wave 0)

**Giải pháp:**

```bash
# Deploy các file mới thay vì infra.yaml
kubectl apply -f applications/namespace.yaml -n argocd
kubectl apply -f applications/postgres.yaml -n argocd
kubectl apply -f applications/redis.yaml -n argocd

# Sync theo thứ tự
argocd app sync banking-demo-namespace
argocd app sync banking-demo-postgres
argocd app sync banking-demo-redis

# Hoặc sync tất cả cùng lúc (ArgoCD sẽ tự động deploy theo sync waves)
argocd app sync -l app.kubernetes.io/name=banking-demo
```

### 7.4. Lỗi "Payload Too Large" khi xóa Application

**Triệu chứng:**
- Lỗi "Unable to delete application: Payload Too Large" khi xóa Application qua UI
- Application có quá nhiều resources hoặc history

**Nguyên nhân:**
- Application quản lý quá nhiều resources
- ArgoCD UI có giới hạn payload size khi gửi request xóa

**Giải pháp:**

**Cách 1: Xóa qua CLI (khuyến nghị)**

```bash
# Linux/Mac
chmod +x delete-application-large-payload.sh
./delete-application-large-payload.sh banking-demo-infra

# Windows PowerShell
.\delete-application-large-payload.ps1 banking-demo-infra
```

**Cách 2: Xóa thủ công qua CLI**

```bash
# Xóa finalizers trước
kubectl patch application banking-demo-infra -n argocd \
  --type json \
  -p='[{"op": "remove", "path": "/metadata/finalizers"}]'

# Xóa Application với cascade=false (không xóa resources)
kubectl delete application banking-demo-infra -n argocd --cascade=false

# Hoặc xóa hoàn toàn (bao gồm resources)
kubectl delete application banking-demo-infra -n argocd
```

**Cách 3: Xóa Application cũ và tạo lại với file mới**

Vì `banking-demo-infra` đã được tách thành `namespace.yaml`, `postgres.yaml`, `redis.yaml`:

```bash
# Xóa Application cũ
kubectl delete application banking-demo-infra -n argocd --cascade=false

# Deploy các file mới
kubectl apply -f applications/namespace.yaml -n argocd
kubectl apply -f applications/postgres.yaml -n argocd
kubectl apply -f applications/redis.yaml -n argocd

# Sync
argocd app sync banking-demo-namespace
argocd app sync banking-demo-postgres
argocd app sync banking-demo-redis
```

**Lưu ý:** 
- `--cascade=false` chỉ xóa Application, không xóa resources trong cluster
- Nếu muốn xóa cả resources, bỏ `--cascade=false` hoặc xóa resources thủ công trước

### 7.5. Postgres/Redis không hiển thị resources

**Triệu chứng:**
- Application `banking-demo-postgres` và `banking-demo-redis` hiển thị "Healthy" và "Synced"
- Nhưng không có Kubernetes resources (Pod, StatefulSet, Service) được tạo ra
- Application Details Tree chỉ hiển thị Application node, không có resources con

**Nguyên nhân:**
- ArgoCD không render Helm templates đúng cách
- Values không được merge đúng giữa valueFiles và parameters
- Application cần hard refresh để reload templates

**Giải pháp:**

**Cách 1: Hard refresh và sync lại (thử trước)**

```bash
# Hard refresh Application để reload templates
argocd app get banking-demo-postgres --refresh
argocd app get banking-demo-redis --refresh

# Sync lại
argocd app sync banking-demo-postgres
argocd app sync banking-demo-redis
```

**Cách 2: Xem rendered templates trong ArgoCD**

```bash
# Xem templates được render như thế nào trong ArgoCD
argocd app manifests banking-demo-postgres

# Kiểm tra xem có resources nào được render không
argocd app manifests banking-demo-postgres | grep -E "kind:|name:"

# Đếm số resources
argocd app manifests banking-demo-postgres | grep -E "^kind:" | wc -l
```

**Cách 2b: Test Helm template local (giống như ArgoCD sẽ render)**

```bash
# Test postgres template (phải có --namespace để set đúng namespace)
cd phase2-helm-chart/banking-demo
helm template test . \
  --values charts/common/values.yaml \
  --values charts/postgres/values.yaml \
  --set namespace.enabled=false \
  --set secret.enabled=false \
  --set redis.enabled=false \
  --set kong.enabled=false \
  --set auth-service.enabled=false \
  --set account-service.enabled=false \
  --set transfer-service.enabled=false \
  --set notification-service.enabled=false \
  --set frontend.enabled=false \
  --set ingress.enabled=false \
  --namespace banking

# Kiểm tra namespace trong output (phải là "banking", không phải "default")
helm template test . \
  --values charts/common/values.yaml \
  --values charts/postgres/values.yaml \
  --set namespace.enabled=false \
  --set secret.enabled=false \
  --set redis.enabled=false \
  --set kong.enabled=false \
  --set auth-service.enabled=false \
  --set account-service.enabled=false \
  --set transfer-service.enabled=false \
  --set notification-service.enabled=false \
  --set frontend.enabled=false \
  --set ingress.enabled=false \
  --namespace banking | grep "namespace:"
```

**Cách 2c: Dùng debug script**

```bash
chmod +x debug-postgres-redis.sh
./debug-postgres-redis.sh
```

**Cách 3: Xóa và tạo lại Application**

```bash
# Xóa Application cũ
kubectl delete application banking-demo-postgres -n argocd --cascade=false
kubectl delete application banking-demo-redis -n argocd --cascade=false

# Apply lại
kubectl apply -f applications/postgres.yaml -n argocd
kubectl apply -f applications/redis.yaml -n argocd

# Sync
argocd app sync banking-demo-postgres
argocd app sync banking-demo-redis
```

**Cách 4: Kiểm tra values được merge**

```bash
# Xem values được merge
argocd app get banking-demo-postgres -o yaml | grep -A 20 "helm:"
```

**Kiểm tra sau khi fix:**

```bash
# Dùng script tự động (khuyến nghị)
chmod +x check-postgres-redis-resources.sh
./check-postgres-redis-resources.sh

# Hoặc PowerShell
.\check-postgres-redis-resources.ps1

# Hoặc thủ công
# Kiểm tra pods
kubectl get pods -n banking | grep -E "postgres|redis"

# Kiểm tra statefulsets
kubectl get statefulsets -n banking

# Kiểm tra services
kubectl get services -n banking | grep -E "postgres|redis"

# Kiểm tra ArgoCD rendered manifests
argocd app manifests banking-demo-postgres | grep -E "kind:|name:"
argocd app manifests banking-demo-redis | grep -E "kind:|name:"
```

**Nếu vẫn không có resources (Application Synced nhưng không có resources):**

**Cách 1: Xóa và tạo lại Applications (Khuyến nghị)**

```bash
# Script tự động xóa và tạo lại
chmod +x fix-postgres-redis-no-resources-v2.sh
./fix-postgres-redis-no-resources-v2.sh
```

**Cách 2: Hard refresh và sync thủ công**

```bash
# Hard refresh bằng kubectl (không cần ArgoCD CLI)
kubectl patch application banking-demo-postgres -n argocd --type merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
kubectl annotate application banking-demo-postgres -n argocd argocd.argoproj.io/refresh- 2>/dev/null || true

kubectl patch application banking-demo-redis -n argocd --type merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
kubectl annotate application banking-demo-redis -n argocd argocd.argoproj.io/refresh- 2>/dev/null || true

# Đợi ArgoCD refresh (10-15 giây)
sleep 15

# Sync lại trong ArgoCD UI hoặc đợi auto sync
```

**Cách 3: Debug chi tiết**

```bash
# Script debug để tìm nguyên nhân
chmod +x debug-argocd-render.sh
./debug-argocd-render.sh
```

**Cách 4: Kiểm tra ArgoCD controller logs**

```bash
# Xem logs của ArgoCD controller
ARGOCD_POD=$(kubectl get pods -n argocd -l app.kubernetes.io/name=argocd-application-controller -o jsonpath='{.items[0].metadata.name}')
kubectl logs -n argocd $ARGOCD_POD --tail=100 | grep -i -E "postgres|redis|error"
```

**Cách 5: Kiểm tra values được merge**

```bash
# Xem Application spec và status
kubectl get application banking-demo-postgres -n argocd -o yaml | grep -A 50 "spec:"
kubectl get application banking-demo-postgres -n argocd -o yaml | grep -A 30 "status:"
```

**Cách 6: Xem chi tiết lỗi trong ArgoCD UI:**
   - Vào Application → tab **EVENTS** hoặc **CONDITIONS**
   - Xem có lỗi gì không
   - Xem tab **MANIFESTS** để kiểm tra ArgoCD có render được không

**Lưu ý:**
- Đảm bảo namespace "banking" đã được tạo trước (bởi `namespace.yaml`)
- Đảm bảo secret "banking-db-secret" đã được tạo trước (bởi `namespace.yaml`)
- StorageClass "nfs-client" phải tồn tại trong cluster

### 7.6. SharedResourceWarning - Namespace/Secret được quản lý bởi nhiều Applications

**Triệu chứng:**
- Warning: "Namespace/banking is part of applications argocd/banking-demo-namespace and banking-demo-notification-service"
- Warning: "Secret/banking-db-secret is part of applications argocd/banking-demo-namespace and banking-demo-auth-service"
- Namespace cứ tạo ra là mất
- Postgres/Redis không deploy được

**Nguyên nhân:**
- `charts/common/values.yaml` có `namespace.enabled: true` và `secret.enabled: true`
- Khi các Applications khác dùng `charts/common/values.yaml`, Helm sẽ render namespace và secret từ templates
- Gây conflict khi nhiều Applications cùng quản lý cùng một resource

**Giải pháp (ĐÃ FIX):**

**✅ Tất cả Applications đã được cập nhật với `namespace.enabled=false` và `secret.enabled=false`**

Các file sau đã được fix:
- `applications/auth-service.yaml`
- `applications/notification-service.yaml`
- `applications/account-service.yaml`
- `applications/transfer-service.yaml`
- `applications/kong.yaml`
- `applications/frontend.yaml`
- `applications/ingress.yaml`
- `applications/postgres.yaml`
- `applications/redis.yaml`

**Nếu vẫn có SharedResourceWarning sau khi commit:**

```bash
# Dùng script tự động fix
chmod +x fix-shared-resource-warnings.sh
./fix-shared-resource-warnings.sh
```

Script sẽ:
1. Apply lại tất cả Applications
2. Hard refresh Applications
3. Sync lại theo đúng thứ tự
4. Kiểm tra manifests không có namespace/secret

**Hoặc fix thủ công:**

```bash
# 1. Apply lại Applications
kubectl apply -f applications/ -n argocd

# 2. Hard refresh
for app in banking-demo-namespace banking-demo-postgres banking-demo-redis \
           banking-demo-kong banking-demo-auth-service banking-demo-notification-service \
           banking-demo-account-service banking-demo-transfer-service \
           banking-demo-frontend banking-demo-ingress; do
  argocd app get $app --refresh 2>/dev/null || echo "$app không tồn tại"
done

# 3. Sync lại
argocd app sync banking-demo-namespace --timeout 300
sleep 5
argocd app sync banking-demo-postgres banking-demo-redis --timeout 300
```

**Kiểm tra:**

```bash
# Kiểm tra Application conditions (không còn SharedResourceWarning)
kubectl get application banking-demo-namespace -n argocd -o yaml | grep -A 10 "conditions:"

# Kiểm tra manifests không có namespace/secret (trừ namespace.yaml)
argocd app manifests banking-demo-auth-service | grep -E "kind: Namespace|kind: Secret"
# → Không nên có output

argocd app manifests banking-demo-notification-service | grep -E "kind: Namespace|kind: Secret"
# → Không nên có output
```

**Lưu ý:**
- ✅ Chỉ Application `banking-demo-namespace` (từ `namespace.yaml`) tạo namespace và secret
- ✅ Tất cả Applications khác đã có `namespace.enabled=false` và `secret.enabled=false` trong parameters
- ✅ ApplicationSet (`application-set-all-services.yaml`) cũng đã được cập nhật để tự động disable namespace/secret cho tất cả (trừ namespace)

### 7.7. Các lỗi khác

### 7.1. Application không sync

**Triệu chứng:** Status **OutOfSync** hoặc **Missing**

**Nguyên nhân và cách sửa:**
1. **Chưa sync thủ công**: Vào UI → Sync
2. **Repo URL sai**: Kiểm tra `repoURL` trong Application file
3. **Branch không tồn tại**: Kiểm tra `targetRevision` (vd: `main` có tồn tại không)
4. **Repo private chưa cấu hình credential**: Xem mục 2.2

### 7.2. Pod không start được

**Triệu chứng:** Pod status **CrashLoopBackOff** hoặc **Error**

**Kiểm tra:**
```bash
# Xem logs
kubectl logs -n banking <pod-name>

# Xem events
kubectl describe pod -n banking <pod-name>

# Kiểm tra dependencies (postgres, redis đã chạy chưa)
kubectl get pods -n banking
```

**Nguyên nhân thường gặp:**
- Postgres/Redis chưa sẵn sàng → Đợi infra sync xong
- Image không tồn tại → Kiểm tra `charts/<service>/values.yaml` → `image.repository` và `image.tag`
- Secret không tồn tại → Kiểm tra `charts/common/values.yaml` → `secret.enabled: true`

### 7.3. Service không kết nối được với database

**Triệu chứng:** Service chạy nhưng lỗi "connection refused" hoặc "database not found"

**Kiểm tra:**
```bash
# Kiểm tra postgres đã chạy chưa
kubectl get pods -n banking | grep postgres

# Kiểm tra secret có đúng không
kubectl get secret banking-db-secret -n banking -o yaml

# Kiểm tra env vars trong pod
kubectl exec -n banking <pod-name> -- env | grep DATABASE_URL
```

**Cách sửa:**
- Đảm bảo infra (postgres, redis) đã sync và pods Running
- Kiểm tra `charts/common/values.yaml` → `secret.databaseUrl` có đúng không

### 7.4. Ingress không hoạt động

**Triệu chứng:** Không truy cập được ứng dụng qua domain

**Kiểm tra:**
```bash
# Xem ingress
kubectl get ingress -n banking

# Xem ingress details
kubectl describe ingress banking-ingress -n banking

# Kiểm tra HAProxy Ingress controller
kubectl get pods -n haproxy-ingress
```

**Cách sửa:**
- Đảm bảo HAProxy Ingress controller đã cài
- Kiểm tra `charts/common/values.yaml` → `ingress.host` có đúng domain không
- Kiểm tra DNS trỏ về LoadBalancer IP của HAProxy

### 7.5. WebSocket không kết nối được

**Triệu chứng:** Browser console lỗi "WebSocket connection failed"

**Kiểm tra:**
- Ingress có annotations cho WebSocket chưa (đã có trong `templates/ingress.yaml`)
- Kong route `/ws` có đúng chưa (kiểm tra `charts/kong/values.yaml`)
- Notification service đã chạy chưa

**Cách sửa:**
- Sync lại ingress Application: `argocd app sync banking-demo-ingress`
- Kiểm tra Kong config: `kubectl get configmap kong-config -n banking -o yaml`

---

## 8. Tóm tắt

### Cách deploy khuyến nghị:

1. **Sửa repo URL** trong `project.yaml` và các file `applications/*.yaml`
2. **Áp dụng Project**: `kubectl apply -f argocd/project.yaml -n argocd`
3. **Deploy theo thứ tự**: infra → kong → services → frontend → ingress
4. **Sync thủ công** từng Application qua UI hoặc CLI
5. **Kiểm tra** status trong ArgoCD UI và pods trong namespace `banking`

### Lợi ích:

- ✅ **Mỗi service một dashboard riêng** → Dễ quản lý
- ✅ **Sync/rollback độc lập** → Không ảnh hưởng service khác
- ✅ **An toàn** → Không tự động xóa/tạo lại khi push commit
- ✅ **Dễ troubleshoot** → Biết chính xác service nào lỗi

### Cấu hình values:

- Toàn bộ values nằm trong **`charts/`** (common + từng service)
- Cập nhật image/config: sửa trong `charts/<service>/values.yaml` → push Git → sync Application
- Không dùng `values.yaml` ở folder gốc chart

Sau khi chỉnh repoURL, targetRevision và apply các Application files, sync từng Application trong ArgoCD để deploy banking-demo lên cluster.
