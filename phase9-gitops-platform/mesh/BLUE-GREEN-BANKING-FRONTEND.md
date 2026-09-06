# Hướng dẫn triển khai Blue-Green Banking Frontend (Đợt H-FE)

Runbook **tách riêng** — không thay INSTALL Ambient. Mục tiêu lab: hai bản UI (cũ/mới), Istio chia traffic 70/30 → 0/100, Kiali thấy rõ.

---

## 0. Thuật ngữ (đọc trước)

| Tên | Là gì | Có phải UI? |
|-----|--------|-------------|
| `frontend/` | Code **bản cũ** (blue) | Có — source |
| `frontend-green/` | Code **bản mới** (green, nền emerald) | Có — source |
| Image `.../frontend` | Image build từ `frontend/` | Deploy vào `frontend-blue` |
| Image `.../frontend-green` | Image build từ `frontend-green/` | Deploy vào `frontend-green` |
| `frontend-edge` | Nginx **lễ tân** — nhận Route, chuyển vào mesh | **Không** |
| Service `frontend` | VIP ảo (không pod UI) — Istio gắn waypoint | **Không** |
| `frontend-bluegreen` | **HTTPRoute** = bảng % blue/green | **Không** |
| Waypoint | Trạm L7 Istio — đọc HTTPRoute, chọn blue hoặc green | **Không** |

Luồng request:

```
Browser
  → OpenShift Route (npd-banking.co)
  → frontend-edge (ambient, PERMISSIVE)
  → VIP frontend + waypoint
  → frontend-blue  HOẶC  frontend-green   (theo %)
```

---

## 1. Điều kiện trước khi làm

Trên bastion, mọi lệnh dưới đây phải **OK**:

```bash
# Banking đang chạy
curl -sk -o /dev/null -w "%{http_code}\n" https://npd-banking.co/
curl -sk https://npd-banking.co/api/auth/health

# Ambient banking ổn
oc -n npd-banking get pods
oc get application -n argocd | grep -E 'banking-frontend|mesh-workloads|mesh-waypoint|platform-routes'

# Harbor pull được (đã có secret harbor-pull-creds trong ns)
oc -n npd-banking get secret harbor-pull-creds
```

| App Argo | Vai trò |
|----------|---------|
| `banking-frontend` | Helm FE (blue/green/edge khi bật) |
| `mesh-workloads-banking` | PA + Authz |
| `platform-routes-dev-ocp` (hoặc app route con) | Route → Service |
| `mesh-waypoint` | Gateway + HTTPRoute — **không auto-sync** |

**Repo cần push (đúng nhánh):**

1. `jenkins-shared-library` → `main` (có service `frontend-green` trong `Projects.groovy`)
2. `banking-demo` → `dev-ocp` (code + GitOps trong doc này)

---

## 2. Push Git + Jenkins build image

### 2.1. Shared library (một lần)

```bash
cd /path/to/jenkins-shared-library
git status   # phải có frontend-green trong src/com/platform/Projects.groovy
git push origin main
```

Jenkins → Manage Jenkins → System → Global Pipeline Libraries → `platform` → **Scan** / đợi load bản mới.

### 2.2. Push banking-demo

```bash
cd /path/to/banking-demo
git checkout dev-ocp
git add frontend frontend-green \
  phase2-helm-chart/banking-demo/templates/frontend-*.yaml \
  phase2-helm-chart/banking-demo/charts/frontend/values.yaml \
  phase9-gitops-platform/gitops/values-images.yaml \
  phase9-gitops-platform/gitops/values-frontend-bluegreen.yaml \
  phase9-gitops-platform/mesh/ \
  phase9-gitops-platform/environments/dev-ocp/
git commit -m "feat(mesh): blue-green banking frontend (edge + waypoint weights)"
git push origin dev-ocp
```

### 2.3. Build image trên Jenkins

Job banking-demo (in-cluster), param:

| Lần chạy | `BUILD_TARGET` | Kết quả |
|----------|----------------|---------|
| 1 | `frontend-green` | Push `harbor-platform.../banking-demo/frontend-green:<sha>` + bump `values-images.yaml` |
| 2 (nếu cần image blue mới) | `frontend` | Push `.../frontend:<sha>` |

Hoặc `BUILD_TARGET=all` (lâu hơn).

**Verify Harbor** (UI Harbor hoặc):

```bash
# Sau CI, đọc tag mới trong Git
git -C /path/to/banking-demo pull
grep -A5 '^frontend:' phase9-gitops-platform/gitops/values-images.yaml
grep -A5 '^frontend-green:' phase9-gitops-platform/gitops/values-images.yaml
```

