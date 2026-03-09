# GitHub Actions Security Hardening (Phase 7)

Mục tiêu: bổ sung một layer **security** cho CI/CD, tập trung vào:

- Scan image / code cơ bản.
- Hạn chế leak secrets trong pipeline.
- **DevSecOps pipeline** cho PR (feature → main).

---

## DevSecOps Pipeline (PR flow)

**File:** `.github/workflows/devsecops-pr.yml`

### Luồng hoạt động (GitHub Flow)

1. Dev tạo nhánh `feature/xxx`, push code, tạo **Pull Request** vào `main`
2. Workflow tự trigger khi PR được mở/cập nhật
3. Chạy: Lint → Test → SAST (Trivy, Bandit) → Dependency scan
4. Report: comment lên PR + gửi Telegram (nếu cấu hình)
5. **Chặn merge** nếu có CRITICAL/HIGH (Trivy), HIGH (Bandit), hoặc dependency vuln

### Cấu hình cần thiết

**Branch protection (để chặn merge):**

- Settings → Branches → Add rule cho `main`
- Bật **Require status checks to pass before merging**
- Chọn các check: `Lint`, `Test`, `SAST (Trivy)`, `SAST (Bandit)`, `Dependency Scan`

**Telegram (tùy chọn):**

- Tạo bot qua [@BotFather](https://t.me/BotFather) → lấy Bot Token
- Tạo group, thêm bot, lấy Chat ID
- Settings → Secrets → Actions: thêm `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

Nếu không cấu hình Telegram, step notify sẽ fail nhưng không chặn workflow (continue-on-error).

---

## 1. Thêm job security scan vào `.github/workflows/ci.yml`

Gợi ý thêm job `security-scan` (chạy song song với build/test):

```yaml
security-scan:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    - name: Install Trivy
      uses: aquasecurity/trivy-action@master
      with:
        version: latest

    - name: Trivy FS scan (source)
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: fs
        scan-ref: .
        severity: HIGH,CRITICAL
        ignore-unfixed: true
        exit-code: 0      # demo: không fail build, chỉ report
        format: table
```

Nếu sau này bạn build image trong CI, có thể thêm step:

```yaml
    - name: Trivy Image scan
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: image
        image-ref: your-registry/banking/auth-service:v2
        severity: HIGH,CRITICAL
        ignore-unfixed: true
        exit-code: 1  # fail nếu muốn chặn build
```

## 2. Secret handling trong CI

Nguyên tắc:

- **Không** commit password/API key vào repo (hiện bạn đã ok).
- Các secret cần cho CI (nếu có) nên để trong:
  - GitHub Actions Secrets (`Settings` → `Secrets and variables` → `Actions`).
  - Hoặc dùng môi trường staging riêng.

Trong demo hiện tại, CI **không dùng** DB/Redis thật → không cần secret nhạy cảm trong pipeline (điểm cộng an toàn).

## 3. Gợi ý cho bài "kể chuyện" khi phỏng vấn

- Bạn có thể nói:
  - "Ở Phase 7 em thêm một job security scan bằng Trivy trong CI để check lỗ hổng HIGH/CRITICAL trong code và image".
  - "Tách rõ build/test và security scan, có thể cấu hình exit-code để chặn release nếu có issue nghiêm trọng".
  - "Không sử dụng secret thật trong pipeline để tránh rủi ro leak khi share log/artefact".
