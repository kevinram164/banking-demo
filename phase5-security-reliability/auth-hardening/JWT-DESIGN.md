# JWT + Refresh Token Design (Phase 5)

Mục tiêu: thay session Redis hiện tại bằng **JWT + refresh token**, nhưng vẫn có khả năng **revoke** (logout, force logout) và demo được best practice khi đi phỏng vấn.

## 1. Kiến trúc tổng quan

- **Access Token (JWT)**:
  - Lifetime ngắn (5–15 phút).
  - Dùng cho mọi request tới backend (qua Kong).
  - Không lưu trong DB (stateless).
- **Refresh Token**:
  - Lifetime dài hơn (7–30 ngày).
  - Lưu trong Redis (hoặc DB) để có thể revoke.
  - Chỉ dùng tại endpoint `/auth/refresh`.

Luồng chính:

```text
1) Login:
   client -> POST /auth/login (username/phone + password)
   server -> access_token (JWT), refresh_token (random ID lưu trong Redis)

2) Call API:
   client -> gửi "Authorization: Bearer <access_token>" qua Kong
   kong/hoặc service -> verify JWT, lấy user_id từ claim

3) Refresh:
   client -> POST /auth/refresh (refresh_token)
   server:
     - check refresh_token trong Redis (còn sống, chưa revoke)
     - issue access_token mới, có thể issue refresh_token mới (rotate)

4) Logout:
   client -> POST /auth/logout (refresh_token)
   server:
     - xoá refresh_token trong Redis
     - có thể thêm access_token vào blocklist (tuỳ chính sách)
```

## 2. Cấu trúc JWT đề xuất

Header:

```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

Payload (claims):

```json
{
  "sub": "<user_id>",
  "username": "<display_name>",
  "phone": "<phone>",
  "account_number": "<account_number>",
  "iat": 1710000000,
  "exp": 1710000300,        // 5 phút
  "iss": "banking-demo",
  "aud": "banking-frontend"
}
```

Key:

- Dùng secret `JWT_SECRET` (ổn cho demo).
- Production: nên là key rotation (JWKS/Key ID), nhưng demo không nhất thiết phải implement.

## 3. Refresh Token design

- Refresh token **không phải JWT**, chỉ là random string (vd UUID v4).
- Lưu Redis:

```text
refresh:<token_id> -> user_id (TTL = 7 ngày)
```

Khi refresh:

1. Check key `refresh:<token_id>` có tồn tại.
2. Nếu ok:
   - Issue JWT mới.
   - (Tuỳ chọn) rotate: xoá token cũ, tạo token mới.

## 4. Endpoint design

### `POST /auth/login`

Request:

```json
{
  "phone": "0987654321",
  "password": "secret"
}
```

Response:

```json
{
  "access_token": "<JWT>",
  "refresh_token": "<RANDOM_ID>",
  "token_type": "Bearer",
  "expires_in": 300
}
```

### `POST /auth/refresh`

Request:

```json
{
  "refresh_token": "<RANDOM_ID>"
}
```

Response: như /login nhưng chỉ cấp mới token.

### `POST /auth/logout`

Request:

```json
{
  "refresh_token": "<RANDOM_ID>"
}
```

Server:

- Xoá `refresh:<RANDOM_ID>` khỏi Redis.
- Có thể thêm `jti` của access_token vào blocklist (nếu cần hard logout ngay).

## 5. Integration với Kong

Có 2 lựa chọn:

1. **Kong xác thực JWT** (plugin `jwt` hoặc `oauth2/introspection`)  
   - Pros: service không phải parse JWT lần nữa.
   - Cons: phải quản lý config key trong Kong.

2. **Service tự verify JWT** (hiện tại bạn đã có common lib)  
   - Pros: dễ demo, không phụ thuộc Kong plugin.
   - Cons: mỗi service đều parse JWT.

Cho demo này, có thể:

- Dùng Kong để chỉ **forward header**:
  - `Authorization: Bearer <JWT>`
- Dùng middleware FastAPI (trong common lib) để:
  - Parse & verify JWT.
  - Gắn `request.state.user` hoặc `Depends(current_user)` ở các route cần auth.

## 6. Backward compatibility strategy (Phase 5)

Vì Phase 4 đang dùng session-Redis + header `X-Session`, Phase 5 có thể rollout theo 2 bước:

1. **Song song**:
   - Backend accept cả:
     - `X-Session` (cũ)
     - `Authorization: Bearer <JWT>` (mới)
   - Kong route không thay đổi nhiều (chỉ thêm pass-through header).

2. **Cắt session**:
   - Update frontend dùng JWT hoàn toàn.
   - Dừng tạo session Redis mới; chỉ cho session cũ sống thêm 1 thời gian rồi tắt.

## 7. Demo point khi đi phỏng vấn

- Giải thích **luồng JWT + refresh token** + **tại sao cần refresh** (không dùng JWT lifetime dài).
- Giải thích cách **revoke**:
  - Logout = xoá refresh token khỏi Redis.
  - Force logout = invalidate refresh token + (tuỳ chọn) blocklist access token.
- Giải thích cách **rollout an toàn**:
  - accept song song `X-Session` & JWT.
  - migrate frontend từ session sang JWT dần dần.

