# Custom SCC theo ServiceAccount (dự phòng)

**Hướng chính:** [INSTALL-SCC-HARDENED.md](../INSTALL-SCC-HARDENED.md) — `namespace-scc-setup.sh` (UID range + `nonroot` cả namespace).

Chỉ dùng các file trong thư mục này khi **không patch được** UID vào dải namespace (image bắt buộc UID cố định).

| File | Khi nào |
|------|---------|
| `argocd-redis-scc.yaml` | Redis bắt buộc UID 999, không patch được |
| `argocd-dex-scc.yaml` | Giữ Dex SSO + không scale 0 |
| `harbor-scc.yaml` | Harbor UID 999/10000 (entrypoint `/harbor/entrypoint.sh`) |
| `jenkins-scc.yaml` | Jenkins bắt buộc UID 1000 (chart cũ) |
| `kong-scc.yaml` | Kong bắt buộc UID 1000 — `kong-scc-setup.sh` |
