# Vault + External Secrets — Phase 9

Thay `kubectl create secret` thủ công (Phase 8 README) bằng sync từ Vault.

## Vault paths (KV v2)

```text
secret/banking/db          → banking-db-secret (ns banking)
secret/banking/rabbitmq    → rabbitmq-connection-secret (ns banking)
secret/rabbitmq/admin      → rabbitmq-secret (ns rabbit)
secret/platform/harbor     → harbor-registry dockerconfigjson
secret/platform/jenkins    → credential Jenkins (webhook / git push)
```

---

## Hướng dẫn Vault CLI — tạo path và secret

### 1. Khái niệm path (KV v2)

Trong Vault, một **secret** gồm hai phần:

| Thành phần | Ví dụ | Ý nghĩa |
|------------|-------|---------|
| **Mount path** (engine) | `secret` | Tên KV secrets engine đã bật |
| **Secret path** | `banking/db` | Đường dẫn logic bên trong mount |

Đường dẫn đầy đủ khi ghi/đọc:

```text
secret/banking/db
 └─┬──┘ └────┬────┘
 mount    secret path
```

- **KV v2** lưu nhiều **version** cho cùng một path; mỗi lần `kv put` tạo version mới.
- **External Secrets Operator** (ESO) trong repo này trỏ mount `secret`, version `v2` — xem `external-secrets/cluster-secret-store.yaml`.
- Trong `ExternalSecret`, field `remoteRef.key` là **secret path** (không gồm mount), ví dụ `banking/db` tương ứng Vault path `secret/banking/db`.

> **Lưu ý:** Với KV v2, CLI dùng lệnh `vault kv ...`. Không cần tạo “thư mục” trước — path được tạo tự động khi `kv put` lần đầu.

### 2. Vào pod Vault rồi dùng CLI (khuyến nghị)

Image Vault trên cluster đã có sẵn lệnh `vault` — **không cần** cài CLI trên máy local.

```bash
kubectl get pods -n vault
# NAME      READY   STATUS    RESTARTS   AGE
# vault-0   1/1     Running   0          ...

kubectl exec -it vault-0 -n vault -- sh
```

Trong shell của pod, set biến môi trường (dev mode k3d):

```sh
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'    # devRootToken trong Helm; production KHÔNG dùng root
vault status
```

> Server Vault chạy **cùng container** với CLI → `VAULT_ADDR` trỏ `127.0.0.1:8200`.

**Chạy một lệnh không cần vào shell tương tác:**

```bash
kubectl exec -n vault vault-0 -- sh -c \
  'export VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=root && vault kv get secret/banking/db'
```

