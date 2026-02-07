# Helm Hooks — Giải thích và ví dụ

## Helm Hook là gì?

**Helm hooks** cho phép bạn chạy **Job/Pod** trước hoặc sau khi Helm install/upgrade chart. Thay vì chạy migration thủ công, bạn đánh dấu Job là "hook" → Helm tự động chạy đúng thời điểm.

---

## Các loại Hook

| Hook Type | Khi nào chạy | Ví dụ dùng |
|-----------|--------------|------------|
| `pre-install` | Trước khi install lần đầu | Migration DB, tạo namespace |
| `post-install` | Sau khi install xong | Gửi notification, smoke test (xem [README.md](./README.md#smoke-test-tùy-chọn)) |
| `pre-upgrade` | Trước khi upgrade | **Migration DB** (quan trọng!) |
| `post-upgrade` | Sau khi upgrade | Verify health, cleanup |
| `pre-delete` | Trước khi uninstall | Backup data |
| `post-delete` | Sau khi uninstall | Cleanup external resources |

---

## Cách dùng (annotation)

Thêm annotation vào metadata của Job/Pod:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration
  annotations:
    helm.sh/hook: pre-upgrade,pre-install  # Chạy trước upgrade/install
    helm.sh/hook-weight: "-5"              # Thứ tự (số nhỏ = chạy sớm)
    helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded
```

### `helm.sh/hook-weight`

- Số **âm** = chạy **trước** các resource thường (Deployment, Service)
- Số **dương** = chạy **sau** các resource thường
- Ví dụ: `-10` chạy trước `-5`, `-5` chạy trước `0`

### `helm.sh/hook-delete-policy`

- `before-hook-creation`: Xóa Job cũ trước khi tạo Job mới (tránh conflict tên)
- `hook-succeeded`: Xóa Job khi thành công
- `hook-failed`: Giữ lại Job khi fail (để debug)

---

## Ví dụ: Migration DB cho v2 (Phase 4)

### 1. Tạo Job template trong Helm chart

File: `phase2-helm-chart/banking-demo/templates/db-migration-job.yaml`

```yaml
{{- if .Values.dbMigration.enabled }}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "banking-demo.fullname" . }}-db-migration
  namespace: {{ include "banking-demo.namespace" . }}
  annotations:
    # Hook: chạy TRƯỚC khi upgrade/install
    helm.sh/hook: pre-upgrade,pre-install
    helm.sh/hook-weight: "-10"  # Chạy rất sớm (trước Secret, trước Deployment)
    helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded
  labels:
    {{- include "banking-demo.labels" . | nindent 4 }}
    app.kubernetes.io/component: migration
spec:
  backoffLimit: 2  # Retry tối đa 2 lần nếu fail
  template:
    metadata:
      labels:
        {{- include "banking-demo.labels" . | nindent 8 }}
        app.kubernetes.io/component: migration
    spec:
      restartPolicy: Never
      containers:
      - name: migrate
        image: {{ .Values.dbMigration.image | default "postgres:15-alpine" }}
        command:
          - /bin/sh
          - -c
          - |
            set -e
            echo "Running migration for v2 (add phone + account_number)..."
            
            # Kết nối DB và chạy SQL
            PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<EOF
            -- Step 1: Add columns (nullable, chưa unique)
            ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS account_number VARCHAR(20);
            
            -- Step 2: Backfill account_number cho user cũ (nếu chưa có)
            DO \$\$
            DECLARE
              r RECORD;
              candidate TEXT;
            BEGIN
              FOR r IN SELECT id FROM users WHERE account_number IS NULL LOOP
                LOOP
                  candidate := lpad((floor(random()*1e12))::bigint::text, 12, '0');
                  EXIT WHEN NOT EXISTS (SELECT 1 FROM users WHERE account_number = candidate);
                END LOOP;
                UPDATE users SET account_number = candidate WHERE id = r.id;
              END LOOP;
            END \$\$;
            
            -- Step 3: Add unique index (concurrently nếu có thể)
            CREATE UNIQUE INDEX IF NOT EXISTS users_account_number_uq
            ON users(account_number)
            WHERE account_number IS NOT NULL;
            
            CREATE UNIQUE INDEX IF NOT EXISTS users_phone_uq
            ON users(phone)
            WHERE phone IS NOT NULL;
            
            SELECT 'Migration completed successfully' AS status;
            EOF
            
            echo "Migration done!"
        env:
        - name: POSTGRES_HOST
          value: {{ .Values.postgres.serviceName | default "postgres" }}
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: {{ include "banking-demo.secretName" . }}
              key: POSTGRES_USER
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: {{ include "banking-demo.secretName" . }}
              key: POSTGRES_PASSWORD
        - name: POSTGRES_DB
          valueFrom:
            secretKeyRef:
              name: {{ include "banking-demo.secretName" . }}
              key: POSTGRES_DB
{{- end }}
```

### 2. Thêm vào `values.yaml`

```yaml
# values.yaml
dbMigration:
  enabled: true  # Bật migration hook
  image: postgres:15-alpine  # Image chứa psql
```

### 3. Khi deploy

```bash
# Helm tự động:
# 1. Chạy migration Job (pre-upgrade hook)
# 2. Đợi Job thành công
# 3. Mới deploy Deployment mới (v2)

helm upgrade banking-demo ./banking-demo \
  --set dbMigration.enabled=true \
  --set auth-service.image.tag=v2 \
  -n banking
```

---

## Luồng hoạt động khi `helm upgrade`

```
1. Helm parse templates
2. Tìm resources có annotation helm.sh/hook
3. Chạy hooks theo weight (âm → dương)
   ├─ hook-weight: -10 → db-migration Job
   ├─ hook-weight: -8  → Secret (nếu có)
   └─ hook-weight: 0   → Deployment, Service (resources thường)
4. Đợi hook thành công (nếu fail → dừng upgrade)
5. Deploy resources còn lại
```

---

## Lưu ý quan trọng

### 1. Hook chạy **mỗi lần** upgrade

Nếu migration đã chạy rồi, bạn cần:

- **Option A**: Check trong SQL `IF NOT EXISTS` (như ví dụ trên)
- **Option B**: Tắt hook sau lần đầu: `--set dbMigration.enabled=false`
- **Option C**: Dùng flag trong Job để skip nếu đã migrate

### 2. Hook fail → upgrade dừng

Nếu migration Job fail, Helm sẽ **dừng upgrade** và giữ nguyên version cũ. Đây là **tính năng tốt** (tránh deploy code mới khi DB chưa sẵn sàng).

### 3. Debug hook

```bash
# Xem Job hook
kubectl get jobs -n banking | grep migration

# Xem logs
kubectl logs -n banking job/banking-demo-db-migration-xxxxx

# Xem Pod của hook
kubectl get pods -n banking -l app.kubernetes.io/component=migration
```

---

## So sánh: Hook vs Manual

| Cách | Ưu | Nhược |
|------|-----|-------|
| **Helm Hook** | Tự động, không quên, rollback dễ | Phức tạp hơn một chút |
| **Manual** (chạy Job riêng) | Đơn giản, control tốt | Dễ quên, dễ sai thứ tự |

**Khuyến nghị**: Dùng Helm hook cho migration (production), manual chỉ khi test/dev.

---

## Ví dụ thực tế trong project

Bạn đã thấy hook trong `secret.yaml`:

```yaml
annotations:
  helm.sh/hook: pre-install,pre-upgrade
  helm.sh/hook-weight: "-8"
```

→ Secret được tạo **trước** Deployment (để Deployment có thể mount Secret).
