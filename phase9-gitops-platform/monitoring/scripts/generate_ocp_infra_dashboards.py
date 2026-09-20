#!/usr/bin/env python3
"""Generate Grafana 11 dashboards for OpenShift infrastructure monitoring.

Units (documented in docs/promql.md):
  Disk throughput  -> Grafana unit binBps (IEC: KiB/s, MiB/s)
  Network          -> Grafana unit bps (bits/s: Mbps)
  Disk latency     -> seconds (Grafana unit s, displayed as ms)
  Disk busy        -> percent (iostat %util from node_disk_io_time_seconds_total)
"""
from __future__ import annotations

import json
from pathlib import Path


def find_workspace() -> Path:
    here = Path.cwd()
    for p in [here, *here.parents]:
        if (p / "banking-demo").is_dir() and (p / "Open-Source-AIOps-Platform").is_dir():
            return p
        if (p / "phase9-gitops-platform").is_dir() and (
            p.parent / "Open-Source-AIOps-Platform"
        ).is_dir():
            return p.parent
    raise SystemExit(
        "Run from OCP workspace (sibling banking-demo + Open-Source-AIOps-Platform)"
    )


DS = {"type": "prometheus", "uid": "${datasource}"}

# OpenShift node-exporter join: instance (IP:9100) -> nodename
NODE = (
    '* on(instance) group_left(nodename) '
    'node_uname_info{job="node-exporter",nodename=~"$node"}'
)
FS = 'fstype!~"tmpfs|overlay|squashfs|nsfs|iso9660|autofs|devtmpfs|proc|sysfs|cgroup.*"'
DISK = 'device!~"^(loop|ram|sr|fd).*"'
# Keep physical / br-ex (OVN uplink). Drop veth, tunnel, node overlay mgmt.
NET = (
    'device!~"lo|veth.*|cali.*|tunl.*|cni.*|flannel.*|'
    'br-int|genev.*|ovn-k8s-mp0|ovn-k8s-gw0|kube-ipvs0"'
)


def datasource_var() -> dict:
    return {
        "name": "datasource",
        "type": "datasource",
        "query": "prometheus",
        "current": {"text": "Prometheus", "value": "Prometheus"},
        "hide": 0,
        "label": "Datasource",
    }


def query_var(name: str, query: str, include_all: bool = True, all_value: str = ".*",
              label: str | None = None, multi: bool = True) -> dict:
    return {
        "name": name,
        "label": label or name,
        "type": "query",
        "datasource": DS,
        "query": query,
        "refresh": 2,
        "includeAll": include_all,
        "allValue": all_value,
        "multi": multi,
        "sort": 1,
        "current": {"text": "All", "value": "$__all"} if include_all else {},
    }


def custom_var(name: str, value: str, label: str | None = None) -> dict:
    return {
        "name": name,
        "label": label or name,
        "type": "custom",
        "query": value,
        "current": {"text": value, "value": value},
        "options": [{"text": value, "value": value, "selected": True}],
        "hide": 0,
    }


def target(expr: str, legend: str, ref: str = "A") -> dict:
    return {
        "datasource": DS,
        "expr": expr,
        "legendFormat": legend,
        "refId": ref,
        "editorMode": "code",
        "range": True,
    }


def grid(x: int, y: int, w: int, h: int) -> dict:
    return {"x": x, "y": y, "w": w, "h": h}


def field_defaults(unit: str, extra: dict | None = None) -> dict:
    cfg = {
        "unit": unit,
        "custom": {
            "drawStyle": "line",
            "lineInterpolation": "smooth",
            "lineWidth": 1,
            "fillOpacity": 12,
            "spanNulls": True,
            "showPoints": "never",
            "axisBorderShow": False,
        },
    }
    if extra:
        cfg.update(extra)
    return cfg


def ts(pid: int, title: str, expr: str, x: int, y: int, w: int = 12, h: int = 8,
       unit: str = "percent", legend: str = "{{nodename}}", description: str = "",
       extra_targets: list | None = None, thresholds: list | None = None) -> dict:
    defaults = field_defaults(unit)
    if thresholds:
        defaults["thresholds"] = {
            "mode": "absolute",
            "steps": thresholds,
        }
        defaults["custom"]["thresholdsStyle"] = {"mode": "dashed"}
    panel = {
        "id": pid,
        "type": "timeseries",
        "title": title,
        "description": description,
        "gridPos": grid(x, y, w, h),
        "datasource": DS,
        "targets": [target(expr, legend)] + (extra_targets or []),
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "legend": {
                "displayMode": "table",
                "placement": "bottom",
                "calcs": ["mean", "lastNotNull", "max"],
                "showLegend": True,
            },
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
    }
    return panel


def stat(pid: int, title: str, expr: str, x: int, y: int, w: int = 4, h: int = 4,
         unit: str = "percent", legend: str = "{{nodename}}", description: str = "",
         steps: list | None = None) -> dict:
    steps = steps or [
        {"color": "green", "value": None},
        {"color": "yellow", "value": 70},
        {"color": "red", "value": 85},
    ]
    return {
        "id": pid,
        "type": "stat",
        "title": title,
        "description": description,
        "gridPos": grid(x, y, w, h),
        "datasource": DS,
        "targets": [target(expr, legend)],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "decimals": 1,
                "thresholds": {"mode": "absolute", "steps": steps},
                "color": {"mode": "thresholds"},
            },
            "overrides": [],
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "orientation": "auto",
            "textMode": "value_and_name",
            "colorMode": "value",
            "graphMode": "area",
            "justifyMode": "auto",
        },
    }


