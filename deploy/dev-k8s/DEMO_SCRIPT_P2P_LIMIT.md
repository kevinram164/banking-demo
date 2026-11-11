# Demo video — Hạn mức CK P2P/ngày → lỗi → rollback → fix

Narrate production-like trên cụm `dev-k8s` + Concert Operate.

## Câu chuyện

| Bước | Nội dung |
|------|----------|
| CR | Kiểm soát nội bộ: giới hạn tổng tiền **CK P2P theo ngày / user** |
| Feature | Check trong `transfer-service` `handle_create` |
| Bug | `P2P_DAILY_LIMIT_STRICT_DEFAULT=true` + thiếu `P2P_DAILY_LIMIT_VND` → limit=0 → reject mọi P2P với `TRANSFER_DAILY_LIMIT_EXCEEDED` |
| Mitigate | Runbook Argo rollback image `transfer-service` |
| Fix | `STRICT_DEFAULT=false` + set `P2P_DAILY_LIMIT_VND=50000000` → redeploy |

Shop / `MERCHANT_PAY` **không** dính gate (chỉ `txn_type==P2P`).

## Shot list + lời thoại

### 1 — Baseline (30–45s)
- UI `https://npd-banking.co`: CK P2P SUCCESS; chuông nhận tin PENDING/SUCCESS.
- (Tuỳ chọn) peer cron đang chạy.
- **Lời thoại:** “Hệ thống ổn định, chuyển khoản cá nhân realtime.”

### 2 — Nghiệp vụ mới (20s)
- Slide/ticket: *Hạn mức CK P2P theo ngày*.
- **Lời thoại:** “Yêu cầu kiểm soát rủi ro — thêm kiểm tra hạn mức ngày trước khi tạo PENDING.”

### 3 — Release (40s)
- Diff `transfer-service` + `values-ecosystem.yaml` (STRICT + chưa set LIMIT).
- Jenkins build `transfer-service` → Argo sync `banking-transfer-service`.
- **Lời thoại:** “Rollout qua GitOps / CI — không sửa tay trên pod.”

### 4 — Outage user (45s)
- CK tay → UI: `[TRANSFER_DAILY_LIMIT_EXCEEDED] Đã vượt hạn mức… (HTTP 503)`.
- Chuông/WS: `REJECTED [P2P]: không thể chuyển tiền — … (TRANSFER_DAILY_LIMIT_EXCEEDED)`.
- Kibana `logs-bank-*`: `error_code` / `failure_code`.
- **Lời thoại:** “Sau release, user không chuyển được tiền; mã lỗi chuẩn trên UI, noti và log.”

### 5 — Ops Telegram + AIOps (60s)
- Telegram: `[FIRING] BankingTransferUnavailable [critical] ns: npd-banking` + summary tiếng Việt.
- Concert: Incident → topology `transfer-service/npd-banking` → RCA.
- **Lời thoại:** “Ops nhận Telegram; AIOps correlate alert và topology, chỉ ra transfer-service.”

### 6 — Runbook rollback (45s)
- Mở runbook: `cloud-native-platform/.../aiops-observer/RUNBOOK_TRANSFER_ROLLBACK.md`.
- Argo History → Rollback revision trước fault.
- **Lời thoại:** “Ops mitigate bằng rollback GitOps — không hotfix trong container.”

### 7 — Mitigate OK (20s)
- CK tay SUCCESS lại; Telegram có thể `[RESOLVED]`.
- **Lời thoại:** “Dịch vụ đã hồi phục; giao dịch trở lại.”

### 8 — Fix & redeploy (45s)
- Đặt `P2P_DAILY_LIMIT_STRICT_DEFAULT=false`, `P2P_DAILY_LIMIT_VND=50000000`.
- CI → Argo → CK OK; (tuỳ chọn) demo vượt hạn thật.
- Đóng incident / đánh dấu runbook worked.
- **Lời thoại:** “Engineering sửa đúng logic hạn mức, rollout lại có kiểm soát.”

## Lệnh nhanh (npd-master / runner)

```bash
# Sau sync bản lỗi — kích fail
# UI: chuyển P2P bất kỳ
/home/sysadmin/npd-ecosystem/bin/run-job.sh peer

# Log
kubectl -n npd-banking logs deploy/banking-transfer-service -c transfer-service --tail=50 \
  | grep -E 'TRANSFER_DAILY_LIMIT_EXCEEDED|transfer_rejected'

# Rollback (xem RUNBOOK_TRANSFER_ROLLBACK.md)
argocd app history banking-transfer-service
argocd app rollback banking-transfer-service <REV>
```

## Env

| Key | Commit A (lỗi) | Commit B (fix) |
|-----|----------------|-----------------|
| `P2P_DAILY_LIMIT_ENABLED` | `true` | `true` |
| `P2P_DAILY_LIMIT_STRICT_DEFAULT` | `true` | `false` |
| `P2P_DAILY_LIMIT_VND` | *(không set)* | `50000000` |
