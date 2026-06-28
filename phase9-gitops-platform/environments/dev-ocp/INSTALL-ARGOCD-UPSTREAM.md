# ArgoCD upstream (opensource) trên OCP — ns `argocd`

Dùng **ArgoCD community** cài thủ công — không phụ thuộc **Red Hat OpenShift GitOps Operator** (trial/subscription).

> Operator Red Hat: xem [INSTALL-GITOPS-OPERATOR.md](./INSTALL-GITOPS-OPERATOR.md) — **tùy chọn**, cần license/trial.

---

## 1. Cài ArgoCD (nếu chưa có)

```bash
# Namespace
oc create namespace argocd

# Manifest upstream (pin version nếu cần)
oc apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

watch oc get pods -n argocd
```

---

## 1b. SCC — bắt buộc trên OpenShift (lab)

Manifest upstream chạy container với UID cố định (`redis` **999**, `dex` **1001**, …). Namespace `argocd` mặc định chỉ cho UID range `1000740000+` → pod **Forbidden** SCC.

Triệu chứng (Events):

```text
unable to validate against any security context constraint
runAsUser: Invalid value: 999 / 1001
seccomp may not be set   ← argocd-dex-server (cần privileged, không chỉ anyuid)
```

**Sửa (lab — cần `cluster-admin`):**

```bash
chmod +x phase9-gitops-platform/environments/dev-ocp/scripts/argocd-scc-anyuid.sh
./phase9-gitops-platform/environments/dev-ocp/scripts/argocd-scc-anyuid.sh argocd
```

Script gán **`anyuid` + `privileged`** cho `system:serviceaccounts:argocd`.

Hoặc thủ công:

```bash
oc adm policy add-scc-to-group anyuid system:serviceaccounts:argocd
oc adm policy add-scc-to-group privileged system:serviceaccounts:argocd
oc rollout restart statefulset,deployment -n argocd
watch oc get pods -n argocd
```

**Kiểm tra SCC đã gán chưa:**

```bash
oc get scc privileged -o yaml | grep 'system:serviceaccounts:argocd'
oc get scc anyuid -o yaml | grep 'system:serviceaccounts:argocd'
```

Nếu không thấy dòng trên → lệnh chạy bằng user **không đủ quyền** (cần `cluster-admin`).

**Tùy chọn — tắt Dex** (không dùng SSO/login OIDC):

```bash
oc scale deployment argocd-dex-server -n argocd --replicas=0
```

ArgoCD vẫn login `admin` + password local được.

Kỳ vọng pods **Running**: `argocd-redis-*`, `argocd-dex-server-*` (nếu giữ dex).

| Component | Vấn đề SCC | SCC lab |
|-----------|------------|---------|
| argocd-redis | UID 999 | `anyuid` |
| argocd-dex-server | UID 1001 + **seccomp** annotation | `privileged` (hoặc scale 0) |
| argocd-server | thường OK | — |

> Production: gán SCC từng ServiceAccount, hạn chế `privileged` — lab NPD dùng group trên namespace `argocd`.

---

## 2. Route (OpenShift Router)

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/routes/argocd-route.yaml
```

URL:

```text
https://argocd-server-argocd.apps.ocp01.npd.co
```

Nếu 502 — thử `targetPort: http` + TLS `edge` (ArgoCD `--insecure`):

```bash
oc patch configmap argocd-cmd-params-cm -n argocd --type merge \
  -p '{"data":{"server.insecure":"true"}}'
oc rollout restart deployment argocd-server -n argocd

oc patch route argocd-server -n argocd --type=merge -p '
{"spec":{"port":{"targetPort":"http"},"tls":{"termination":"edge","insecureEdgeTerminationPolicy":"Redirect"}}}'
```

---

## 2b. Lỗi "Application is not available" (pods vẫn Running)

Trang OpenShift Router khi **không route được** tới backend — pods ArgoCD có thể vẫn OK.

### Chẩn đoán

```bash
oc get route -n argocd
oc get svc,endpoints argocd-server -n argocd
oc describe route argocd-server -n argocd
```

| Kiểm tra | Kỳ vọng |
|----------|---------|
| `oc get route -n argocd` | Có `argocd-server` |
| `endpoints argocd-server` | IP pod (không `<none>`) |
| Host Route | `argocd-server-argocd.apps.ocp01.npd.co` |

### Sửa nhanh — tạo Route (nếu chưa có)

```bash
oc apply -f phase9-gitops-platform/environments/dev-ocp/ocp-values/routes/argocd-route.yaml
```

### Sửa nhanh — đổi sang edge + insecure (hay dùng nhất trên OCP lab)

```bash
oc patch configmap argocd-cmd-params-cm -n argocd --type merge \
  -p '{"data":{"server.insecure":"true"}}'
oc rollout restart deployment argocd-server -n argocd
oc rollout status deployment argocd-server -n argocd

oc apply -f - <<'EOF'
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: argocd-server
  namespace: argocd
spec:
  host: argocd-server-argocd.apps.ocp01.npd.co
  to:
    kind: Service
    name: argocd-server
    weight: 100
  port:
    targetPort: http
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
  wildcardPolicy: None
EOF
```

Đợi 30s → refresh `https://argocd-server-argocd.apps.ocp01.npd.co`

### reencrypt (nếu giữ HTTPS nội bộ ArgoCD)

```bash
oc get svc argocd-server -n argocd -o yaml | grep -A5 ports:
# targetPort phải khớp Route: https (443) hoặc tên port service
```

---

## 3. Mật khẩu admin

```bash
oc get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath='{.data.password}' | base64 -d; echo
# user: admin
```

---

## 4. Bootstrap banking-demo (dev-ocp)

```bash
export ARGOCD_NS=argocd
cd banking-demo && git checkout dev-ocp

# UI: Settings → Repositories → https://github.com/kevinram164/banking-demo.git

oc apply -f phase9-gitops-platform/environments/dev-ocp/appproject.yaml -n $ARGOCD_NS
./phase9-gitops-platform/environments/dev-ocp/apply-argocd.sh
```

Thứ tự sync: platform → routes → infra → banking — xem [README.md](./README.md).

---

## 5. Hết trial OCP

Trial cluster Red Hat hết hạn ≠ ArgoCD hỏng — nhưng **cả cluster** có thể không dùng tiếp. Khi đó:

- Lab tiếp trên **k3d** (`dev-k3d`) — ArgoCD upstream tương tự, ns `argocd`
- Hoặc cluster OCP mới + cài lại ArgoCD manifest (bước 1–4)

Không cần OpenShift GitOps Operator để học GitOps Phase 9.
