# Web Application Firewall (WAF) — Phase 7

Mục tiêu: bổ sung **WAF** để bảo vệ ứng dụng khỏi các tấn công Layer 7 (SQL injection, XSS, LFI, RCE, …).

## 1. Kiến trúc đề xuất

```
[Client] → [NGINX LB + WAF] → [HAProxy Ingress] → [Kong] → [Services]
```

- **NGINX LB** (10.100.1.100): đã có sẵn, đặt WAF tại đây — chặn sớm trước khi vào cluster.
- **Kong** (đã có): rate-limiting, request-size-limiting, CORS — bảo vệ API cơ bản.
- **HAProxy KIC** (`haproxy.org`): không hỗ trợ ModSecurity, nên WAF đặt ở NGINX LB.

## 2. WAF trên NGINX LB

### 2.1. NGINX Plus — F5 WAF (App Protect)

Nếu có license **F5 WAF for NGINX** (NGINX App Protect):

- WAF tích hợp sẵn với NGINX Plus.
- Hơn 7.500 signatures, OWASP Top 10, bot prevention, API security.
- Cấu hình qua `app_protect_*` directives trong nginx.conf.

### 2.2. NGINX + ModSecurity (open-source)

Cài module `modsecurity-nginx` và OWASP CRS:

```nginx
load_module modules/ngx_http_modsecurity_module.so;

http {
    modsecurity on;
    modsecurity_rules_file /etc/nginx/modsec/main.conf;

    server {
        listen 80;
        server_name npd-banking.co;
        location / {
            modsecurity on;
            proxy_pass http://<haproxy-ingress-backend>;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

**OWASP CRS:** cài vào `/etc/nginx/modsec/` và include trong `main.conf`.

### 2.3. Chế độ DetectionOnly

Để test rule mà không chặn request:

- Trong `modsecurity.conf`: `SecRuleEngine DetectionOnly`
- Request vẫn qua, log ghi nhận vi phạm.

## 3. Các lựa chọn WAF (tóm tắt)

| Phương án | Vị trí | Ghi chú |
|-----------|--------|---------|
| **F5 WAF for NGINX** | NGINX Plus LB | Cần license, tích hợp sẵn |
| **ModSecurity + OWASP CRS** | NGINX LB | Open-source, cài module |
| **Kong plugins** | Kong | rate-limit, size-limit — không phải WAF đầy đủ |
| **HAProxy Ingress + ModSecurity** | Trong cluster | Phải đổi sang HAProxy Ingress community |

## 4. Lựa chọn thay thế: WAF ở HAProxy Ingress

Nếu muốn WAF **trong cluster** thay vì ở NGINX LB:

- Phải chuyển từ HAProxy KIC (`haproxy.org`) sang **HAProxy Ingress community** (`haproxy-ingress.github.io`).
- Deploy ModSecurity SPOA agent: [modsecurity-deployment.yaml](https://haproxy-ingress.github.io/resources/modsecurity-deployment.yaml)
- Cấu hình ConfigMap `modsecurity-endpoints`, annotation `haproxy-ingress.github.io/waf: "modsecurity"`.

Tham khảo: [HAProxy Ingress ModSecurity](https://haproxy-ingress.github.io/docs/examples/modsecurity/)

## 5. Liên kết

- [F5 WAF for NGINX](https://www.f5.com/products/nginx/nginx-app-protect)
- [ModSecurity-nginx](https://github.com/SpiderLabs/ModSecurity-nginx)
- [OWASP Core Rule Set](https://coreruleset.org/)
- [Kong Security Plugins](../kong-security/KONG-PLUGINS.md) — bảo vệ API cơ bản (kết hợp với WAF)
