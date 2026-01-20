"""Scenario schema for Patch3 sweeps (equal total offered load).

Patch3 compares TDMA vs CSMA under *equal total network offered load*.

We sweep TOTAL_TRAFFIC_RATE in [1..20] where TOTAL_TRAFFIC_RATE is the
aggregate packet generation rate (packets/sec) across all drones.

Per-drone Poisson rate is derived at runtime as:
    per_node_rate = total_traffic_rate / n_drones

The scenario_id is stable and does NOT include the replicate seed.
"""

from __future__ import annotations

from hashlib import sha1
from typing import Any, Dict, List, Tuple


SCENARIO_FIELDS: List[str] = [
    "mac_mode",
    "traffic_pattern",
    "total_traffic_rate",
    "uniform_iat_us",
    "payload_mode",
    "avg_payload_bytes",
    "payload_var_bytes",
    "enable_dynamic_mobility",
    "enable_obstacle_avoidance",
]


# Canonical metric ordering for tensor axis y.
METRICS: List[str] = [
    "pdr_percent",
    "e2e_delay_ms",
    "routing_load",
    "throughput_kbps",
    "hop_count",
    "collisions",
    "mac_delay_ms",
]


def scenario_key(d: Dict[str, Any]) -> str:
    parts = []
    for k in SCENARIO_FIELDS:
        v = d.get(k, None)
        parts.append(f"{k}={v}")
    return "|".join(parts)


def scenario_id_from_key(key: str) -> str:
    return sha1(key.encode("utf-8")).hexdigest()[:12]


def make_equal_total_load_scenarios(
    *,
    avg_payload_bytes: int,
    payload_mode: str = "fixed",
    payload_var_bytes: int = 0,
    enable_dynamic_mobility: bool = True,
    enable_obstacle_avoidance: bool = True,
    uniform_iat_us: Tuple[int, int] = (500000, 505000),
    total_rate_range: Tuple[int, int] = (1, 20),
) -> List[Dict[str, Any]]:
    """2 MAC modes x TOTAL_TRAFFIC_RATE range (Poisson), keeping total load equal."""
    lo, hi = total_rate_range
    scenarios: List[Dict[str, Any]] = []
    for mac in ["TDMA", "CSMA"]:
        for total_r in range(int(lo), int(hi) + 1):
            s: Dict[str, Any] = {
                "mac_mode": mac,
                "traffic_pattern": "Poisson",
                "total_traffic_rate": int(total_r),
                "uniform_iat_us": tuple(map(int, uniform_iat_us)),
                "payload_mode": payload_mode,
                "avg_payload_bytes": int(avg_payload_bytes),
                "payload_var_bytes": int(payload_var_bytes),
                "enable_dynamic_mobility": bool(enable_dynamic_mobility),
                "enable_obstacle_avoidance": bool(enable_obstacle_avoidance),
            }
            key = scenario_key(s)
            s["scenario_key"] = key
            s["scenario_id"] = scenario_id_from_key(key)
            scenarios.append(s)
    return scenarios