Hai key phải có **cùng tag** (hoặc tag green mới vừa build). Ghi lại:

```bash
TAG=$(grep -A3 '^frontend-green:' phase9-gitops-platform/gitops/values-images.yaml | grep 'tag:' | head -1 | awk '{print $2}' | tr -d '"')
echo "TAG=$TAG"
```

**Nếu Jenkins chưa có `frontend-green`:** shared lib chưa push/reload — build tay:

```bash
REG=harbor-platform.apps.ocp01.npd.co/banking-demo
TAG=$(git -C banking-demo rev-parse --short HEAD)   # ví dụ
cd banking-demo
docker build -t $REG/frontend-green:$TAG ./frontend-green
docker push $REG/frontend-green:$TAG
# Sửa tay values-images.yaml frontend-green.image.tag rồi commit push
```

**Cổng kiểm tra trước Phase 3:** image `frontend-green:$TAG` đã có trên Harbor.

---

## 3. Bật GitOps blue-green (mesh + Helm + Route)

Thứ tự sync **bắt buộc** (tránh Route trỏ `frontend-edge` khi Deploy chưa có).

### 3.1. Mesh policy (PA / Authz)

```bash
argocd app sync mesh-workloads-banking --force
# hoặc: oc apply -f phase9-gitops-platform/mesh/workloads/banking-peer-authentication.yaml
#        oc apply -f phase9-gitops-platform/mesh/workloads/banking-authorization.yaml

oc -n npd-banking get peerauthentication
oc -n npd-banking get authorizationpolicy | grep -E 'frontend|edge'
```

Kỳ vọng có: `route-frontend-edge`, `allow-route-to-frontend-edge`, `allow-edge-to-frontend-blue`, `allow-edge-to-frontend-green`.

### 3.2. Helm dual + edge

File [`gitops/values-frontend-bluegreen.yaml`](../gitops/values-frontend-bluegreen.yaml) đã `blueGreen.enabled: true` và Argo `banking-frontend` đã khai báo valueFile này.

```bash
argocd app sync banking-frontend
argocd app wait banking-frontend --health

oc -n npd-banking get deploy frontend-blue frontend-green frontend-edge
oc -n npd-banking get pods -l 'app in (frontend-blue,frontend-green,frontend-edge)'
oc -n npd-banking get svc frontend frontend-blue frontend-green frontend-edge
```

**Kỳ vọng:**

- 3 Deployment Ready (`1/1`)
- Svc `frontend`: **không** có `selector` pod (chỉ VIP)
- Label: `oc -n npd-banking get svc frontend -o jsonpath='{.metadata.labels}'` có `istio.io/use-waypoint=waypoint`

Image green:

```bash
oc -n npd-banking get deploy frontend-green -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
# .../frontend-green:<TAG>
```

**Deploy cũ tên `frontend` còn sót** (Argo prune=false):

```bash
oc -n npd-banking delete deploy frontend --ignore-not-found
# KHÔNG xóa svc/frontend
```

**Cổng kiểm tra:** 3 deploy Ready, chưa đổi Route vẫn có thể còn trỏ Service cũ — sang bước 3.3.

### 3.3. Route → frontend-edge

Manifest: [`routes/banking-route-frontend.yaml`](../environments/dev-ocp/ocp-values/routes/banking-route-frontend.yaml) → `to.name: frontend-edge`.

```bash
argocd app sync platform-routes-dev-ocp
# nếu Route nằm app khác: argocd app list | grep -i route

oc -n npd-banking get route npd-banking -o jsonpath='{.spec.to.name}{"\n"}'
# Kỳ vọng: frontend-edge

curl -sk -o /dev/null -w "%{http_code}\n" https://npd-banking.co/
# Kỳ vọng: 200
```

**Rollback nhanh Route** (nếu 503):

```bash
oc -n npd-banking patch route npd-banking --type=merge -p '{"spec":{"to":{"name":"frontend-blue","weight":100}}}'
# tạm thời; sau đó sửa Git + sync lại
```

---

## 4. Waypoint + HTTPRoute (chia %)

### 4.1. Sync mesh-waypoint (tay)

```bash
# Application tồn tại?
oc get application mesh-waypoint -n argocd || \
  oc apply -f phase9-gitops-platform/gitops-platform/applications/mesh/waypoint.yaml

argocd app sync mesh-waypoint
# hoặc: oc apply -k phase9-gitops-platform/mesh/waypoint/

oc -n npd-banking get gateway waypoint
oc -n npd-banking get httproute frontend-bluegreen -o yaml | head -60
oc -n npd-banking label svc/frontend istio.io/use-waypoint=waypoint --overwrite
```

