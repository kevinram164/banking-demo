> Canonical location: banking-demo/phase9-gitops-platform/monitoring/.
> Grafana folder **NPD OCP Infra** (AIOps chart). Alerts: team=platform -> Telegram platform.

# Metrics catalog

Nguồn mặc định: **node-exporter / kube-state-metrics / kubelet / apiserver / etcd** do Cluster Monitoring Operator scrape. Job names: `node-exporter`, `kube-state-metrics`, `kubelet`, `apiserver`, `etcd`, `scheduler`, `kube-controller-manager`.

`cluster` trên dashboard là biến hiển thị (`ocp01`). Grafana datasource đã chấm Thanos của cluster này — không nhét `cluster=` vào PromQL (OCP đơn cluster thường **không** có label đó).

## CPU

| Metric | Meaning | Type / unit | Source | Dashboard |
|--------|---------|-------------|--------|-----------|
| `node_cpu_seconds_total` | Seconds each CPU spent in a mode | counter, seconds | node-exporter | Node, Disk (iowait) |
| `node_load1/5/15` | Load average | gauge | node-exporter | Node |

Derived: CPU % = `100 * (1 - avg(rate(idle)))`. I/O wait % = `100 * avg(rate(iowait))`.

## Memory

| Metric | Meaning | Type / unit | Source | Dashboard |
|--------|---------|-------------|--------|-----------|
| `node_memory_MemTotal_bytes` | RAM size | gauge, bytes | node-exporter | Node |
| `node_memory_MemAvailable_bytes` | Estimate of memory for new allocs (includes reclaimable cache) | gauge, bytes | node-exporter | Node |
| `node_memory_Cached_bytes` | Page cache | gauge, bytes | node-exporter | Node |
| `node_memory_Buffers_bytes` | Block buffers | gauge, bytes | node-exporter | Node |
| `node_memory_SwapTotal_bytes` / `SwapFree_bytes` | Swap | gauge, bytes | node-exporter | Node |

Utilization % uses **MemAvailable**, not `MemFree`. That matches Linux and avoids false "90% used" when cache is full.

## Filesystem

| Metric | Meaning | Type / unit | Source | Dashboard |
|--------|---------|-------------|--------|-----------|
| `node_filesystem_size_bytes` | Capacity | gauge, bytes | node-exporter | Node, Disk |
| `node_filesystem_avail_bytes` | Available to non-root | gauge, bytes | node-exporter | Node, Disk |
| `node_filesystem_free_bytes` | Free including reserved | gauge, bytes | node-exporter | (available if needed) |
| `node_filesystem_files` / `files_free` | Inodes | gauge | node-exporter | Disk |
| `node_filesystem_readonly` | 1 if remounted ro | gauge | node-exporter | Disk |

Excluded fstypes: `tmpfs`, `overlay`, `squashfs`, `nsfs`, `iso9660`, `autofs`, `devtmpfs`, `proc`, `sysfs`, `cgroup.*`.

## Disk I/O

| Metric | Meaning | Type / unit | Source | Dashboard |
|--------|---------|-------------|--------|-----------|
| `node_disk_read_bytes_total` | Bytes read | counter, bytes | node-exporter | Node, Disk |
| `node_disk_written_bytes_total` | Bytes written | counter, bytes | node-exporter | Node, Disk |
| `node_disk_reads_completed_total` | Completed reads | counter, ops | node-exporter | Disk |
| `node_disk_writes_completed_total` | Completed writes | counter, ops | node-exporter | Disk |
| `node_disk_read_time_seconds_total` | Cumulative read service time | counter, seconds | node-exporter | Disk |
| `node_disk_write_time_seconds_total` | Cumulative write service time | counter, seconds | node-exporter | Disk |
| `node_disk_io_time_seconds_total` | Time device had I/O in flight | counter, seconds | node-exporter | Disk |
| `node_disk_io_time_weighted_seconds_total` | Weighted I/O time (iostat `aveq`) | counter, seconds | node-exporter | Disk |

Devices excluded: `loop*`, `ram*`, `sr*`, `fd*`. `dm-*` **kept** (LVM).

**Limitation — queue depth:** node-exporter does not export NVMe/SCSI hardware QD. `rate(node_disk_io_time_weighted_seconds_total)` ≈ iostat `avgqu-sz` (average in-flight I/Os at the OS). Dashboards label it that way on purpose.

## Network

