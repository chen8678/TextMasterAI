"""轻量运行时监控聚合（进程内，P3-T30）。"""
from __future__ import annotations

from collections import deque
from threading import Lock
from time import time
from typing import Deque, Dict, Tuple


_WINDOW_SECONDS = 15 * 60
_MAX_EVENTS = 12000
_lock = Lock()
_events: Deque[Tuple[float, int, float]] = deque(maxlen=_MAX_EVENTS)


def _prune(now_ts: float) -> None:
    cutoff = now_ts - _WINDOW_SECONDS
    while _events and _events[0][0] < cutoff:
        _events.popleft()


def record_request(status_code: int, duration_seconds: float) -> None:
    now_ts = time()
    with _lock:
        _events.append((now_ts, int(status_code or 0), float(duration_seconds or 0.0)))
        _prune(now_ts)


def snapshot() -> Dict[str, float]:
    now_ts = time()
    with _lock:
        _prune(now_ts)
        rows = list(_events)

    total = len(rows)
    if total == 0:
        return {
            "window_seconds": _WINDOW_SECONDS,
            "total_calls": 0,
            "error_calls": 0,
            "error_rate": 0.0,
            "avg_ms": 0.0,
            "p95_ms": 0.0,
        }

    errors = sum(1 for _, code, _ in rows if code >= 400)
    durations_ms = sorted(d * 1000.0 for _, _, d in rows)
    idx95 = min(len(durations_ms) - 1, max(0, int(len(durations_ms) * 0.95) - 1))
    return {
        "window_seconds": _WINDOW_SECONDS,
        "total_calls": total,
        "error_calls": errors,
        "error_rate": round(errors / total * 100.0, 2),
        "avg_ms": round(sum(durations_ms) / total, 2),
        "p95_ms": round(durations_ms[idx95], 2),
    }
