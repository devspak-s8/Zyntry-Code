"""In-memory metrics registry.

Simple counters/histograms used for observability (routing decisions,
escalations, provider errors, execution timings) and exposed via ``/metrics``.
On Workers these are per-isolate — for cross-isolate aggregation, push these to
Cloudflare Analytics/Logpush; this registry keeps the wiring in one place.
"""

import time
from collections import defaultdict
from typing import Any


class Metrics:
    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._started_at = time.monotonic()

    def incr(self, name: str, n: int = 1) -> None:
        self._counters[name] += n

    def observe(self, name: str, value: float) -> None:
        self._histograms[name].append(value)

    def snapshot(self) -> dict[str, Any]:
        hist = {}
        for name, values in self._histograms.items():
            hist[name] = {
                "count": len(values),
                "sum": round(sum(values), 3),
                "avg": round(sum(values) / len(values), 3) if values else 0,
            }
        return {
            "uptime_seconds": round(time.monotonic() - self._started_at, 3),
            "counters": dict(self._counters),
            "histograms": hist,
        }


metrics = Metrics()