| Metric | Meaning | Type / unit | Source | Dashboard |
|--------|---------|-------------|--------|-----------|
| `node_network_receive_bytes_total` | RX bytes | counter, bytes | node-exporter | Node, Network |
| `node_network_transmit_bytes_total` | TX bytes | counter, bytes | node-exporter | Node, Network |
| `node_network_receive_packets_total` | RX packets | counter | node-exporter | Network |
| `node_network_transmit_packets_total` | TX packets | counter | node-exporter | Network |
| `node_network_receive_errs_total` | RX errors | counter | node-exporter | Network |
| `node_network_transmit_errs_total` | TX errors | counter | node-exporter | Network |
| `node_network_receive_drop_total` | RX drops | counter | node-exporter | Network |
| `node_network_transmit_drop_total` | TX drops | counter | node-exporter | Network |

Interface filter: drop `lo`, `veth.*`, `cali.*`, `tunl.*`, `cni.*`, `flannel.*`, `br-int`, `genev.*`, `ovn-k8s-mp0`, `ovn-k8s-gw0`, `kube-ipvs0`. **Keep** `ens*` / `eth*` / `enp*` / `br-ex` (OVN node uplink).

## Kubernetes / OpenShift node

| Metric | Meaning | Type / unit | Source | Dashboard |
|--------|---------|-------------|--------|-----------|
| `kube_node_status_condition` | Ready, MemoryPressure, DiskPressure, PIDPressure, NetworkUnavailable | gauge 0/1 | kube-state-metrics | Cluster, Node |
| `kube_pod_status_phase` | Running/Pending/Failed/… | gauge | kube-state-metrics | Cluster |

## Kubelet

Verified names used by kubelet on OpenShift 4 (job=`kubelet`):

| Metric | Meaning | Dashboard |
|--------|---------|-----------|
| `kubelet_running_pods` | Pods kubelet thinks are running | Control plane |
| `kubelet_runtime_operations_total` | CRI ops | Control plane |
| `kubelet_runtime_operations_errors_total` | CRI errors | Control plane |
| `kubelet_pleg_relist_duration_seconds_bucket` | PLEG relist latency | Control plane |
| `rest_client_requests_total{job="kubelet"}` | Kubelet → API | Control plane |
| `storage_operation_duration_seconds_count` | Volume ops (if present) | Control plane |

If a panel is empty, the metric is absent on this OCP version — do not invent replacements.

## Control plane / etcd

| Metric | Meaning | Dashboard |
|--------|---------|-----------|
| `apiserver_request_total` | API request counter (code/verb) | Control plane |
| `apiserver_request_duration_seconds_bucket` | API latency histogram | Control plane |
| `etcd_server_has_leader` | 1 if member sees a leader | Control plane |
| `etcd_server_leader_changes_seen_total` | Leadership elections | Control plane |
| `etcd_mvcc_db_total_size_in_bytes` | DB file size (fallback: `etcd_debugging_mvcc_db_total_size_in_bytes`) | Control plane |
| `etcd_disk_wal_fsync_duration_seconds_bucket` | WAL fsync | Control plane |
| `etcd_disk_backend_commit_duration_seconds_bucket` | Backend commit | Control plane |
| `up{job="etcd\|apiserver\|scheduler\|kube-controller-manager"}` | Scrape health | Control plane |
| `scheduler_schedule_attempts_total` | Schedule results | Control plane |
| `workqueue_depth` | Controller queues | Control plane |

## Alert thresholds (tunable)

All values live in `prometheus/rules/*.yaml` as `annotations.threshold`.

| Alert | Initial threshold | `for` | Why |
|-------|-------------------|-------|-----|
| Node CPU | > 85% | 10m | Avoid build spikes |
| Node memory | > 90% MemAvailable-based | 10m | Cache is available |
| Filesystem | > 85% / > 95% | 15m / 5m | 95% is near DiskPressure |
| Inodes | > 90% | 15m | Separate from bytes |
| CPU iowait | > 20% | 10m | Severe; use 10% on NVMe |
| Disk latency | > 50 ms avg | 10m | VMware/NFS baseline; 20ms for flash |
| Disk busy | > 80% util | 15m | Skip backup spikes |
| NIC errors/drops | > 1 /s | 10m | Skip single CRC |
| NotReady / pressure | condition true | 5m | Kubelet view |
| etcd no leader | `has_leader==0` | 1m | Already broken |
| etcd leader changes | > 3 / 15m | 0 (windowed) | Disk or master NIC |
| API 5xx ratio | > 5% | 10m | Coarse; CMO has SLO burn |

Tune by editing the YAML; do not chase noisiness by shortening `for:` first — lengthen it or raise the number.
