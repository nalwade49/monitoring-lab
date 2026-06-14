# Monitoring Lab

A self-driven observability stack built post-CDAC (June 2026), running entirely on Docker + WSL2. Covers both the **DevOps story** (infrastructure metrics) and the **SOC/Security story** (log aggregation and alerting) using a single `docker-compose.yml`.

---

## What This Lab Covers

| Layer | Tool | Purpose |
|---|---|---|
| **Metrics collection** | Node Exporter | Exposes host CPU, RAM, disk, network metrics |
| **Metrics storage** | Prometheus | Scrapes and stores time-series metrics |
| **Log shipping** | Promtail | Tails host log files, ships to Loki |
| **Log storage** | Loki | Lightweight log aggregation backend |
| **Visualization + Alerting** | Grafana | Single UI for metrics, logs, and alert rules |

---

## Architecture

```
WSL2 Host (Ubuntu)
        │
        ├── /proc, /sys ──────────► Node Exporter :9100 ──► Prometheus :9090 ──┐
        │                                                                        │
        └── /var/log/auth.log ───► Promtail :9080 ────────► Loki :3100 ────────┤
            /var/log/syslog                                                      │
                                                                                 ▼
                                                                        Grafana :3000
                                                                     (Dashboards + Alerts)
                                                                                 │
                                                                        Browser: localhost:3000
```

**Data flow:**
- Node Exporter reads kernel metrics from `/proc` and `/sys` on the WSL2 host
- Prometheus scrapes Node Exporter every 15 seconds and stores metrics as time-series data
- Promtail tails `/var/log/auth.log` and `/var/log/syslog` continuously
- Promtail pushes log streams to Loki with labels (`job="auth"`, `job="varlogs"`)
- Grafana queries both Prometheus (PromQL) and Loki (LogQL) and serves a single UI

---

## Why Loki Over ELK

Elasticsearch requires 1-2GB heap minimum. Loki indexes only metadata labels, not full log content — making it significantly lighter (~200MB) while still enabling powerful log queries in the same Grafana interface used for metrics. For a local lab on constrained hardware this is the practical choice, and Loki is production-used at scale (Grafana Cloud runs it).

---

## DevOps Story — Infrastructure Metrics

Imported the community **Node Exporter Full** dashboard (Grafana ID: 1860) which provides:

- Live CPU usage per core
- Memory used/free/cached
- Disk I/O read/write rates
- Network bytes in/out
- System uptime
- Filesystem usage

Dashboard auto-refreshes every 1 minute and retains 7 days of metric history.

---

## SOC/Security Story — Log Aggregation

Promtail tails auth logs from the host and ships them to Loki. In Grafana Explore, security-relevant events can be queried using LogQL:

```
# All auth events
{job="auth"}

# Sudo privilege escalation events
{job="auth"} |= "sudo"

# Specific user activity (uid=1000 = human operator)
{job="auth"} |= "uid=1000"

# Failed authentication attempts
{job="auth"} |= "Failed"

# Session opened events
{job="auth"} |= "session opened"
```

These queries surface:
- Privilege escalation (sudo usage)
- Human vs automated activity (uid=1000 vs cron)
- Authentication failures (brute force detection)
- Session lifecycle tracking

---

## Alerting

Configured a Grafana alert rule on CPU usage:

**Rule:** `High CPU Usage`
**Query:**
```promql
100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```
**Condition:** Fires when CPU > 80% sustained for 5 minutes

**Evaluation:** Every 1 minute, 5 minute pending period (prevents false positives from short spikes)

This demonstrates the full alerting pipeline — metric collection → threshold evaluation → alert state → notification routing.

---

## Project Structure

```
monitoring-lab/
├── docker-compose.yml
├── prometheus/
│   └── prometheus.yml          # Scrape config — targets and intervals
├── loki/
│   └── loki-config.yml         # Storage, schema, ingester, compactor config
├── promtail/
│   └── promtail-config.yml     # Log targets, labels, Loki push endpoint
└── grafana/
    └── provisioning/
        └── datasources/
            └── datasources.yml # Auto-provisions Prometheus + Loki on startup
```

---

## How to Run

**Prerequisites:** Docker, Docker Compose, WSL2 (Ubuntu)

```bash
# Clone the repo
git clone git@github.com:nalwade49/monitoring-lab.git
cd monitoring-lab

# Start the stack
docker compose up -d

# Verify all containers are running
docker compose ps
```

Access Grafana at `http://localhost:3000`
- Username: `admin`
- Password: `admin123`

Both datasources (Prometheus and Loki) are auto-provisioned on first startup — no manual configuration needed.

---

## Verify the Stack

```bash
# Check all 5 containers are up
docker compose ps

# Check Prometheus is scraping Node Exporter
curl http://localhost:9090/api/v1/targets

# Check Loki is receiving logs
curl http://localhost:3100/ready

# Check Node Exporter metrics endpoint
curl http://localhost:9100/metrics | grep node_cpu
```

---

## Key LogQL Queries for SOC Use

| Query | What it detects |
|---|---|
| `{job="auth"} \|= "Failed password"` | SSH brute force attempts |
| `{job="auth"} \|= "sudo"` | Privilege escalation |
| `{job="auth"} \|= "session opened"` | New session tracking |
| `{job="auth"} \|= "invalid user"` | Unknown user login attempts |
| `{job="varlogs"} \|= "error"` | System errors |

---

## Key PromQL Queries for DevOps Use

| Query | What it measures |
|---|---|
| `100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)` | CPU usage % |
| `node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100` | Available memory % |
| `rate(node_network_receive_bytes_total[5m])` | Network receive rate |
| `node_filesystem_avail_bytes / node_filesystem_size_bytes * 100` | Disk free % |

---

## Environment

- **OS:** Windows 11 + WSL2 (Ubuntu)
- **Hardware:** Intel i3-1215U, 8GB RAM (WSL2 limited to 5GB)
- **Docker:** v29.5.2
- **Docker Compose:** v5.1.3
- **Grafana:** latest
- **Prometheus:** latest
- **Loki:** 2.9.0
- **Promtail:** 2.9.0

---

## Status

Active — alert notification channels and additional SOC detection rules in progres