def table(pid: int, title: str, expr: str, x: int, y: int, w: int = 24, h: int = 8,
          description: str = "") -> dict:
    return {
        "id": pid,
        "type": "table",
        "title": title,
        "description": description,
        "gridPos": grid(x, y, w, h),
        "datasource": DS,
        "targets": [{
            "datasource": DS,
            "expr": expr,
            "format": "table",
            "instant": True,
            "refId": "A",
        }],
        "transformations": [
            {"id": "organize", "options": {"excludeByName": {"Time": True, "__name__": True}}},
        ],
        "fieldConfig": {
            "defaults": {
                "custom": {"align": "auto"},
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "green", "value": None},
                        {"color": "red", "value": 1},
                    ],
                },
            },
            "overrides": [],
        },
        "options": {"showHeader": True, "footer": {"show": False}},
    }


def row(pid: int, title: str, y: int) -> dict:
    return {
        "id": pid,
        "type": "row",
        "title": title,
        "gridPos": grid(0, y, 24, 1),
        "collapsed": False,
        "panels": [],
    }


def dashboard(uid: str, title: str, tags: list[str], variables: list, panels: list,
              description: str) -> dict:
    return {
        "uid": uid,
        "title": title,
        "description": description,
        "tags": tags,
        "timezone": "browser",
        "editable": True,
        "graphTooltip": 1,
        "schemaVersion": 39,
        "version": 1,
        "refresh": "30s",
        "time": {"from": "now-1h", "to": "now"},
        "timepicker": {},
        "annotations": {"list": []},
        "templating": {"list": variables},
        "panels": panels,
        "links": [
            {"title": "Node Overview", "type": "link",
             "url": "/d/ocp-infra-node", "keepTime": True},
            {"title": "Disk", "type": "link",
             "url": "/d/ocp-infra-disk", "keepTime": True},
            {"title": "Network", "type": "link",
             "url": "/d/ocp-infra-net", "keepTime": True},
            {"title": "Cluster", "type": "link",
             "url": "/d/ocp-infra-cluster", "keepTime": True},
            {"title": "Control Plane", "type": "link",
             "url": "/d/ocp-infra-cp", "keepTime": True},
        ],
    }


def warn_cpu():
    return [
        {"color": "green", "value": None},
        {"color": "yellow", "value": 70},
        {"color": "red", "value": 85},
    ]


def warn_mem():
    return [
        {"color": "green", "value": None},
        {"color": "yellow", "value": 80},
        {"color": "red", "value": 90},
    ]


def warn_io():
    return [
        {"color": "green", "value": None},
        {"color": "yellow", "value": 10},
        {"color": "red", "value": 20},
    ]


# --- PromQL -----------------------------------------------------------------

CPU_PCT = f'''100 * (1 - avg by (nodename) (
  rate(node_cpu_seconds_total{{job="node-exporter",mode="idle"}}[5m])
  {NODE}
))'''

CPU_IDLE = f'''100 * avg by (nodename) (
  rate(node_cpu_seconds_total{{job="node-exporter",mode="idle"}}[5m])
  {NODE}
)'''

CPU_IOWAIT = f'''100 * avg by (nodename) (
  rate(node_cpu_seconds_total{{job="node-exporter",mode="iowait"}}[5m])
  {NODE}
)'''

LOAD1 = f'node_load1{{job="node-exporter"}} {NODE}'
LOAD5 = f'node_load5{{job="node-exporter"}} {NODE}'
LOAD15 = f'node_load15{{job="node-exporter"}} {NODE}'

MEM_PCT = f'''100 * (1 - (
  node_memory_MemAvailable_bytes{{job="node-exporter"}}
  / node_memory_MemTotal_bytes{{job="node-exporter"}}
)) {NODE}'''

MEM_AVAIL = f'node_memory_MemAvailable_bytes{{job="node-exporter"}} {NODE}'
MEM_CACHED = f'node_memory_Cached_bytes{{job="node-exporter"}} {NODE}'
MEM_BUFFERS = f'node_memory_Buffers_bytes{{job="node-exporter"}} {NODE}'
SWAP_USED = f'''(
  node_memory_SwapTotal_bytes{{job="node-exporter"}}
  - node_memory_SwapFree_bytes{{job="node-exporter"}}
) {NODE}'''

FS_PCT = f'''100 * (1 - (
  node_filesystem_avail_bytes{{job="node-exporter",{FS}}}
  / node_filesystem_size_bytes{{job="node-exporter",{FS}}}
)) {NODE}'''

FS_MAX = f'''max by (nodename) (
  100 * (1 - (
    node_filesystem_avail_bytes{{job="node-exporter",{FS}}}
    / node_filesystem_size_bytes{{job="node-exporter",{FS}}}
  )) {NODE}
)'''

INODE_PCT = f'''100 * (1 - (
  node_filesystem_files_free{{job="node-exporter",{FS}}}
  / clamp_min(node_filesystem_files{{job="node-exporter",{FS}}}, 1)
)) {NODE}'''

DISK_READ = f'''rate(node_disk_read_bytes_total{{job="node-exporter",{DISK},device=~"$device"}}[5m])
{NODE}'''

DISK_WRITE = f'''rate(node_disk_written_bytes_total{{job="node-exporter",{DISK},device=~"$device"}}[5m])
{NODE}'''