HTTPRoute mặc định **B0 = blue 100 / green 0** ([`banking-frontend-bluegreen.yaml`](waypoint/banking-frontend-bluegreen.yaml)).

### 4.2. Verify B0 (100% UI cũ)

```bash
n=30; g=0
for i in $(seq 1 $n); do
  curl -sk https://npd-banking.co/ | grep -q 'GREEN v2' && g=$((g+1)) || true
done
echo "green_hits=$g / $n"   # kỳ vọng 0
```

**OK nếu `green_hits=0`.** Browser: nền slate/xanh dương, không badge GREEN v2.

#### `/variant.txt` (chỉ đúng sau khi rebuild image có file này)

Image **cũ** (trước khi Dockerfile ghi `variant.txt`) → nginx SPA trả **cả trang HTML** thay vì chữ `blue`. Đó **không** phải lỗi weight.

```bash
# Kiểm tra image đang chạy có file không
oc -n npd-banking exec deploy/frontend-blue -- ls -la /usr/share/nginx/html/variant.txt 2>&1

# Sau rebuild frontend (+ frontend-green) có variant.txt:
for i in $(seq 1 20); do curl -sk https://npd-banking.co/variant.txt; echo; done | sort | uniq -c
# B0 kỳ vọng: 20 dòng "blue"
```

Thiếu file → Jenkins `BUILD_TARGET=frontend` (và `frontend-green`) rồi sync Argo, hoặc tạm bỏ qua `variant.txt`, chỉ dùng `GREEN v2` / mắt nhìn UI.

---

## 5. Tăng dần weight (demo)

### SPA sticky (quan trọng)

CRA build mỗi version một hash `/static/js/main.xxxx.js`. Nếu **không sticky**:
HTML blue + CSS/JS green → file không tồn tại → nginx trả HTML → **trang trần / mất style** (không phải “UI V2 xấu”).

**Edge** dùng cookie `fe_bg=blue|green` + `split_clients` theo `frontend.blueGreen.weight`. Đổi % = sửa **cả hai**:

1. `gitops/values-frontend-bluegreen.yaml` → `weight.blue` / `weight.green`
2. `mesh/waypoint/banking-frontend-bluegreen.yaml` → HTTPRoute weights (khớp)
3. `argocd app sync banking-frontend` (rollout edge) + `argocd app sync mesh-waypoint`
4. Browser: **xóa cookie `fe_bg`** hoặc cửa sổ ẩn danh khi đo lại %

Snippet HTTPRoute: [`waypoint/FRONTEND-WEIGHT-STEPS.md`](waypoint/FRONTEND-WEIGHT-STEPS.md).

### Cách đổi (mỗi bước)

1. Sửa `phase9-gitops-platform/mesh/waypoint/banking-frontend-bluegreen.yaml` — `weight` blue/green.
2. (Tuỳ chọn) đổi label `banking-demo/traffic-step: B1-70-30`.
3. Push Git **hoặc** apply trực tiếp lab:

```bash
# Lab nhanh (không chờ Git) — sau đó nhớ commit cho khớp GitOps
oc apply -f phase9-gitops-platform/mesh/waypoint/banking-frontend-bluegreen.yaml
# hoặc
argocd app sync mesh-waypoint
```

4. Tạo traffic + đếm + xem Kiali (mục 6).

| Bước | Blue | Green | Soak | `green_hits` / 50 (gần đúng) |
|------|------|-------|------|------------------------------|
| B0 | 100 | 0 | 5 phút | ~0 |
| B1 | 70 | 30 | 10 phút | ~12–18 |
| B2 | 50 | 50 | 10 phút | ~20–30 |
| B3 | 30 | 70 | 10 phút | ~30–40 |
| B4 | 0 | 100 | ổn định | ~50 |

**Rollback % ngay:**

```yaml
# weight blue=100 green=0 rồi
argocd app sync mesh-waypoint
```

---

## 6. Quan sát Kiali + curl (mỗi bước weight)

### 6.1. Curl / variant

```bash
n=50; g=0
for i in $(seq 1 $n); do
  curl -sk https://npd-banking.co/ | grep -q 'GREEN v2' && g=$((g+1)) || true
done
echo "green_hits=$g / $n"

for i in $(seq 1 40); do curl -sk https://npd-banking.co/variant.txt; echo; done | sort | uniq -c
```

### 6.2. Tạo traffic cho graph

```bash
hey -z 2m -c 4 https://npd-banking.co/ 2>/dev/null || \
  for i in $(seq 1 200); do curl -sk https://npd-banking.co/ >/dev/null; done
```

### 6.3. Kiali