**Cách khác (tùy chọn):** cài [Vault CLI](https://developer.hashicorp.com/vault/install) trên máy + `kubectl port-forward -n vault svc/vault 8200:8200` — chỉ khi bạn muốn chạy `vault` từ ngoài cluster.

### 4. Kiểm tra KV engine

Mount mặc định thường là `secret/` (KV v2):

```bash
vault secrets list
```

Kết quả mong đợi có dòng `secret/` với type `kv` (version 2). Nếu chưa có (cluster mới, chưa init engine):

```bash
vault secrets enable -path=secret kv-v2
```

### 5. Tạo secret — `vault kv put`

Các lệnh dưới đây chạy **trong pod** `vault-0` (sau `export VAULT_ADDR` / `VAULT_TOKEN` ở mục 2).

Cú pháp:

```bash
vault kv put <mount>/<secret-path> KEY1='value1' KEY2='value2'
```

#### 5.1 `secret/banking/db`

```bash
vault kv put secret/banking/db \
  DATABASE_URL='postgresql://banking:bankingpass@postgres.postgres.svc.cluster.local:5432/banking' \
  REDIS_URL='redis://redis.redis.svc.cluster.local:6379/0'
```

#### 5.2 `secret/banking/rabbitmq`

```bash
vault kv put secret/banking/rabbitmq \
  RABBITMQ_URL='amqp://banking:banking@rabbitmq.rabbit.svc.cluster.local:5672/'
```

#### 5.3 `secret/rabbitmq/admin`

```bash
vault kv put secret/rabbitmq/admin \
  username='banking' \
  password='banking'
```

#### 5.4 `secret/platform/harbor` (docker registry)

ESO thường map field `.dockerconfigjson`. Lưu nội dung JSON registry:

```bash
vault kv put secret/platform/harbor \
  .dockerconfigjson='{"auths":{"harbor-npd.co":{"username":"robot$k8s-pull","password":"ROBOT_TOKEN","auth":"BASE64_USER_PASS"}}}'
```

Lấy JSON từ máy local (ngoài pod), rồi `kv put` **trong pod**:

```bash
# trên máy local
kubectl get secret harbor-pull-creds -n platform -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d

# trong pod vault-0
vault kv put secret/platform/harbor .dockerconfigjson='<dán JSON ở trên>'
```

#### 5.5 `secret/platform/jenkins` — toàn bộ credential Jenkins

JCasC tạo ID `harbor-ci-push`, `github-gitops-push` từ secret này (không nhập tay trên UI).

```bash
vault kv put secret/platform/jenkins \
  admin_username='admin' \
  admin_password='YOUR_JENKINS_ADMIN_PASSWORD' \
  harbor_username='robot$banking-demo+ci-push' \
  harbor_password='HARBOR_ROBOT_TOKEN' \
  github_username='kevinram164' \
  github_pat='github_pat_xxxx' \
  github_webhook_secret='OPTIONAL_WEBHOOK_SECRET'
```

| Vault key | Jenkins dùng cho |
|-----------|------------------|
| `admin_username` / `admin_password` | Login UI (`jenkins-admin-user` / `jenkins-admin-password` trong K8s secret) |
| `harbor_username` / `harbor_password` | Credential `harbor-ci-push` (Kaniko) |
| `github_username` / `github_pat` | Credential `github-gitops-push` (push GitOps) |
| `github_webhook_secret` | (Tùy chọn) GitHub webhook |

Sau seed → ESO tạo secret `jenkins-platform-credentials` (ns `platform`) → Jenkins wave 2 đọc qua JCasC.

Đổi secret (rotate): `vault kv patch` → force-sync ExternalSecret → restart Jenkins:

```bash
kubectl annotate externalsecret jenkins-platform-credentials -n platform force-sync=$(date +%s) --overwrite
kubectl delete pod jenkins-0 -n platform
```

### 6. Đọc, liệt kê, sửa secret

(Lệnh `vault kv ...` — trong pod `vault-0`.)

**Đọc toàn bộ (metadata + data):**

```bash
vault kv get secret/banking/db
```

**Chỉ lấy một field:**

```bash
vault kv get -field=DATABASE_URL secret/banking/db
```

**Liệt kê path con (như `ls`):**

```bash
vault kv list secret/
vault kv list secret/banking/
```

**Ghi thêm/sửa field (giữ field cũ):**

```bash
vault kv patch secret/banking/db NEW_KEY='new-value'
```

**Xóa secret (toàn bộ versions tại path đó):**

```bash
vault kv metadata delete secret/banking/db
```

**Xóa một version cụ thể:**

```bash
vault kv delete -versions=1 secret/banking/db
```

**Xem lịch sử version:**

```bash
vault kv metadata get secret/banking/db
```

### 7. Seed nhanh toàn bộ path lab

Vào pod rồi chạy (hoặc copy block dưới sau khi `kubectl exec -it vault-0 -n vault -- sh`):

```sh
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'

vault kv put secret/banking/db \
  DATABASE_URL='postgresql://banking:bankingpass@postgres.postgres.svc.cluster.local:5432/banking' \
  REDIS_URL='redis://redis.redis.svc.cluster.local:6379/0'

vault kv put secret/banking/rabbitmq \
  RABBITMQ_URL='amqp://banking:bankingpass@rabbitmq.rabbit.svc.cluster.local:5672/'

vault kv put secret/rabbitmq/admin \
  username='banking' \
  password='bankingpass'

# harbor / jenkins: thay giá trị thật trước khi chạy
# vault kv put secret/platform/harbor .dockerconfigjson='...'
# vault kv put secret/platform/jenkins github_webhook_secret='...'
```

### 8. Map Vault → Kubernetes (ESO)

| Vault path | `remoteRef.key` | K8s Secret | Namespace |
|------------|-----------------|------------|-----------|
| `secret/banking/db` | `banking/db` | `banking-db-secret` | `banking` |
| `secret/banking/rabbitmq` | `banking/rabbitmq` | `rabbitmq-connection-secret` | `banking` |
| `secret/rabbitmq/admin` | `rabbitmq/admin` | `rabbitmq-secret` | `rabbit` |

Sau khi seed Vault, ESO đồng bộ theo `refreshInterval` (mặc định 1h) hoặc khi reconcile:

```bash
kubectl get externalsecret -A
kubectl get secret banking-db-secret -n banking
```

---

## Apply External Secrets (thứ tự quan trọng)

Làm **đúng thứ tự** sau — nếu đảo bước sẽ gặp `InvalidProviderConfig` hoặc `SecretSyncedError`:

### Bước 1 — Vault chạy + seed secret trong Vault

```bash
kubectl get pods -n vault    # vault-0 Running
kubectl exec -it vault-0 -n vault -- sh
# trong pod: export VAULT_ADDR + VAULT_TOKEN, rồi vault kv put ... (mục 7)
```

### Bước 2 — ESO controller chạy

```bash
kubectl get pods -n external-secrets
```

### Bước 3 — Tạo `vault-token` **trước** khi apply ClusterSecretStore

```bash
kubectl create secret generic vault-token \
  --from-literal=token=root \
  -n external-secrets
```

> `ClusterSecretStore` đọc token từ secret này. Nếu chưa có → ArgoCD/ESO báo  
> `InvalidProviderConfig: cannot get Kubernetes secret "vault-token": secrets "vault-token" not found`.

### Bước 4 — Namespace + apply manifest

```bash
kubectl create ns banking --dry-run=client -o yaml | kubectl apply -f -
kubectl create ns rabbit --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f phase9-gitops-platform/vault/external-secrets/
```

Hoặc qua ArgoCD: `platform-external-secrets` + `platform-external-secrets-config`.

### Bước 5 — Kiểm tra

```bash
kubectl get clustersecretstore vault-backend
# STATUS phải Valid / Ready

kubectl get externalsecret -A
# STATUS: SecretSynced, READY: True

kubectl get secret banking-db-secret -n banking
```

Force reconcile sau khi sửa `vault-token` hoặc seed Vault:

```bash
kubectl annotate clustersecretstore vault-backend \
  force-sync=$(date +%s) --overwrite

kubectl annotate externalsecret banking-db-secret -n banking \
  force-sync=$(date +%s) --overwrite
```

---

## Xử lý lỗi thường gặp

| Triệu chứng | Nguyên nhân | Cách sửa |
|-------------|-------------|----------|
| `InvalidProviderConfig` … `vault-token` not found | Apply `ClusterSecretStore` trước khi tạo secret | Tạo `vault-token` (bước 3), annotate `force-sync` |
| `SecretSyncedError`, READY `False` | Vault chưa có path tương ứng | Seed bằng `vault kv put` trong pod `vault-0` |
| `namespaces "rabbit" not found` | Thiếu namespace | `kubectl create ns rabbit` rồi apply lại |
| `banking-db-secret` not found | ESO chưa sync thành công | `kubectl describe externalsecret banking-db-secret -n banking` xem MESSAGE |

**Đọc lỗi chi tiết:**

```bash
kubectl describe clustersecretstore vault-backend
kubectl describe externalsecret banking-db-secret -n banking
kubectl logs -n external-secrets -l app.kubernetes.io/name=external-secrets --tail=50
```

**Test Vault từ trong cluster (secret đã seed chưa):**

```bash
kubectl exec -n vault vault-0 -- sh -c \
  'export VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=root && vault kv get secret/banking/db'
```

Nếu lệnh trên báo `No value found` → cần `vault kv put` trước; ESO không tự tạo secret trong Vault.

## ClusterSecretStore

Chỉnh `vault/server` và `auth` trong `cluster-secret-store.yaml` cho môi trường thật (Kubernetes auth recommended).