DISK_READ_SUM = f'''sum by (nodename) (
  rate(node_disk_read_bytes_total{{job="node-exporter",{DISK}}}[5m]) {NODE}
)'''

DISK_WRITE_SUM = f'''sum by (nodename) (
  rate(node_disk_written_bytes_total{{job="node-exporter",{DISK}}}[5m]) {NODE}
)'''

READ_IOPS = f'''rate(node_disk_reads_completed_total{{job="node-exporter",{DISK},device=~"$device"}}[5m])
{NODE}'''

WRITE_IOPS = f'''rate(node_disk_writes_completed_total{{job="node-exporter",{DISK},device=~"$device"}}[5m])
{NODE}'''

TOTAL_IOPS = f'''(
  rate(node_disk_reads_completed_total{{job="node-exporter",{DISK},device=~"$device"}}[5m])
  + rate(node_disk_writes_completed_total{{job="node-exporter",{DISK},device=~"$device"}}[5m])
) {NODE}'''

READ_LAT = f'''(
  rate(node_disk_read_time_seconds_total{{job="node-exporter",{DISK},device=~"$device"}}[5m])
  /
  clamp_min(rate(node_disk_reads_completed_total{{job="node-exporter",{DISK},device=~"$device"}}[5m]), 1e-9)
) {NODE}'''

WRITE_LAT = f'''(
  rate(node_disk_write_time_seconds_total{{job="node-exporter",{DISK},device=~"$device"}}[5m])
  /
  clamp_min(rate(node_disk_writes_completed_total{{job="node-exporter",{DISK},device=~"$device"}}[5m]), 1e-9)
) {NODE}'''

DISK_BUSY = f'''100 * rate(node_disk_io_time_seconds_total{{job="node-exporter",{DISK},device=~"$device"}}[5m])
{NODE}'''

# iostat avgqu-sz analogue — NOT hardware queue depth
DISK_AVGQU = f'''rate(node_disk_io_time_weighted_seconds_total{{job="node-exporter",{DISK},device=~"$device"}}[5m])
{NODE}'''

NET_RX = f'''rate(node_network_receive_bytes_total{{job="node-exporter",{NET},device=~"$interface"}}[5m]) * 8
{NODE}'''

NET_TX = f'''rate(node_network_transmit_bytes_total{{job="node-exporter",{NET},device=~"$interface"}}[5m]) * 8
{NODE}'''

NET_RX_SUM = f'''sum by (nodename) (
  rate(node_network_receive_bytes_total{{job="node-exporter",{NET}}}[5m]) * 8 {NODE}
)'''

NET_TX_SUM = f'''sum by (nodename) (
  rate(node_network_transmit_bytes_total{{job="node-exporter",{NET}}}[5m]) * 8 {NODE}
)'''

NET_RX_PKT = f'''rate(node_network_receive_packets_total{{job="node-exporter",{NET},device=~"$interface"}}[5m])
{NODE}'''

NET_TX_PKT = f'''rate(node_network_transmit_packets_total{{job="node-exporter",{NET},device=~"$interface"}}[5m])
{NODE}'''

NET_RX_ERR = f'''rate(node_network_receive_errs_total{{job="node-exporter",{NET},device=~"$interface"}}[5m])
{NODE}'''

NET_TX_ERR = f'''rate(node_network_transmit_errs_total{{job="node-exporter",{NET},device=~"$interface"}}[5m])
{NODE}'''

NET_RX_DROP = f'''rate(node_network_receive_drop_total{{job="node-exporter",{NET},device=~"$interface"}}[5m])
{NODE}'''

NET_TX_DROP = f'''rate(node_network_transmit_drop_total{{job="node-exporter",{NET},device=~"$interface"}}[5m])
{NODE}'''


def vars_node(cluster: bool = True, device: bool = False, interface: bool = False) -> list:
    v = [datasource_var()]
    if cluster:
        v.append(custom_var("cluster", "ocp01", "Cluster"))
    v.append(query_var(
        "node",
        'label_values(node_uname_info{job="node-exporter"}, nodename)',
        label="Node",
    ))
    if device:
        v.append(query_var(
            "device",
            f'label_values(node_disk_read_bytes_total{{job="node-exporter",{DISK}}} {NODE}, device)',
            label="Device",
        ))
    if interface:
        v.append(query_var(
            "interface",
            f'label_values(node_network_receive_bytes_total{{job="node-exporter",{NET}}} {NODE}, device)',
            label="Interface",
        ))
    return v


