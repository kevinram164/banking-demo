# Keycloak / OIDC — shared IdP cho platform + banking (dev-ocp)

## Mục tiêu

Một Keycloak (`https://keycloak-platform.apps.ocp01.npd.co`) làm OIDC IdP cho:

| Client | Redirect / tích hợp |
|--------|---------------------|
| `argocd` | ArgoCD OIDC (`argocd-cm`) |
| `jenkins` | Jenkins oic-auth / OpenID Connect |
| `harbor` | Harbor OIDC |
| `ocp-console` | OpenShift `OAuth` IdP (OpenID) |
| `banking` | Banking frontend Authorization Code (+ map user Postgres) |
| *(apps sau)* | Cùng realm `platform`, client mới |

## Kiến trúc

```text
Users ──► Keycloak (realm: platform)
              │
              ├─► ArgoCD
              ├─► Jenkins
              ├─► Harbor
              ├─► OpenShift Console / API (OAuth CR)
              └─► Banking UI (OIDC) ──► auth-service (đổi/ kèm Redis session)
```

Banking hiện tại: bcrypt + Redis `X-Session` — **không** drop-in. Phase 5 mới đổi app.

## Phase

| # | Việc | Trạng thái repo |
|---|------|-----------------|
| 1 | Deploy Keycloak + Route + AppProject | GitOps sẵn |
| 2 | ArgoCD OIDC | Chưa |
| 3 | Harbor + Jenkins OIDC | Chưa |
| 4 | OpenShift OAuth IdP | Chưa (cluster CR) |
| 5 | Banking OIDC | Chưa (code + Kong) |

## Deploy Phase 1

```bash
# AppProject (ns keycloak)
oc apply -f phase9-gitops-platform/environments/dev-ocp/appproject.yaml -n argocd

# SCC cho ns keycloak (sau khi CreateNamespace)
oc apply -f ... # hoặc đợi Argo tạo ns rồi:
./phase9-gitops-platform/environments/dev-ocp/scripts/namespace-scc-setup.sh keycloak

# Sync (auto nếu platform-app-of-apps đã automated)
# ArgoCD → platform-keycloak → Sync
# Route nằm trong platform-routes-dev-ocp
```

Admin (lab): `admin` / `ChangeMe-Keycloak-Admin`  
URL: `https://keycloak-platform.apps.ocp01.npd.co`

## Realm / clients (thủ công lần đầu hoặc import sau)

1. Tạo realm **`platform`** (không dùng `master` cho app clients).
2. Clients (standard OIDC, confidential trừ SPA banking nếu public+PKCE):

| Client ID | Root / Valid redirect (ví dụ) |
|-----------|-------------------------------|
| argocd | `https://argocd-server-argocd.apps.ocp01.npd.co/auth/callback` |
| jenkins | `https://jenkins-platform.apps.ocp01.npd.co/securityRealm/finishLogin` |
| harbor | `https://harbor-platform.apps.ocp01.npd.co/c/oidc/callback` |
| ocp-console | theo OpenShift OAuth client redirect |
| banking | `https://npd-banking.co/oauth/callback` (sau khi FE hỗ trợ) |

3. Groups/roles: `platform-admins`, `developers`, `banking-users` — map vào từng hệ thống.

## Files

| File | Vai trò |
|------|---------|
| `gitops-platform/applications/platform/keycloak.yaml` | Argo Application |
| `environments/dev-ocp/ocp-values/platform/values-keycloak.yaml` | Helm values |
| `environments/dev-ocp/ocp-values/routes/keycloak-route.yaml` | Route |

## Bảo mật lab → prod

- Đưa `auth.adminPassword` + DB password vào Vault/ESO.
- Tắt local admin trên ArgoCD/Jenkins/Harbor sau khi OIDC ổn.
- Redis/session banking: giữ fallback hoặc migrate hẳn sang OIDC token.