1. Mở Kiali → namespace **`npd-banking`**.
2. Time range **5–15 minutes**.
3. Display: bật **TCP** (Ambient); có waypoint thì thêm HTTP nếu hiện.
4. Kỳ vọng topology:
   - `frontend-edge` → (waypoint / `frontend`) → **`frontend-blue`** và **`frontend-green`**
   - Tỷ lệ cạnh gần với weight đang set.

---

## 7. Cutover & dọn (sau B4 ổn)

1. Giữ weight **0 / 100** đủ soak.
2. Scale down blue (demo):

```bash
oc -n npd-banking scale deploy/frontend-blue --replicas=0
```

3. (Tuỳ chọn) sau demo: đưa UI green thành canonical — đổi image `frontend` = nội dung green, tắt `blueGreen.enabled`, Route lại đơn giản — **chỉ khi** kết thúc lab và cập nhật GitOps có chủ đích.

4. Không tắt `blueGreen` khi vẫn đang demo split.

---

## 8. Checklist tổng (in / tick trên bastion)

- [ ] Shared lib có `frontend-green`; Jenkins BUILD_TARGET hiện option
- [ ] Harbor có `frontend-green:<tag>`
- [ ] `values-images.yaml` có block `frontend-green` đúng tag
- [ ] Sync `mesh-workloads-banking` — Authz/PA edge
- [ ] Sync `banking-frontend` — 3 deploy Ready
- [ ] Xóa deploy `frontend` cũ nếu sót
- [ ] Route `to.name=frontend-edge`, HTTP 200
- [ ] Sync `mesh-waypoint` — HTTPRoute + Gateway Ready
- [ ] B0: 0% GREEN v2
- [ ] B1→B4: % khớp + Kiali thấy 2 version
- [ ] Rollback weight / Route đã thử một lần

---

## 9. Troubleshooting

| Triệu chứng | Kiểm tra / sửa |
|-------------|----------------|
| Jenkins không có `frontend-green` | Push `jenkins-shared-library` main; reload library |
| `ImagePullBackOff` green | Tag Harbor ≠ values; pull secret; đúng repo `frontend-green` |
| Blue mãi `9b04db8` dù values-images đã bump | Pin tag trong `values-frontend-bluegreen.yaml` — **đã bỏ pin**; sync `banking-frontend` |
| `/variant.txt` ra HTML | Blue thiếu file (image cũ). Green có file nhưng B0 = 100% blue → vẫn HTML. Rebuild/sync blue. |
| **UI trần / mất CSS** (Sign in thô) | HTML một version, `/static/*` version kia. Sync edge sticky mới; xóa cookie `fe_bg`; hard refresh |
| Route 503 | `frontend-edge` Ready? PA PERMISSIVE edge? Authz `allow-route-to-frontend-edge`? |
| Luôn blue dù weight green > 0 | HTTPRoute đã sync? `use-waypoint` trên svc/frontend? Waypoint pod Ready? |
| 403 / empty từ edge | Authz cho SA `frontend-edge` + `waypoint` → blue/green |
| Kiali không có mũi tên | UWM + ztunnel PodMonitor; tạo traffic curl/hey; xem `mesh/README.md` |
| `/api` lỗi sau khi qua edge | Edge proxy cả `/` vào VIP; blue/green nginx vẫn proxy Kong — kiểm tra Kong + Route `/api` |
| Deploy `frontend` và blue/green cùng lúc | `oc delete deploy frontend` — giữ svc VIP |

---

## 10. File quan trọng

| Path | Việc |
|------|------|
| [`frontend/`](../../frontend/) | Code blue |
| [`frontend-green/`](../../frontend-green/) | Code green |
| [`gitops/values-images.yaml`](../gitops/values-images.yaml) | Tag CI bump |
| [`gitops/values-frontend-bluegreen.yaml`](../gitops/values-frontend-bluegreen.yaml) | `blueGreen.enabled` |
| Helm `templates/frontend-bluegreen.yaml` + `frontend-edge.yaml` | Deploy dual + edge |
| [`routes/banking-route-frontend.yaml`](../environments/dev-ocp/ocp-values/routes/banking-route-frontend.yaml) | Route → edge |
| [`workloads/banking-*.yaml`](workloads/) | PA / Authz |
| [`waypoint/banking-frontend-bluegreen.yaml`](waypoint/banking-frontend-bluegreen.yaml) | Weights |
| [`waypoint/FRONTEND-WEIGHT-STEPS.md`](waypoint/FRONTEND-WEIGHT-STEPS.md) | Snippet % |
| `jenkins-shared-library/.../Projects.groovy` | Catalog Jenkins |

---

## Ngoài phạm vi

Shop FE, blue-green `api-producer` / transfer, DestinationRule retry, thay Route bằng Gateway API public.