def node_infrastructure() -> dict:
    # Overview: cluster + node only (device/interface All via implicit sum / by-device series)
    # Disk/net panels on this dashboard show ALL devices/interfaces of the selected node.
    panels = [
        row(1, "Status — answer: CPU, memory, disk, or network?", 0),
        stat(2, "Node Ready",
             'max by (node) (kube_node_status_condition{condition="Ready",status="true",node=~"$node"})',
             0, 1, 4, 4, unit="bool", legend="{{node}}",
             description="1 = Ready. 0 = NotReady.",
             steps=[{"color": "red", "value": None}, {"color": "green", "value": 1}]),
        stat(3, "CPU %", CPU_PCT, 4, 1, 4, 4, description="100 * (1 - avg idle). All cores.",
             steps=warn_cpu()),
        stat(4, "CPU I/O Wait %", CPU_IOWAIT, 8, 1, 4, 4,
             description="Time cores wait for block I/O. Correlate with Disk dashboard.",
             steps=warn_io()),
        stat(5, "Memory %", MEM_PCT, 12, 1, 4, 4,
             description="100 * (1 - MemAvailable/MemTotal). Includes cache as available.",
             steps=warn_mem()),
        stat(6, "Worst filesystem %", FS_MAX, 16, 1, 4, 4,
             description="Max used% across real filesystems (tmpfs/overlay excluded).",
             steps=warn_cpu()),
        stat(7, "Load 1", LOAD1, 20, 1, 4, 4, unit="short",
             description="1-minute load average. Compare with CPU count.",
             steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 8},
                    {"color": "red", "value": 16}]),

        stat(8, "Network RX", NET_RX_SUM, 0, 5, 4, 4, unit="bps",
             description="Sum of physical/uplink RX. Unit: bits/s (Mbps)."),
        stat(9, "Network TX", NET_TX_SUM, 4, 5, 4, 4, unit="bps",
             description="Sum of physical/uplink TX. Unit: bits/s (Mbps)."),
        stat(10, "Disk read", DISK_READ_SUM, 8, 5, 4, 4, unit="binBps",
             description="Sum of block-device read throughput. Unit: MiB/s (IEC)."),
        stat(11, "Disk write", DISK_WRITE_SUM, 12, 5, 4, 4, unit="binBps",
             description="Sum of block-device write throughput. Unit: MiB/s (IEC)."),
        stat(12, "Read IOPS (sum)",
             f'sum by (nodename) (rate(node_disk_reads_completed_total{{job="node-exporter",{DISK}}}[5m]) {NODE})',
             16, 5, 4, 4, unit="iops"),
        stat(13, "Write IOPS (sum)",
             f'sum by (nodename) (rate(node_disk_writes_completed_total{{job="node-exporter",{DISK}}}[5m]) {NODE})',
             20, 5, 4, 4, unit="iops"),

        row(20, "CPU / load / I/O wait", 9),
        ts(21, "CPU utilization %", CPU_PCT, 0, 10, 12, 8, unit="percent",
           description="Per node. Thresholds 70 / 85%."),
        ts(22, "CPU I/O Wait %", CPU_IOWAIT, 12, 10, 12, 8, unit="percent",
           description="High iowait + high disk latency = storage bottleneck, not CPU starve."),
        ts(23, "Load average", LOAD1, 0, 18, 12, 8, unit="short", legend="{{nodename}} load1",
           extra_targets=[
               target(LOAD5, "{{nodename}} load5", "B"),
               target(LOAD15, "{{nodename}} load15", "C"),
           ]),
        ts(24, "CPU idle %", CPU_IDLE, 12, 18, 12, 8),

        row(30, "Memory", 26),
        ts(31, "Memory utilization %", MEM_PCT, 0, 27, 12, 8, unit="percent"),
        ts(32, "Memory available / cache / buffers", MEM_AVAIL, 12, 27, 12, 8, unit="bytes",
           legend="{{nodename}} available",
           extra_targets=[
               target(MEM_CACHED, "{{nodename}} cached", "B"),
               target(MEM_BUFFERS, "{{nodename}} buffers", "C"),
               target(SWAP_USED, "{{nodename}} swap used", "D"),
           ]),

        row(40, "Disk (all devices of selected node) — pick a device on Disk dashboard", 35),
        ts(41, "Disk throughput",
           f'rate(node_disk_read_bytes_total{{job="node-exporter",{DISK}}}[5m]) {NODE}',
           0, 36, 12, 8, unit="binBps", legend="{{nodename}} {{device}} read",
           extra_targets=[
               target(f'rate(node_disk_written_bytes_total{{job="node-exporter",{DISK}}}[5m]) {NODE}',
                      "{{nodename}} {{device}} write", "B"),
           ],
           description="IEC bytes/s (MiB/s). Filter one device on Disk / Storage dashboard."),
        ts(42, "Disk IOPS",
           f'rate(node_disk_reads_completed_total{{job="node-exporter",{DISK}}}[5m]) {NODE}',
           12, 36, 12, 8, unit="iops", legend="{{nodename}} {{device}} read",
           extra_targets=[
               target(f'rate(node_disk_writes_completed_total{{job="node-exporter",{DISK}}}[5m]) {NODE}',
                      "{{nodename}} {{device}} write", "B"),
           ]),
        ts(43, "Disk latency (avg per I/O)",
           f'''(
             rate(node_disk_read_time_seconds_total{{job="node-exporter",{DISK}}}[5m])
             / clamp_min(rate(node_disk_reads_completed_total{{job="node-exporter",{DISK}}}[5m]), 1e-9)
           ) {NODE}''',
           0, 44, 12, 8, unit="s", legend="{{nodename}} {{device}} read",
           extra_targets=[
               target(f'''(
                 rate(node_disk_write_time_seconds_total{{job="node-exporter",{DISK}}}[5m])
                 / clamp_min(rate(node_disk_writes_completed_total{{job="node-exporter",{DISK}}}[5m]), 1e-9)
               ) {NODE}''', "{{nodename}} {{device}} write", "B"),
           ],
           description="Average service time. clamp_min avoids divide-by-zero when IOPS=0."),
        ts(44, "Disk busy % (iostat util)",
           f'100 * rate(node_disk_io_time_seconds_total{{job="node-exporter",{DISK}}}[5m]) {NODE}',
           12, 44, 12, 8, unit="percent", legend="{{nodename}} {{device}}",
           description="Fraction of time the device had I/O in flight. Can exceed 100% on some RAID."),

        row(50, "Filesystem / network", 52),
        ts(51, "Filesystem used %", FS_PCT, 0, 53, 12, 8, legend="{{nodename}} {{mountpoint}}",
           description="Excludes tmpfs, overlay, squashfs, nsfs, iso9660, autofs, devtmpfs, proc, sysfs."),
        ts(52, "Network RX / TX (physical + br-ex)", NET_RX_SUM, 12, 53, 12, 8, unit="bps",
           legend="{{nodename}} RX",
           extra_targets=[target(NET_TX_SUM, "{{nodename}} TX", "B")],
           description="Bits/s. veth/OVN internals excluded — see docs/promql.md."),

        row(60, "Node conditions", 61),
        table(61, "Node conditions (1 = true)",
              'kube_node_status_condition{status="true",node=~"$node"}',
              0, 62, 24, 8,
              description="Ready should be 1. MemoryPressure/DiskPressure/PIDPressure/NetworkUnavailable should be 0."),
    ]
    return dashboard(
        "ocp-infra-node",
        "NPD OCP Infra / Node Overview",
        ["npd", "openshift", "infra", "node"],
        vars_node(),
        panels,
        "Select a node to see CPU, memory, disk, network. "
        "Cluster variable is informational (Grafana already talks to this cluster's Thanos). "
        "Units: disk = MiB/s (IEC), network = bits/s (Mbps).",
    )


