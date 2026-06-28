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
oc patch route argocd-server -n argocd --type=merge -p '
{"spec":{"port":{"targetPort":"http"},"tls":{"termination":"edge","insecureEdgeTerminationPolicy":"Redirect"}}}'
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
