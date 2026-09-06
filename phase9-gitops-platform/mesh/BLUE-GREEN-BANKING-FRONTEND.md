# Blue-Green Banking Frontend (Đợt H-FE)

Runbook **tách riêng** — không thay INSTALL Ambient chung. Retry / blue-green `api-producer` = plan khác.

## Kiến trúc

```
Browser → OCP Route (npd-banking.co)
       → Service frontend-edge (nginx, ambient, PERMISSIVE)
       → http://frontend.npd-banking.svc:80  (VIP, use-waypoint)
       → Waypoint (L7)
       → HTTPRoute weights → frontend-blue | frontend-green
```

OpenShift Router **không** qua waypoint. Edge hop in-mesh buộc mọi request UI đi L7 split — Kiali thấy `frontend-blue` vs `frontend-green`.

| Workload | Mesh | mTLS inbound |
|----------|------|----------------|
| `frontend-edge` | ambient | PERMISSIVE (Route) |
| `frontend-blue` / `frontend-green` | ambient | STRICT (default ns) |
| Service `frontend` | VIP + `istio.io/use-waypoint=waypoint` | — |

## File GitOps

| Path | Vai trò |
|------|---------|
| [`gitops/values-frontend-bluegreen.yaml`](../gitops/values-frontend-bluegreen.yaml) | `blueGreen.enabled: true` + image tags |
| Helm `templates/frontend-bluegreen.yaml` | Deploy/Svc blue + green + VIP `frontend` |
| Helm `templates/frontend-edge.yaml` | Edge nginx + SA |
| [`routes/banking-route-frontend.yaml`](../environments/dev-ocp/ocp-values/routes/banking-route-frontend.yaml) | Route → `frontend-edge` |
| [`workloads/banking-*.yaml`](workloads/) | PA + Authz edge/waypoint → blue/green |
| [`waypoint/banking-frontend-bluegreen.yaml`](waypoint/banking-frontend-bluegreen.yaml) | HTTPRoute weights (sync tay `mesh-waypoint`) |
| [`frontend/`](../../frontend/) | FE **blue** (ổn định) — image `.../frontend` |
| [`frontend-green/`](../../frontend-green/) | FE **green** (mới) — image `.../frontend-green` — **folder + pipeline riêng** |

---

## Phase 0 — Baseline

1. `curl -sk https://npd-banking.co/ | head -c 200` và `/api/auth/health` OK.
2. Screenshot Kiali ns `npd-banking` (trước FE ambient dual).
3. `argocd app get mesh-waypoint` — **không** automated.

---

## Phase 1–2 — Build images (trước khi sync Helm blue-green)

Hai folder / hai image / **hai target Jenkins**:

```bash
# Jenkins job banking-demo — param BUILD_TARGET
#   frontend       → context frontend/
#   frontend-green → context frontend-green/
#   auto           → build khi git diff chạm watchPath tương ứng

# Tay (tương đương Kaniko):
REG=harbor-platform.apps.ocp01.npd.co/banking-demo
TAG=9b04db8
cd banking-demo
docker build -t $REG/frontend:$TAG ./frontend
docker build -t $REG/frontend-green:$TAG ./frontend-green
docker push $REG/frontend:$TAG
docker push $REG/frontend-green:$TAG
```

Catalog: `jenkins-shared-library` → `src/com/platform/Projects.groovy` (`banking-demo` services).  
CI bump tag: `values-images.yaml` keys `frontend` / `frontend-green`.

**Cần push repo `jenkins-shared-library` (nhánh main)** rồi reload library trên Jenkins trước khi BUILD_TARGET thấy `frontend-green`.

---

## Phase 3 — Deploy dual + edge

Thứ tự:

1. Push Git → sync **`mesh-workloads-banking`** (PA/Authz) trước hoặc cùng lúc.
2. Sync **`banking-frontend`** (valueFile `values-frontend-bluegreen.yaml`).
3. Sync Route app (Route → `frontend-edge`).
4. Đợi pods Ready:

```bash
oc -n npd-banking get deploy,svc -l 'app.kubernetes.io/component in (frontend,frontend-edge)'
oc -n npd-banking get pods -l 'app in (frontend-blue,frontend-green,frontend-edge)' -o wide
oc -n npd-banking get svc frontend -o yaml | grep -E 'use-waypoint|ClusterIP'
```

Kỳ vọng: 3 Deploy Ready; Svc `frontend` **không** có selector pod; label `istio.io/use-waypoint=waypoint`.

**Rollback Helm:** `frontend.blueGreen.enabled: false` + Route lại `frontend` + sync.

**Argo `prune: false`:** sau khi bật blue-green, xóa tay Deploy/Svc cũ nếu còn:

```bash
oc -n npd-banking delete deploy frontend --ignore-not-found
# Không xóa Svc frontend — VIP logic vẫn cần (Helm tạo lại không selector)
```

---