def disk_storage() -> dict:
    panels = [
        row(1, "Selected node + device", 0),
        stat(2, "Read throughput", DISK_READ, 0, 1, 4, 4, unit="binBps",
             legend="{{nodename}} {{device}}", description="MiB/s (IEC)."),
        stat(3, "Write throughput", DISK_WRITE, 4, 1, 4, 4, unit="binBps",
             legend="{{nodename}} {{device}}"),
        stat(4, "Read IOPS", READ_IOPS, 8, 1, 4, 4, unit="iops",
             legend="{{nodename}} {{device}}"),
        stat(5, "Write IOPS", WRITE_IOPS, 12, 1, 4, 4, unit="iops",
             legend="{{nodename}} {{device}}"),
        stat(6, "Read latency", READ_LAT, 16, 1, 4, 4, unit="s",
             legend="{{nodename}} {{device}}",
             steps=[{"color": "green", "value": None},
                    {"color": "yellow", "value": 0.02},
                    {"color": "red", "value": 0.05}]),
        stat(7, "Write latency", WRITE_LAT, 20, 1, 4, 4, unit="s",
             legend="{{nodename}} {{device}}",
             steps=[{"color": "green", "value": None},
                    {"color": "yellow", "value": 0.02},
                    {"color": "red", "value": 0.05}]),

        stat(8, "Disk busy %", DISK_BUSY, 0, 5, 6, 4, legend="{{nodename}} {{device}}",
             description="iostat %util. Not hardware queue depth.",
             steps=[{"color": "green", "value": None},
                    {"color": "yellow", "value": 60},
                    {"color": "red", "value": 80}]),
        stat(9, "Avg in-flight I/O (avgqu-sz)", DISK_AVGQU, 6, 5, 6, 4, unit="short",
             legend="{{nodename}} {{device}}",
             description="rate(weighted I/O time). Same idea as iostat avgqu-sz. "
                         "NOT SCSI/NVMe hardware queue depth — node-exporter cannot provide that."),
        stat(10, "Total IOPS", TOTAL_IOPS, 12, 5, 6, 4, unit="iops",
             legend="{{nodename}} {{device}}"),
        stat(11, "CPU I/O Wait % (node)", CPU_IOWAIT, 18, 5, 6, 4,
             description="Correlate with device latency/busy. Storage pain shows up here.",
             steps=warn_io()),

        row(20, "Throughput / IOPS / latency", 9),
        ts(21, "Disk read throughput", DISK_READ, 0, 10, 12, 8, unit="binBps",
           legend="{{nodename}} {{device}}", description="IEC MiB/s."),
        ts(22, "Disk write throughput", DISK_WRITE, 12, 10, 12, 8, unit="binBps",
           legend="{{nodename}} {{device}}"),
        ts(23, "Read IOPS", READ_IOPS, 0, 18, 8, 8, unit="iops", legend="{{nodename}} {{device}}"),
        ts(24, "Write IOPS", WRITE_IOPS, 8, 18, 8, 8, unit="iops", legend="{{nodename}} {{device}}"),
        ts(25, "Total IOPS", TOTAL_IOPS, 16, 18, 8, 8, unit="iops", legend="{{nodename}} {{device}}"),
        ts(26, "Read latency", READ_LAT, 0, 26, 12, 8, unit="s", legend="{{nodename}} {{device}}",
           description="read_time / reads_completed. Protected with clamp_min(..., 1e-9)."),
        ts(27, "Write latency", WRITE_LAT, 12, 26, 12, 8, unit="s", legend="{{nodename}} {{device}}"),

        row(30, "Saturation", 34),
        ts(31, "Disk busy %", DISK_BUSY, 0, 35, 12, 8, legend="{{nodename}} {{device}}"),
        ts(32, "Avg in-flight I/O (avgqu-sz analogue)", DISK_AVGQU, 12, 35, 12, 8, unit="short",
           legend="{{nodename}} {{device}}",
           description="Limitation: this is average queue length seen by the OS, not device QD."),

        row(40, "Filesystem + CPU I/O wait (same node)", 43),
        ts(41, "Filesystem used %", FS_PCT, 0, 44, 8, 8, legend="{{nodename}} {{mountpoint}}"),
        ts(42, "Inode used %", INODE_PCT, 8, 44, 8, 8, legend="{{nodename}} {{mountpoint}}"),
        ts(43, "CPU I/O Wait %", CPU_IOWAIT, 16, 44, 8, 8),
        ts(44, "Filesystem read-only?",
           f'node_filesystem_readonly{{job="node-exporter",{FS}}} {NODE}',
           0, 52, 24, 6, unit="short", legend="{{nodename}} {{mountpoint}}",
           description="1 = mounted read-only. Should stay 0."),
    ]
    return dashboard(
        "ocp-infra-disk",
        "NPD OCP Infra / Disk Storage",
        ["npd", "openshift", "infra", "disk", "storage"],
        vars_node(device=True),
        panels,
        "Troubleshoot storage bottlenecks. Select node + device (sda, sdb, vda, nvme0n1). "
        "Throughput unit: MiB/s (IEC). Latency unit: seconds (shown as ms). "
        "Queue-depth of the hardware is NOT available from node-exporter.",
    )


