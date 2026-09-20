> Canonical location: banking-demo/phase9-gitops-platform/monitoring/.
> Grafana folder **NPD OCP Infra** (AIOps chart). Alerts: team=platform -> Telegram platform.

# Troubleshooting

## Is this node slow because of CPU, memory, disk, or network?

Open **OCP Infra / Node Overview**, set `node`. Then:

| You see | Likely cause | Next dashboard |
|---------|--------------|----------------|
| CPU % high, iowait low | Compute saturation / too many pods | Cluster (who is on the node) |
| CPU iowait high | Waiting on storage | Disk — latency + busy% + device |
| Memory % high + MemoryPressure | RAM, evictions | `oc describe node` + Cluster |
| Disk busy high / latency tens of ms | Storage path (VMDK, NFS, vSAN, iSCSI) | Disk with `$device` |
| RX/TX tiny, errors/drops rising | NIC / vSwitch | Network |
| Ready=0 | kubelet/CNI/disk | Cluster + `oc describe node` |

Target sketch (`worker-02` + `sdb`): use **Disk** dashboard for sdb numbers; Node overview for CPU/mem/net.

## Panel "No data"

1. Grafana datasource must be **Prometheus → Thanos Querier**, not UWM-only.
2. Variable `$node` All / regex must match `node_uname_info.nodename` (not necessarily kube `metadata.name` if they differ — on OCP they usually match).
3. Disk device names: `lsblk` on the node (`sda` vs `nvme0n1` vs `dm-0`).
4. Control-plane panels: confirm `up{job="etcd"}`, `up{job="apiserver"}` via Explore. Job names differ by OCP version — matchers already allow both.
5. `storage_operation_duration_seconds_count` may be absent — leave the panel empty; do not fake a metric.

## Alerts duplicate / noisy

| This pack | Already elsewhere |
|-----------|-------------------|
| `NPDNodeNotReady` | CMO `KubeNodeNotReady` |
| `NPDNodeHighCPU` / `NPDNodeMemoryPressure` | (this file — kept names) |
| `NPDInfraFilesystem*` | CMO `NodeFilesystemSpaceFillingUp` |
| `NPDInfraEtcdNoLeader` | CMO `etcdNoLeader` |

**Do not delete CMO rules.** To quiet this pack, delete or comment the overlapping `alert:` in `prometheus/rules/` and re-apply. Prefer keeping **iowait / disk latency / disk busy / NIC drops** — those are the gaps.

## node-exporter not on every node

```bash
oc get ds node-exporter -n openshift-monitoring
oc get pods -n openshift-monitoring -l app.kubernetes.io/name=node-exporter -o wide
```

Ready should equal master+worker count. Missing a node: kubelet down, taints without matching toleration (CMO DS already tolerates masters), or the node NotReady.

## PrometheusRule not loading

```bash
oc get prometheusrule -n openshift-monitoring npd-ocp-node-alerts -o yaml
# labels must include prometheus=k8s and role=alert-rules
oc logs -n openshift-monitoring prometheus-k8s-0 -c prometheus | grep -i rule
```

Wrong namespace (UWM) = silent no-op for node metrics.

## Grafana dashboards missing

JSON lives in `Open-Source-AIOps-Platform/charts/grafana/dashboards/npd-ocp-infra-*.json`.
They appear in Grafana folder **NPD** after Argo syncs the Grafana chart (`NPD OCP Infra / …`).

```bash
python phase9-gitops-platform/monitoring/scripts/generate_ocp_infra_dashboards.py
```

## Dry-run / apply

```bash
oc apply --dry-run=client -k phase9-gitops-platform/monitoring/manifests/prometheusrules/platform
oc apply -k phase9-gitops-platform/monitoring/manifests/prometheusrules/platform
```

Never `oc delete` CMO resources from this tree. Objects are named `npd-ocp-*-alerts`.

## Live PromQL smoke (bastion)

```bash
TH=https://thanos-querier.openshift-monitoring.svc:9091
TOKEN=$(oc whoami -t)

# node-exporter coverage
curl -sk -H "Authorization: Bearer $TOKEN" \
  --data-urlencode 'query=count(up{job="node-exporter"}==1)' \
  "$TH/api/v1/query"

# one node CPU
curl -sk -H "Authorization: Bearer $TOKEN" \
  --data-urlencode 'query=100*(1-avg(rate(node_cpu_seconds_total{job="node-exporter",mode="idle"}[5m])))' \
  "$TH/api/v1/query"
```

This workstation did not have `oc` on PATH and kubeconfig pointed at another API (`10.100.1.120`) that timed out — run the smoke test on the OCP bastion.