## Phase 4 — Waypoint + weight steps

```bash
# Một lần: đảm bảo Application tồn tại
oc apply -f phase9-gitops-platform/gitops-platform/applications/mesh/waypoint.yaml

argocd app sync mesh-waypoint
# hoặc: oc apply -k phase9-gitops-platform/mesh/waypoint/

oc -n npd-banking label svc/frontend istio.io/use-waypoint=waypoint --overwrite
oc -n npd-banking get gateway waypoint
oc -n npd-banking get httproute frontend-bluegreen -o yaml
```

### Bảng weight (chỉ sửa [`banking-frontend-bluegreen.yaml`](waypoint/banking-frontend-bluegreen.yaml))

Copy-paste sẵn: [`waypoint/FRONTEND-WEIGHT-STEPS.md`](waypoint/FRONTEND-WEIGHT-STEPS.md).

| Bước | Blue | Green | Soak | Checkpoint |
|------|------|-------|------|------------|
| **B0** | 100 | 0 | 5–10 phút | 0 hit `GREEN v2`; Kiali chỉ blue |
| **B1** | 70 | 30 | 10–15 phút | ~30% green |
| **B2** | 50 | 50 | 10–15 phút | ~50% |
| **B3** | 30 | 70 | 10–15 phút | đa số green |
| **B4** | 0 | 100 | ổn định | 100% green |
| **B5** | — | 100 | — | cleanup blue |

Sau mỗi sửa weight:

```bash
argocd app sync mesh-waypoint
# cập nhật annotation label banking-demo/traffic-step cho dễ audit
```

**Rollback weight:** set lại `100` / `0`, sync `mesh-waypoint`.

---

## Phase 5 — Verify Kiali + curl (bắt buộc mỗi bước)

### Browser

Hard-refresh `https://npd-banking.co/` nhiều lần — green = nền emerald + badge **GREEN v2**.

### Đếm tỷ lệ (bastion)

```bash
# 50 request — số lần thấy marker green trong HTML tĩnh
n=50; g=0
for i in $(seq 1 $n); do
  curl -sk https://npd-banking.co/ | grep -q 'GREEN v2' && g=$((g+1)) || true
done
echo "green_hits=$g / $n (expect ~ weight_green%)"
```

Hoặc `/variant.txt` (green trả `GREEN v2`, blue trả `blue`):

```bash
for i in $(seq 1 40); do curl -sk https://npd-banking.co/variant.txt; echo; done | sort | uniq -c
```

### Kiali

1. Namespace **`npd-banking`**, time range **5–15m**.
2. Display: **TCP** (+ HTTP nếu waypoint đã emit).
3. Topology kỳ vọng:
   - `frontend-edge` → `frontend` / waypoint → **`frontend-blue`** và **`frontend-green`**
   - Tỷ lệ cạnh gần weight (lab: chạy vòng `curl`/`hey` trong lúc xem).
4. Workload labels: `version=blue` / `version=green`.

```bash
# Tạo traffic để graph có mũi tên
hey -z 2m -c 4 https://npd-banking.co/ || \
  for i in $(seq 1 200); do curl -sk https://npd-banking.co/ >/dev/null; done
```

### Checklist từng bước

- [ ] B0: `green_hits=0`; Kiali không (hoặc ~0) traffic green  
- [ ] B1: green ~25–40%  
- [ ] B2: green ~40–60%  
- [ ] B3: green ~60–80%  
- [ ] B4: green ~100%; UI luôn emerald  

---

## Phase 6 — Cutover & dọn

1. Soak B4 ổn.
2. Đổi tag “canonical” / scale `frontend-blue` → 0 hoặc xóa Deploy blue.
3. Cập nhật `values-images.yaml`; có thể giữ edge + HTTPRoute 0/100 hoặc rút gọn sau demo.
4. `frontend.blueGreen.enabled: false` chỉ khi đã merge green thành single Deploy (và sửa Route).

---

## Troubleshooting

| Triệu chứng | Xử lý |
|-------------|--------|
| Route 503 | `frontend-edge` Ready? Authz `allow-route-to-frontend-edge`? PA PERMISSIVE edge? |
| Luôn blue dù weight green > 0 | HTTPRoute synced? `use-waypoint` trên Svc `frontend`? Waypoint Gateway Ready? |
| 403/RBAC mesh | Authz cho SA `waypoint` + `frontend-edge` trên blue/green |
| ImagePullBackOff green | Push tag `*-green`; khớp `values-frontend-bluegreen.yaml` |
| Kiali không thấy FE | Pod ambient? UWM + ztunnel metrics (xem `mesh/README.md`) |
| Edge OK nhưng /api lỗi | Proxy edge → frontend VIP → blue/green nginx vẫn proxy Kong — kiểm tra Kong |

---

## Ngoài phạm vi

Shop FE, transfer/auth blue-green, DestinationRule retry, thay Route bằng Gateway API public.
