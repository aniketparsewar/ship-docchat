"""Observability: log every request, aggregate /metrics.

Each request appends one JSON line to logs/requests.jsonl AND updates
in-memory aggregates. The JSONL file is the durable record (survives
restarts); the in-memory aggregates are what /metrics reads (fast).

Privacy note: we log the full question text. Fine for a personal demo;
PII-scrub (or hash) questions before any multi-user use.
"""
import json
import os
import statistics
import threading
import time
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "requests.jsonl"
MAX_KEPT_LATENCIES = 10_000

_lock = threading.Lock()
_events: list[dict] = []          # in-memory copy of the JSONL log
_latencies: dict[str, list[float]] = {}   # endpoint -> [latency_ms]


def log_event(event: dict) -> None:
    event = {"ts": time.time(), **event}
    LOG_DIR.mkdir(exist_ok=True)
    with _lock:
        _events.append(event)
        _latencies.setdefault(event["endpoint"], []).append(
            event["latency_ms"])
        # Bound memory: drop oldest latencies, keep the log file as truth.
        lat = _latencies[event["endpoint"]]
        if len(lat) > MAX_KEPT_LATENCIES:
            del lat[: len(lat) - MAX_KEPT_LATENCIES]
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = min(len(ordered) - 1, int(p / 100 * len(ordered)))
    return ordered[k]

def replay() -> None:
    if not LOG_FILE.exists():
        return
    with _lock:
        for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            _events.append(event)
            _latencies.setdefault(event["endpoint"], []).append(
                event["latency_ms"])



def get_metrics() -> dict:
    with _lock:
        events = list(_events)
        lat = {k: list(v) for k, v in _latencies.items()}
    by_endpoint: dict[str, int] = {}
    refused = 0
    tokens_in = 0
    tokens_out = 0
    cost = 0.0
    for e in events:
        by_endpoint[e["endpoint"]] = by_endpoint.get(e["endpoint"], 0) + 1
        refused += 1 if e.get("refused") else 0
        tokens_in += e.get("input_tokens", 0)
        tokens_out += e.get("output_tokens", 0)
        cost += e.get("cost_usd", 0.0)
    ask_lat = lat.get("ask", [])
    return {
        "requests_total": len(events),
        "requests_by_endpoint": by_endpoint,
        "ask_latency_ms": {
            "count": len(ask_lat),
            "avg": round(statistics.fmean(ask_lat), 1) if ask_lat else 0.0,
            "p50": round(_pct(ask_lat, 50), 1),
            "p95": round(_pct(ask_lat, 95), 1),
        },
        "tokens": {"input": tokens_in, "output": tokens_out},
        "cost_usd_total": round(cost, 6),
        "refusals": refused,
        "refusal_rate": round(refused / len(events), 3) if events else 0.0,
    }
