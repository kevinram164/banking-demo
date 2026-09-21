# Troubleshooting: Instana Host Agent → TechZone (self-hosted)

Tài liệu ghi lại sự cố kết nối host agent từ lab OCP (`ocp01`) tới Instana TechZone (`itz-tdl40p`), nguyên nhân và cách xử lý đã xác nhận.

| | |
|--|--|
| **Lab** | OCP cluster `ocp01` — namespace `instana-agent` |
| **Backend** | TechZone Instana — unit `poc-mcredit` |
| **UI** | `https://instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com/` |
| **Agent endpoint (đúng)** | `agent-acceptor.instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com:443` |

---

## 1. Triệu chứng

### 1.1 Timeout tới `:1443`

```text
Could not connect to agent-acceptor…:1443
connection timed out … /67.18.131.144:1443
```

Agent/UI wizard lúc đầu hướng dẫn `endpointPort=1443`. Từ lab **không** mở được TCP 1443 (firewall TechZone chỉ expose SSH / router 443).

### 1.2 Connected nhưng 404

```text
Connected using HTTP/2 to agent-acceptor…:443
Endpoint not found (404) for Backend … Either wrong endpoint configured
  or an endpoint used that the current backend doesn't understand.
```

Trên TechZone, log `gateway-v2`:

```text
"POST /metrics HTTP/2" 404 NR …
```

`NR` = Envoy **No Route** — request tới gateway nhưng **không khớp** virtual-host / listener cho agent API.

### 1.3 Nhầm “sai agent key”

UI Deploy Agent chỉ có **một** key; agent đã dùng đúng key đó. 404 **không** phải do key sai unit.

### 1.4 NodePort / IP nhầm

| Endpoint firewall | Ý nghĩa |
|-------------------|----------|
| `67.18.131.144:10022` | Bastion SSH |
| `67.18.131.144:443` | OpenShift **router** (UI + Routes) |
| `67.18.131.61:31443` | NodePort OCP Cluster (sau khi mở firewall) |

- `nc …144 31443` → timeout (port không map trên IP bastion).
- `nc …61 31443` → Connected sau khi có Service NodePort.
- Agent nối bằng **IP** `:31443` vẫn 404 vì thiếu TLS **SNI** hostname `agent-acceptor…`.

---

## 2. Kiến trúc liên quan

```text
Lab OCP agent
    │  TLS + SNI: agent-acceptor…:443
    ▼
Internet / TechZone LB  (DNS apps → thường .144)
    │
    ▼
OpenShift Route "acceptor" (TLS passthrough)
    host: agent-acceptor.instana.apps.…
    to:   gateway-v2
    │
    ▼
gateway-v2 (Envoy)
    │  phải có filter/route cho SNI agent-acceptor
    │  trên listener tương ứng Core acceptors.agent.port
    ▼
service acceptor → Instana backend
```

**UI và agent cùng port 443 ngoài, nhưng khác hostname → khác Route / listener.**

- `instana.apps…` / `poc-mcredit.instana…` → UI  
- `agent-acceptor.instana…` → agent acceptor  

Vào được UI **không** đồng nghĩa agent acceptor đã đúng.

Core CR (ban đầu):

```yaml
spec:
  acceptors:
    agent:
      host: agent-acceptor.instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com
      port: 1443          # ← lệch với đường lab chỉ ra được :443
  baseDomain: instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com
```

Gateway có port nội bộ `1444` (acceptor) và `8443` (HTTPS/router). Agent phải vào đúng listener mà Core khai báo.

---

## 3. Root cause (tóm tắt)

1. **Port Core = 1443**, lab/firewall **không** tới được 1443.  
2. Agent chuyển sang **`:443`** (Route có sẵn) → TLS OK nhưng gateway trả **404 NR** vì Core/gateway vẫn config agent trên listener **1443/1444**, không phải listener Route 443.  
3. Key đúng; DNS `.144` cho `*.apps` là bình thường (cùng IP public, khác port/service).  
4. Workaround NodePort cần đúng IP (`.61`), đúng targetPort (`1444`), và **SNI = FQDN** — phức tạp hơn so với sửa Core.

---

## 4. Cách xử lý đã áp dụng (khuyến nghị)

### Bước A — Sửa Core trên TechZone (chìa khóa)

Trên bastion TechZone:

```bash
oc -n instana-core get core instana-core \
  -o jsonpath='{.spec.acceptors.agent}' ; echo

# Đổi port agent acceptor → 443 (khớp Route + firewall lab)
oc -n instana-core patch core instana-core --type=json -p='[
  {"op":"replace","path":"/spec/acceptors/agent/port","value":443}
]'

oc -n instana-core get core instana-core -o jsonpath='{.spec.acceptors.agent}' ; echo
oc -n instana-core rollout status deploy/gateway-v2
```

