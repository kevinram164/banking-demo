# Kong Security Plugins (Phase 7)

Mục tiêu: dùng các plugin có sẵn của **Kong** để tăng bảo mật cho API mà không phải sửa nhiều code.

## 1. Các plugin khuyến nghị

### 1.1. `rate-limiting`

Giới hạn số request trong 1 khoảng thời gian (theo IP/consumer).

Ví dụ (demo): tối đa **300 request/phút** trên mỗi client cho public API.

### 1.2. `request-size-limiting`

Chặn request body quá lớn (bảo vệ API khỏi payload "bắn phá").

Ví dụ: giới hạn **10MB** per request.

### 1.3. `correlation-id`

Thêm header `X-Correlation-ID` vào request/response để trace log/traces end-to-end.

Giúp:
- log backend, log Kong, traces trong Tempo trùng 1 id → dễ debug.

## 2. Cấu hình trong values (Phase 2 chart hoặc chart Kong riêng)

File: `phase2-helm-chart/banking-demo/charts/kong/values.yaml` (hoặc chart Kong riêng sau Phase 5) đã có:

```yaml
kong:
  extraPlugins: []
```

Bạn có thể enable plugin global (áp dụng cho mọi service) bằng cách set:

```yaml
kong:
  extraPlugins:
    - name: rate-limiting
      config:
        minute: 300
        policy: local
    - name: request-size-limiting
      config:
        allowed_payload_size: 10  # MB
        require_content_length: true
    - name: correlation-id
      config:
        header_name: X-Correlation-ID
        generator: uuid
        echo_downstream: true
```

Template tương ứng: `templates/kong-configmap.yaml` sẽ render `plugins:` cho từng service với `extraPlugins` này.

## 3. Áp dụng theo service (nếu muốn granular hơn)

Hiện tại chart đang apply chung 1 set plugin cho mọi backend. Nếu muốn granular hơn (VD auth chặt hơn, notification lỏng hơn), bạn có 2 option:

1. Dùng **nhiều `backends` block** với plugin riêng (phức tạp hơn trong chart).
2. Hoặc chấp nhận 1 policy chung (đủ tốt cho demo).

Cho Phase 7 demo, policy chung là đủ:

- Auth bị rate-limit = tốt (bảo vệ login).
- Transfer bị request-size-limit = tốt (body nhỏ).
- Notification cũng hưởng chung không sao.

## 4. Check cách plugin hoạt động

Sau khi apply:

```bash
kubectl -n banking get configmap kong-config -o yaml
```

(Kong có thể ở ns `kong` sau Phase 5 – kiểm tra đúng namespace.)

Kiểm tra trong phần `data.kong.yml`:

- `services[].plugins` chứa `rate-limiting`, `request-size-limiting`, `correlation-id`.

Test nhanh rate-limit:

```bash
for i in $(seq 1 400); do
  curl -s -o /dev/null -w "%{http_code}\n" http://<ingress>/api/auth/health
done
```

Kỳ vọng:
- ~300 request đầu: 200
- sau đó: 429 (Too Many Requests).

## 5. Liên kết với Observability (Phase 3)

Kết hợp với Phase 3:

- `correlation-id` giúp tìm 1 request qua:
  - log Kong
  - log service (qua Loki)
  - trace (Tempo)
- `rate-limiting` + metrics KEDA giúp bạn mô tả câu chuyện "bảo vệ API + autoscale".