def network() -> dict:
    panels = [
        row(1, "Selected node + interface", 0),
        stat(2, "RX throughput", NET_RX, 0, 1, 6, 4, unit="bps", legend="{{nodename}} {{device}}",
             description="Bits/s (Mbps)."),
        stat(3, "TX throughput", NET_TX, 6, 1, 6, 4, unit="bps", legend="{{nodename}} {{device}}"),
        stat(4, "RX errors/s", NET_RX_ERR, 12, 1, 6, 4, unit="pps", legend="{{nodename}} {{device}}",
             steps=[{"color": "green", "value": None}, {"color": "red", "value": 0.01}]),
        stat(5, "TX errors/s", NET_TX_ERR, 18, 1, 6, 4, unit="pps", legend="{{nodename}} {{device}}",
             steps=[{"color": "green", "value": None}, {"color": "red", "value": 0.01}]),

        row(10, "Throughput / packets", 5),
        ts(11, "RX throughput", NET_RX, 0, 6, 12, 8, unit="bps", legend="{{nodename}} {{device}}"),
        ts(12, "TX throughput", NET_TX, 12, 6, 12, 8, unit="bps", legend="{{nodename}} {{device}}"),
        ts(13, "RX packet rate", NET_RX_PKT, 0, 14, 12, 8, unit="pps", legend="{{nodename}} {{device}}"),
        ts(14, "TX packet rate", NET_TX_PKT, 12, 14, 12, 8, unit="pps", legend="{{nodename}} {{device}}"),

        row(20, "Errors / drops", 22),
        ts(21, "RX errors", NET_RX_ERR, 0, 23, 12, 8, unit="pps", legend="{{nodename}} {{device}}"),
        ts(22, "TX errors", NET_TX_ERR, 12, 23, 12, 8, unit="pps", legend="{{nodename}} {{device}}"),
        ts(23, "RX drops", NET_RX_DROP, 0, 31, 12, 8, unit="pps", legend="{{nodename}} {{device}}",
           description="Kernel drop of incoming packets. Sustained > 0 is a problem."),
        ts(24, "TX drops", NET_TX_DROP, 12, 31, 12, 8, unit="pps", legend="{{nodename}} {{device}}"),

        row(30, "Filter note", 39),
        table(31, "Interfaces currently matching the filter",
              f'node_network_up{{job="node-exporter",{NET},device=~"$interface"}} {NODE}',
              0, 40, 24, 8,
              description="Excluded: lo, veth*, cali*, tunl*, cni*, flannel*, br-int, "
                          "genev*, ovn-k8s-mp0, ovn-k8s-gw0, kube-ipvs0. Kept: ens/eth/enp, br-ex."),
    ]
    return dashboard(
        "ocp-infra-net",
        "NPD OCP Infra / Network",
        ["npd", "openshift", "infra", "network"],
        vars_node(interface=True),
        panels,
        "Network deep dive. Throughput unit: bits/s (Mbps). "
        "OVN-Kubernetes internals are excluded; br-ex (node uplink) is kept.",
    )