Sau reconcile, gateway gắn traffic SNI `agent-acceptor` trên listener phục vụ `:443`.

### Bước B — Agent trên lab OCP

```bash
helm upgrade instana-agent instana-agent \
  --repo https://agents.instana.io/helm \
  -n instana-agent --reuse-values \
  --set openshift=true \
  --set agent.endpointHost=agent-acceptor.instana.apps.itz-tdl40p.infra01-lb.dal14.techzone.ibm.com \
  --set agent.endpointPort=443 \
  --set cluster.name=ocp01 \
  --set agent.key='<KEY_FROM_UI>' \
  --set agent.downloadKey='<KEY_FROM_UI>'

# SCC (OCP)
oc adm policy add-scc-to-user privileged -z instana-agent -n instana-agent
```

### Bước C — Verify

```bash
# Lab — Backend.cfg
kubectl exec -n instana-agent ds/instana-agent -c instana-agent -- \
  cat /opt/instana/agent/etc/instana/com.instana.agent.main.sender.Backend-1.cfg
# host=agent-acceptor…  port=443

# Log (tránh grep '404' trần — khớp nhầm timestamp .404)
kubectl logs -n instana-agent -l app.kubernetes.io/component=instana-agent -c instana-agent --since=5m \
  | grep -E 'Connected using HTTP/2|Endpoint not found|Announced|timed out'
```

**Thành công:**

```text
Connected using HTTP/2 to agent-acceptor…:443 …
```

**Không** còn `Endpoint not found (404)`.

UI → unit **poc-mcredit** → **Infrastructure Map**: host `npd-ocp-worker*`, cluster `ocp01`.

### Label log đúng (operator chart)

```bash
# Host agent DaemonSet — KHÔNG dùng component=agent
kubectl logs -n instana-agent -l app.kubernetes.io/component=instana-agent -c instana-agent

# k8sensor (K8s metrics) — khác component
kubectl logs -n instana-agent -l app.kubernetes.io/component=k8sensor
```

---

## 5. Workaround đã thử (không cần nếu đã sửa Core → 443)

Giữ lại để hiểu / lab tương tự:

1. Firewall TechZone → **OCP Cluster** → NodePort (vd. `31443`).  
2. External endpoint: **`67.18.131.61:31443`** (không dùng `.144`).  
3. Service NodePort → `gateway-v2` **targetPort acceptor (1444)**.  
4. Agent: FQDN + port NodePort **và** DNS/hostAliases trỏ FQDN → `.61` (để có SNI).  
   - CRD InstanaAgent **không** hỗ trợ `hostAliases`.  
   - Edit CoreDNS `dns-default` bị DNS Operator ghi đè.

→ Phức tạp hơn nhiều so với **Core `port: 443`**.

---

## 6. So với Instana SaaS

| | SaaS | TechZone self-hosted |
|--|------|----------------------|
| Endpoint | `ingress-*-saas.instana.io:443` đã public | Tự cấu hình acceptor host/port + Route + firewall |
| Agent chỉ cần | key + host UI đưa | Đúng **port Core**, đúng **hostname acceptor**, path mạng mở |
| UI :443 lên được | Thường đủ cho agent | Chỉ chứng minh router sống — **chưa** đủ nếu Core vẫn `:1443` |

---

## 7. Checklist nhanh khi lại 404 / timeout

1. `oc -n instana-core get core … -o jsonpath='{.spec.acceptors.agent}'` → `port` phải khớp agent.  
2. `nc -zv agent-acceptor… <port>` từ lab.  
3. Log gateway: `404 NR` = sai listener/SNI; timeout = firewall/mạng.  
4. Backend.cfg: host FQDN (không IP nếu gateway bắt SNI), port đúng.  
5. Key lấy từ UI **cùng** Instana instance (thường không phải nguyên nhân 404 NR).

---

## 8. Ghi chú thêm (lab ocp01)

- **1 agent Pending / Insufficient cpu**: worker04 request CPU ~97%. Hạ `agent.pod.requests.cpu` (vd. `50m`) hoặc giải phóng request trên node.  
- **Services banking/shop trên UI**: cần OTLP traces (app → collector → agent `:4317` hoặc OTLP acceptor). Host agent chỉ mang Infrastructure; xem `DEPLOY.md` + exporter `otlp/instana` trên shared collector.  
- File values collector OCP hiện trỏ `values-otel-collector-k3d.yaml` (tên lịch sử) — Argo app `observability-otel-collector` dùng file đó.
