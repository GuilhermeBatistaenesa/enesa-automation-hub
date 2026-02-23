from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

runs_total = Counter("enesa_runs_total", "Total number of run completions")
runs_failed_total = Counter("enesa_runs_failed_total", "Total number of failed runs")
run_duration_seconds = Histogram(
    "enesa_run_duration_seconds",
    "Duration of run execution in seconds",
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1200),
)
queue_depth = Gauge("enesa_queue_depth", "Current queue depth in Redis")
worker_heartbeat = Gauge("enesa_worker_heartbeat_unix", "Worker heartbeat unix timestamp", ["worker"])


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST

