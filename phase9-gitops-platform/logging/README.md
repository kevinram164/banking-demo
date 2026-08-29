# Logging (OpenSearch)

Pod stdout → Fluent Bit → **logs-bank-***, **logs-shop-***, **logs-movie-***, **logs-infra-***.

| Doc | Nội dung |
|-----|----------|
| [`DEPLOY.md`](DEPLOY.md) | Cài stack, index pattern, ISM 7 ngày |
| [`dashboards/DASHBOARDS.md`](dashboards/DASHBOARDS.md) | Dashboard giao dịch / đơn hàng / thanh toán |

Index tách 4 nhóm: **bank / shop / movie / infra** — retention **7 ngày** (ISM).

→ [DEPLOY.md](DEPLOY.md)

| Pattern | Ns |
|---------|-----|
| `logs-bank-*` | npd-banking |
| `logs-shop-*` | npd-shop |
| `logs-movie-*` | npd-movie |
| `logs-infra-*` | kafka, platform, observability, … |

UI: https://logs-platform.apps.ocp01.npd.co
