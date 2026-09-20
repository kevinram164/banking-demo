> Canonical location: banking-demo/phase9-gitops-platform/monitoring/.
> Grafana folder **NPD OCP Infra** (AIOps chart). Alerts: team=platform -> Telegram platform.

# PromQL

Mọi query dashboard join node-exporter `instance` → `nodename` bằng:

```promql
* on(instance) group_left(nodename)
  node_uname_info{job="node-exporter",nodename=~"$node"}
```

`$node` All = `.*`. `$device` / `$interface` tương tự.

## CPU utilization %

```promql
100 * (1 - avg by (nodename) (
  rate(node_cpu_seconds_total{job="node-exporter",mode="idle"}[5m])
  * on(instance) group_left(nodename)
    node_uname_info{job="node-exporter",nodename=~"$node"}
))
```

`rate(idle)` per CPU core; `avg` across cores = idle fraction of the machine. `1 - idle` = busy (user+system+iowait+irq+…).

## CPU idle %

Same without `1 -`. Sanity check: idle + busy ≈ 100%.

## CPU I/O wait %

```promql
100 * avg by (nodename) (
  rate(node_cpu_seconds_total{job="node-exporter",mode="iowait"}[5m])
  * on(instance) group_left(nodename)
    node_uname_info{job="node-exporter",nodename=~"$node"}
)
```

Iowait is **not** "disk is 20% busy". It is "fraction of CPU time waiting on I/O". A node can have high disk `%util` and low iowait if lots of CPU work hides it — look at both.

## Memory utilization %

```promql
100 * (1 - (
  node_memory_MemAvailable_bytes{job="node-exporter"}
  / node_memory_MemTotal_bytes{job="node-exporter"}
))
```

Do not use `MemTotal - MemFree`; that treats page cache as used and always looks "full".

## Filesystem used %

```promql
100 * (1 - (
  node_filesystem_avail_bytes{job="node-exporter",fstype!~"tmpfs|overlay|squashfs|nsfs|iso9660|autofs|devtmpfs"}
  / node_filesystem_size_bytes{job="node-exporter",fstype!~"tmpfs|overlay|squashfs|nsfs|iso9660|autofs|devtmpfs"}
))
```

`avail` is what non-root can still write (respects ext reserved blocks).

## Disk throughput (MiB/s IEC)

```promql
rate(node_disk_read_bytes_total{job="node-exporter",device=~"$device"}[5m])
rate(node_disk_written_bytes_total{job="node-exporter",device=~"$device"}[5m])
```

Grafana unit **`binBps`** (1024-based). 85 MiB/s on the design sketch is this unit, not MB/s SI.

## Disk IOPS

```promql
rate(node_disk_reads_completed_total{job="node-exporter",device=~"$device"}[5m])   # Read IOPS
rate(node_disk_writes_completed_total{job="node-exporter",device=~"$device"}[5m])  # Write IOPS
# Total = read + write rates
```

These are completed I/Os / s (iostat `r/s`, `w/s`), not requests in the scheduler.

## Disk latency (seconds → ms on graph)

```promql
rate(node_disk_read_time_seconds_total{...}[5m])
/
clamp_min(rate(node_disk_reads_completed_total{...}[5m]), 1e-9)
```

Average service time per completed I/O. `clamp_min(..., 1e-9)` prevents `+Inf` when the device is idle (0 completions). Grafana unit `s` renders as milliseconds automatically below 1s.

Write latency: same with `write_time` / `writes_completed`.

## Disk busy % (saturation)

```promql
100 * rate(node_disk_io_time_seconds_total{job="node-exporter",device=~"$device"}[5m])
```

This is iostat **`%util`**: fraction of time the device had at least one I/O in flight. On one spinning disk it saturates near 100%. On NVMe it can sit below 100% while still serving huge IOPS.

### What we do *not* calculate

Hardware queue depth (NVMe SQ/CQ, `nr_requests` occupancy) is **not** in node-exporter. Closest analogue:

```promql
rate(node_disk_io_time_weighted_seconds_total[5m])  # iostat avgqu-sz
```

Treat it as "average in-flight I/Os", not "device QD is 32".

## Network throughput (Mbps)

```promql
rate(node_network_receive_bytes_total{job="node-exporter",device=~"$interface"}[5m]) * 8
rate(node_network_transmit_bytes_total{...}[5m]) * 8
```

Grafana unit **`bps`** (bits). 240 Mbps on the sketch is this, not MiB/s.

Filter (same in alerts): exclude `lo|veth.*|cali.*|tunl.*|cni.*|flannel.*|br-int|genev.*|ovn-k8s-mp0|ovn-k8s-gw0|kube-ipvs0`. Keep `br-ex` and physical NICs.

## Node Ready / pressure

```promql
kube_node_status_condition{condition="Ready",status="true",node=~"$node"}
kube_node_status_condition{condition="MemoryPressure",status="true"}
kube_node_status_condition{condition="DiskPressure",status="true"}
kube_node_status_condition{condition="PIDPressure",status="true"}
kube_node_status_condition{condition="NetworkUnavailable",status="true"}
```

Value `1` means that condition is true. Ready should be 1; the others should be 0.

## API / etcd (control plane)

```promql
sum(rate(apiserver_request_total{job=~"apiserver|kube-apiserver"}[5m]))
sum(rate(apiserver_request_total{job=~"apiserver|kube-apiserver",code=~"5.."}[5m]))
histogram_quantile(0.99, sum by (le) (
  rate(apiserver_request_duration_seconds_bucket{job=~"apiserver|kube-apiserver",verb=~"GET|LIST|POST|PUT|PATCH|DELETE"}[5m])
))

etcd_server_has_leader{job="etcd"}
increase(etcd_server_leader_changes_seen_total{job="etcd"}[15m])
etcd_mvcc_db_total_size_in_bytes{job="etcd"}
  or etcd_debugging_mvcc_db_total_size_in_bytes{job="etcd"}
histogram_quantile(0.99, sum by (le) (rate(etcd_disk_wal_fsync_duration_seconds_bucket{job="etcd"}[5m])))
```

`job=~` covers CMO naming (`apiserver`, `scheduler`) vs vanilla (`kube-apiserver`, `kube-scheduler`).