def cluster_health() -> dict:
    cpu_all = '''100 * (1 - avg by (nodename) (
  rate(node_cpu_seconds_total{job="node-exporter",mode="idle"}[5m])
  * on(instance) group_left(nodename) node_uname_info{job="node-exporter"}
))'''
    mem_all = '''100 * (1 - (
  node_memory_MemAvailable_bytes{job="node-exporter"}
  / node_memory_MemTotal_bytes{job="node-exporter"}
)) * on(instance) group_left(nodename) node_uname_info{job="node-exporter"}'''

    panels = [
        row(1, "Node health", 0),
        stat(2, "Nodes Ready",
             'count(kube_node_status_condition{condition="Ready",status="true"} == 1)',
             0, 1, 4, 4, unit="short", legend="ready",
             steps=[{"color": "red", "value": None}, {"color": "green", "value": 1}]),
        stat(3, "Nodes NotReady",
             'count(kube_node_status_condition{condition="Ready",status="true"} == 0) or vector(0)',
             4, 1, 4, 4, unit="short", legend="notready",
             steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
        stat(4, "MemoryPressure",
             'count(kube_node_status_condition{condition="MemoryPressure",status="true"} == 1) or vector(0)',
             8, 1, 4, 4, unit="short",
             steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
        stat(5, "DiskPressure",
             'count(kube_node_status_condition{condition="DiskPressure",status="true"} == 1) or vector(0)',
             12, 1, 4, 4, unit="short",
             steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
        stat(6, "PIDPressure",
             'count(kube_node_status_condition{condition="PIDPressure",status="true"} == 1) or vector(0)',
             16, 1, 4, 4, unit="short",
             steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
        stat(7, "NetworkUnavailable",
             'count(kube_node_status_condition{condition="NetworkUnavailable",status="true"} == 1) or vector(0)',
             20, 1, 4, 4, unit="short",
             steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),

        row(10, "Pods", 5),
        stat(11, "Pods running",
             'sum(kube_pod_status_phase{phase="Running"})',
             0, 6, 6, 4, unit="short"),
        stat(12, "Pods pending",
             'sum(kube_pod_status_phase{phase="Pending"})',
             6, 6, 6, 4, unit="short",
             steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 1},
                    {"color": "red", "value": 5}]),
        stat(13, "Pods failed",
             'sum(kube_pod_status_phase{phase="Failed"})',
             12, 6, 6, 4, unit="short",
             steps=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
        stat(14, "Pods total",
             'sum(kube_pod_status_phase)',
             18, 6, 6, 4, unit="short"),
        ts(15, "Pod count by phase",
           'sum by (phase) (kube_pod_status_phase)',
           0, 10, 24, 8, unit="short", legend="{{phase}}"),

        row(20, "Capacity by node", 18),
        ts(21, "CPU utilization by node", cpu_all, 0, 19, 12, 8, legend="{{nodename}}"),
        ts(22, "Memory utilization by node", mem_all, 12, 19, 12, 8, legend="{{nodename}}"),

        row(30, "Unhealthy node conditions (table)", 27),
        table(31, "Conditions currently true (except Ready)",
              'kube_node_status_condition{status="true",condition!="Ready"} == 1',
              0, 28, 24, 8,
              description="Empty table = no pressure / network issues. Ready is shown in the stats row."),
        table(32, "Ready status per node",
              'kube_node_status_condition{condition="Ready",status="true"}',
              0, 36, 24, 8),
    ]
    return dashboard(
        "ocp-infra-cluster",
        "NPD OCP Infra / Cluster Health",
        ["npd", "openshift", "infra", "cluster"],
        [datasource_var(), custom_var("cluster", "ocp01", "Cluster")],
        panels,
        "Cluster-wide node conditions and pod phases. Unhealthy nodes must be obvious here.",
    )


def control_plane() -> dict:
    # Metric names verified against OpenShift 4 CMO / kube-prometheus (job labels).
    panels = [
        row(1, "API server", 0),
        stat(2, "API request rate",
             'sum(rate(apiserver_request_total{job=~"apiserver|kube-apiserver"}[5m]))',
             0, 1, 6, 4, unit="reqps"),
        stat(3, "API 5xx rate",
             'sum(rate(apiserver_request_total{job=~"apiserver|kube-apiserver",code=~"5.."}[5m]))',
             6, 1, 6, 4, unit="reqps",
             steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 0.1},
                    {"color": "red", "value": 1}]),
        stat(4, "API p99 latency",
             'histogram_quantile(0.99, sum by (le) (rate(apiserver_request_duration_seconds_bucket{job=~"apiserver|kube-apiserver",verb=~"GET|LIST|POST|PUT|PATCH|DELETE"}[5m])))',
             12, 1, 6, 4, unit="s",
             steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 1},
                    {"color": "red", "value": 3}]),
        stat(5, "API server up",
             'sum(up{job=~"apiserver|kube-apiserver"})',
             18, 1, 6, 4, unit="short",
             steps=[{"color": "red", "value": None}, {"color": "green", "value": 1}]),
        ts(6, "API request rate by code",
           'sum by (code) (rate(apiserver_request_total{job=~"apiserver|kube-apiserver"}[5m]))',
           0, 5, 12, 8, unit="reqps", legend="{{code}}"),
        ts(7, "API p50 / p99 latency",
           'histogram_quantile(0.50, sum by (le) (rate(apiserver_request_duration_seconds_bucket{job=~"apiserver|kube-apiserver",verb=~"GET|LIST|POST|PUT|PATCH|DELETE"}[5m])))',
           12, 5, 12, 8, unit="s", legend="p50",
           extra_targets=[
               target(
                   'histogram_quantile(0.99, sum by (le) (rate(apiserver_request_duration_seconds_bucket{job=~"apiserver|kube-apiserver",verb=~"GET|LIST|POST|PUT|PATCH|DELETE"}[5m])))',
                   "p99", "B"),
           ]),

        row(10, "etcd", 13),
        stat(11, "etcd has leader",
             'min(etcd_server_has_leader{job="etcd"})',
             0, 14, 6, 4, unit="short",
             description="1 = healthy quorum leader. 0 = no leader.",
             steps=[{"color": "red", "value": None}, {"color": "green", "value": 1}]),
        stat(12, "etcd up",
             'sum(up{job="etcd"})',
             6, 14, 6, 4, unit="short",
             steps=[{"color": "red", "value": None}, {"color": "green", "value": 3}]),
        stat(13, "Leader changes / 15m",
             'sum(increase(etcd_server_leader_changes_seen_total{job="etcd"}[15m]))',
             12, 14, 6, 4, unit="short",
             steps=[{"color": "green", "value": None}, {"color": "yellow", "value": 1},
                    {"color": "red", "value": 3}]),
        stat(14, "etcd DB size",
             'max(etcd_mvcc_db_total_size_in_bytes{job="etcd"} or etcd_debugging_mvcc_db_total_size_in_bytes{job="etcd"})',
             18, 14, 6, 4, unit="bytes"),
        ts(15, "etcd request / WAL fsync p99",
           'histogram_quantile(0.99, sum by (le) (rate(etcd_disk_wal_fsync_duration_seconds_bucket{job="etcd"}[5m])))',
           0, 18, 12, 8, unit="s", legend="WAL fsync p99",
           extra_targets=[
               target(
                   'histogram_quantile(0.99, sum by (le) (rate(etcd_disk_backend_commit_duration_seconds_bucket{job="etcd"}[5m])))',
                   "backend commit p99", "B"),
           ],
           description="WAL fsync p99 should stay well under 10ms on healthy disks. "
                       "etcd_request_duration_seconds is used when present (see second panel)."),
        ts(16, "etcd DB size",
           'etcd_mvcc_db_total_size_in_bytes{job="etcd"} or etcd_debugging_mvcc_db_total_size_in_bytes{job="etcd"}',
           12, 18, 12, 8, unit="bytes", legend="{{instance}}"),
        ts(17, "etcd leader changes",
           'increase(etcd_server_leader_changes_seen_total{job="etcd"}[15m])',
           0, 26, 12, 8, unit="short", legend="{{instance}}"),
        ts(18, "etcd has leader",
           'etcd_server_has_leader{job="etcd"}',
           12, 26, 12, 8, unit="short", legend="{{instance}}"),

        row(20, "Scheduler / controller-manager", 34),
        stat(21, "Scheduler up",
             'sum(up{job=~"scheduler|kube-scheduler"})',
             0, 35, 6, 4, unit="short",
             steps=[{"color": "red", "value": None}, {"color": "green", "value": 1}]),
        stat(22, "Controller manager up",
             'sum(up{job=~"kube-controller-manager|controller-manager"})',
             6, 35, 6, 4, unit="short",
             steps=[{"color": "red", "value": None}, {"color": "green", "value": 1}]),
        ts(23, "Scheduler scheduling attempts",
           'sum by (result) (rate(scheduler_schedule_attempts_total{job=~"scheduler|kube-scheduler"}[5m]))',
           0, 39, 12, 8, unit="ops", legend="{{result}}",
           description="result=error/unschedulable is the health signal."),
        ts(24, "Controller workqueue depth",
           'sum by (name) (workqueue_depth{job=~"kube-controller-manager|controller-manager"})',
           12, 39, 12, 8, unit="short", legend="{{name}}"),

        row(30, "Kubelet (selected via instance; cluster-wide here)", 47),
        ts(31, "Kubelet running pods",
           'sum by (node, instance) (kubelet_running_pods{job="kubelet"})',
           0, 48, 12, 8, unit="short", legend="{{node}}"),
        ts(32, "Kubelet runtime operations",
           'sum by (operation_type, instance) (rate(kubelet_runtime_operations_total{job="kubelet"}[5m]))',
           12, 48, 12, 8, unit="ops", legend="{{instance}} {{operation_type}}"),
        ts(33, "Kubelet runtime operation errors",
           'sum by (operation_type, instance) (rate(kubelet_runtime_operations_errors_total{job="kubelet"}[5m]))',
           0, 56, 12, 8, unit="ops", legend="{{instance}} {{operation_type}}"),
        ts(34, "Kubelet PLEG relist p99",
           'histogram_quantile(0.99, sum by (instance, le) (rate(kubelet_pleg_relist_duration_seconds_bucket{job="kubelet"}[5m])))',
           12, 56, 12, 8, unit="s", legend="{{instance}}"),
        ts(35, "Kubelet REST client requests",
           'sum by (code, instance) (rate(rest_client_requests_total{job="kubelet"}[5m]))',
           0, 64, 12, 8, unit="reqps", legend="{{instance}} {{code}}"),
        ts(36, "Volume / storage operations",
           'sum by (operation_name, instance) (rate(storage_operation_duration_seconds_count{job="kubelet"}[5m]))',
           12, 64, 12, 8, unit="ops", legend="{{instance}} {{operation_name}}",
           description="Only plotted if kubelet exposes storage_operation_duration_seconds_count."),
    ]
    return dashboard(
        "ocp-infra-cp",
        "NPD OCP Infra / Control Plane etcd",
        ["npd", "openshift", "infra", "etcd", "control-plane"],
        [datasource_var(), custom_var("cluster", "ocp01", "Cluster")],
        panels,
        "API server, etcd, scheduler, controller-manager, kubelet. "
        "Job matchers accept OpenShift CMO names (apiserver, etcd, scheduler, kube-controller-manager, kubelet).",
    )


def main() -> None:
    out = (
        find_workspace()
        / "Open-Source-AIOps-Platform"
        / "charts"
        / "grafana"
        / "dashboards"
    )
    out.mkdir(parents=True, exist_ok=True)
    mapping = {
        "npd-ocp-infra-node-infrastructure.json": node_infrastructure(),
        "npd-ocp-infra-disk-storage.json": disk_storage(),
        "npd-ocp-infra-network.json": network(),
        "npd-ocp-infra-openshift-cluster.json": cluster_health(),
        "npd-ocp-infra-control-plane-etcd.json": control_plane(),
    }
    for name, data in mapping.items():
        path = out / name
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path} ({path.stat().st_size} bytes, {len(data['panels'])} panels)")


if __name__ == "__main__":
    main()
