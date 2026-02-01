# Canary Deployment (Phase 6)

Canary: đưa **một phần traffic** sang version mới (canary). Nếu metrics ổn (error rate, latency) thì tăng dần % rồi promote; nếu lỗi thì rollback (giảm % hoặc tắt canary).

## 1. Ý tưởng

- **Stable**: version hiện tại (đa số traffic).
- **Canary**: version mới (ít traffic ban đầu, ví dụ 10%).
- **Traffic split**: Ingress hoặc Service Mesh chia % request sang canary.
- **Promote**: tăng dần % (10% → 50% → 100%) hoặc chuyển hết sang canary rồi xóa stable.
- **Rollback**: giảm % canary về 0 hoặc xóa canary Deployment.

Ưu điểm: phát hiện lỗi sớm trên một nhóm nhỏ user. Nhược: cần Ingress/controller hoặc tool hỗ trợ traffic split và (tùy chọn) analysis tự động.

## 2. Cách triển khai trên K8s

### 2.1. Ingress với traffic split (weight / header)

Nhiều Ingress controller hỗ trợ chia traffic:

- **HAProxy Ingress**: annotation `haproxy.org/balance` và dùng nhiều backend; hoặc dùng **snippet** / **route** để chia theo weight (tùy phiên bản).
- **NGINX Ingress**: có thể dùng **canary annotations**:
  - `nginx.ingress.kubernetes.io/canary: "true"`
  - `nginx.ingress.kubernetes.io/canary-weight: "20"` (20% traffic sang canary)
  - Hoặc `nginx.ingress.kubernetes.io/canary-by-header` để canary theo header (ví dụ `X-Canary: true` cho tester).

Ý tưởng: hai Deployment (stable + canary), hai Service. Ingress chính trỏ tới stable; thêm một Ingress (hoặc rule) với canary annotations trỏ tới Service canary, cùng host/path nhưng có weight/header.

Ví dụ NGINX Ingress canary (minh họa):

```yaml
# Ingress chính – stable
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: auth-service-stable
  namespace: banking
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  rules:
    - host: npd-banking.co
      http:
        paths:
          - path: /api/auth
            pathType: Prefix
            backend:
              service:
                name: auth-service-stable
                port: { number: 80 }
---
# Ingress canary – một phần traffic
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: auth-service-canary
  namespace: banking
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "10"
spec:
  rules:
    - host: npd-banking.co
      http:
        paths:
          - path: /api/auth
            pathType: Prefix
            backend:
              service:
                name: auth-service-canary
                port: { number: 80 }
```

Chỉnh `canary-weight` thành 0 để tắt canary; tăng dần 10 → 50 → 100 khi promote.

### 2.2. Argo Rollouts

[Argo Rollouts](https://argoproj.github.io/rollouts/) cung cấp CRD `Rollout` thay cho Deployment, hỗ trợ **Canary** (và Blue-Green) với bước weight tự động và **analysis** (Prometheus, Job) để promote/rollback tự động.

- Định nghĩa Rollout canary: steps 10% → 30% → 100%, mỗi bước chạy AnalysisTemplate (ví dụ query Prometheus error rate).
- Nếu analysis pass → bước tiếp; fail → rollback.

Phù hợp khi bạn đã dùng Argo CD (Phase 2) và Prometheus (Phase 3): rollout + SLO gắn chặt.

### 2.3. Flagger (Canary + Istio/Linkerd/NGINX/App Mesh)

[Flagger](https://docs.flagger.app/) tạo Canary resource, tích hợp với Prometheus/Grafana để phân tích và tự động promote hoặc rollback. Cần một trong các mesh/ingress được Flagger hỗ trợ.

## 3. Gắn với Phase 2 và Phase 3

- **Phase 2**: Chart banking-demo có một Deployment/Service mỗi app. Để canary:
  - Deploy thêm “canary” Deployment + Service (cùng app, khác label `version: canary` và image tag). Có thể qua Helm values: `canary.enabled: true`, `canary.image.tag: v2`.
  - Ingress: dùng canary annotations (nếu NGINX) hoặc cấu hình HAProxy tương ứng (Phase 2 đang dùng HAProxy có thể cần snippet hoặc route riêng).
- **Phase 3**: Prometheus scrape metrics từ cả stable và canary. Trong Argo Rollouts / Flagger, dùng Prometheus query (error rate, latency p99) làm điều kiện promote/rollback.

## 4. Ví dụ workflow Canary thủ công (Ingress weight)

1. Deploy **auth-service-canary** (image v2), Service **auth-service-canary**.
2. Bật Ingress canary với `canary-weight: "10"`.
3. Theo dõi Grafana/Phase 3: so sánh error rate, latency stable vs canary.
4. Nếu ổn: tăng weight 10 → 30 → 50 → 100. Nếu lỗi: set weight 0.
5. Khi 100% canary: có thể đổi tên/merge thành stable và xóa bản cũ.

## 5. Checklist Canary

1. [ ] Chọn cơ chế: Ingress canary (NGINX/HAProxy) hay Argo Rollouts/Flagger.
2. [ ] Thêm Canary Deployment + Service (hoặc Rollout resource) vào chart/values.
3. [ ] Cấu hình traffic split (weight hoặc header).
4. [ ] (Khuyến nghị) Cấu hình analysis từ Prometheus (Phase 3) nếu dùng Argo Rollouts/Flagger.
5. [ ] Chạy canary với % nhỏ; theo dõi metrics; tăng dần hoặc rollback.

## 6. Liên kết

- **Phase 2**: `phase2-helm-chart/banking-demo` – Ingress, Service; HAProxy Ingress có thể cần doc riêng cho weight.
- **Phase 3**: Prometheus metrics – dùng cho analysis/automation.
- **Phase 5**: SLO & Alerting – định nghĩa ngưỡng success rate/latency cho canary promote.
