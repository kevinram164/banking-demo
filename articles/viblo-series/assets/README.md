# Ảnh minh họa — Viblo Series Phase 9

Upload các file PNG này lên Viblo khi đăng bài [`10-gitops-platform-phase9.md`](../10-gitops-platform-phase9.md).

| File | Chèn sau mục |
|------|--------------|
| `phase9-architecture-overview.png` | **Kiến trúc tổng thể** (k3d / dev-k3d) |
| `phase9-architecture-overview-ocp.png` | **Kiến trúc OpenShift** (OCP / dev-ocp — Route, không Traefik) |
| `phase9-architecture-overview-ocp.mmd` | Nguồn Mermaid để chỉnh / export lại |
| `phase9-cicd-flow.png` | **Luồng CI/CD** |
| `jenkins-shared-library-overview.png` | **Jenkins Shared Library** — ảnh chính (cùng style GitOps platform) |
| `jenkins-shared-library-flow.png` | Shared Library — sơ đồ Mermaid (layered) |
| `jenkins-shared-library-sequence.png` | Shared Library — sequence một lần build |
| `jenkins-shared-library-*.mmd` | Nguồn Mermaid (chỉnh / export lại) |
| `phase9-namespace-map.png` | **Bản đồ namespace** |
| `phase9-vault-eso-flow.png` | **Vault + ESO multi-app** — banking / shop / cinehome / AIOps + platform |
| `phase9-vault-eso-flow.mmd` | Nguồn Mermaid (chỉnh / export lại) |

Ảnh cho bài [`11-vault-agent-injector-vs-eso.md`](../11-vault-agent-injector-vs-eso.md) (nguồn `.mmd` cùng tên):

| File | Chèn sau mục |
|------|--------------|
| `vault-eso-before.png` | **1. Kiến trúc cũ: Vault + ESO** |
| `vault-injector-overview.png` | **2. Vault Agent Injector là gì?** |
| `vault-injector-sequence.png` | **3. Cơ chế hoạt động chi tiết** |
| `vault-injector-pod-mutation.png` | **Bước 1–3: Webhook sửa Pod** |

Xuất lại PNG: `npx -y @mermaid-js/mermaid-cli@11 -i <file>.mmd -o <file>.png -b white -s 2`

**Cách đăng Viblo:**

1. Copy nội dung Markdown từ `10-gitops-platform-phase9.md` (Viblo hỗ trợ Markdown).
2. Các block ` ```mermaid ` — Viblo hiển thị nếu bật Mermaid; nếu không, dùng ảnh PNG thay thế.
3. Upload 3 PNG ở trên → chèn tại vị trí `![...](./assets/...)`.
4. Tag gợi ý: `kubernetes`, `gitops`, `argocd`, `jenkins`, `harbor`, `devops`, `k3d`.

**Series:** Bài 10/12 — sau bài 9 (Phase 5 tuning).
