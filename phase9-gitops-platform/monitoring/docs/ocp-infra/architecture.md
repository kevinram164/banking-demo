> Canonical location: banking-demo/phase9-gitops-platform/monitoring/.
> Grafana folder **NPD OCP Infra** (AIOps chart). Alerts: team=platform -> Telegram platform.

# Architecture

## Data flow

```text
Master-1..3 / Worker-1..5
   │
   ├─ node-exporter  (DS openshift-monitoring, port 9100)
   ├─ kubelet        (/metrics, /metrics/cadvisor, …)
   ├─ kube-apiserver / kube-controller-manager / kube-scheduler (static pods)
   └─ etcd           (static pod, scraped by CMO)
            │
            ▼
   Platform Prometheus (prometheus-k8s)
            │
            ├──────────────► Alertmanager (CMO)
            │                      │
            │                      ├─ CMO default receivers
            │                      └─ (NPD) Telegram / AIOps webhook — không đổi ở đây
            ▼
      Thanos Querier  :9091
            │
            ▼
      Grafana AIOps  (folder import: OCP Infra)
            ├── Node Overview
            ├── Disk / Storage
            ├── Network
            ├── Cluster Health
            └── Control Plane / etcd
```

User Workload Monitoring **không** nằm trên đường đi này. App ServiceMonitors (banking, shop) là luồng khác, gộp ở Thanos khi Grafana query.

## Why platform Prometheus

| Metric family | Scraped by | PrometheusRule namespace |
|---------------|------------|--------------------------|
| `node_*` | node-exporter / CMO | `openshift-monitoring` |
| `kube_node_*`, `kube_pod_*` | kube-state-metrics / CMO | `openshift-monitoring` |
| `kubelet_*`, `apiserver_*`, `etcd_*` | CMO | `openshift-monitoring` |
| App `/metrics` | UWM | user ns |

Rule đặt nhầm namespace UWM → `NPDInfra*` / `NPDNode*` platform không bao giờ fire.

## Labels used to join node name

node-exporter uses `instance` (often `<IP>:9100`). Human node name is `nodename` on `node_uname_info`.

Dashboards do:

```promql
<metric> * on(instance) group_left(nodename)
  node_uname_info{job="node-exporter",nodename=~"$node"}
```

Kube-state-metrics already has `node=`.

## GitOps

- PrometheusRules: `oc apply -k phase9-gitops-platform/monitoring/manifests/prometheusrules/platform`
  (same pattern as the old `nodes.yaml` — platform Prometheus, cluster-admin).
- `team: platform` → AlertmanagerConfig `npd-telegram-platform` (Telegram).
- Grafana JSON: only in `Open-Source-AIOps-Platform/charts/grafana/dashboards/npd-ocp-infra-*.json`
  (Helm folder **NPD**, titles `NPD OCP Infra / …`). Same pattern as `npd-banking.json`. Sync Argo app `grafana`.

## What we refuse to add

- Second Prometheus / Grafana / node-exporter
- Extra ServiceMonitor for node-exporter (CMO already has it)
- Changes to `cluster-monitoring-config`
