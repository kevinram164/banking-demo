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

## 1b. SCC — theo namespace UID range (khuyến nghị)

Manifest upstream chạy UID cố định thấp (`redis` **999**, `dex` **1001**, …). Namespace OpenShift chỉ cho phép dải `openshift.io/sa.scc.uid-range` (vd. `1000740000/10000`) → pod **Forbidden** nếu không patch.

**Cách làm:** patch workload vào dải UID namespace + gán SCC **`nonroot`** cho `system:serviceaccounts:argocd` (một lần cho cả namespace — **không** `anyuid`).

Chi tiết: **[INSTALL-SCC-HARDENED.md](./INSTALL-SCC-HARDENED.md)**

```bash
chmod +x phase9-gitops-platform/environments/dev-ocp/scripts/namespace-scc-setup.sh
./phase9-gitops-platform/environments/dev-ocp/scripts/namespace-scc-setup.sh argocd
watch oc get pods -n argocd
```

Script tự: patch Deployment/STS, tắt Dex (lab), gỡ `anyuid`/`privileged`, gán `nonroot` cho namespace.

Triệu chứng nếu chưa chạy:

```text
unable to validate against any security context constraint
runAsUser: Invalid value: 999
```

**PoC nhanh (không khuyến nghị):** `scripts/argocd-scc-anyuid.sh` — cảnh báo trước khi gán `anyuid`.

| Component | Sau namespace-scc-setup |
|-----------|-------------------------|
| argocd-redis | runAsUser → MIN_UID dải namespace |
| argocd-dex-server | scale 0 (không SSO) |
| argocd-server, repo-server, … | nonroot + UID trong dải |

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

Trial cluster Red Hat hết hạn → cluster không dùng tiếp. Cài lại ArgoCD manifest trên cluster OCP mới (bước 1–4).

Không cần OpenShift GitOps Operator để học GitOps Phase 9.
