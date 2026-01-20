"""Scenario schema for Patch2 sweeps.

This module defines:
  - scenario dictionaries (knob sets)
  - stable scenario_key and scenario_id generation
  - canonical metric ordering

It is intentionally dependency-light so it can be used from multiprocessing workers.
"""

from __future__ import annotations

from hashlib import sha1
from typing import Any, Dict, List, Tuple


# Canonical scenario fields (seed is NOT part of scenario_id; seed is the z-axis).
SCENARIO_FIELDS: List[str] = [
    "mac_mode",
    "traffic_pattern",
    "traffic_rate",
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
    """Build a stable scenario_key string from the canonical field list."""
    parts = []
    for k in SCENARIO_FIELDS:
        v = d.get(k, None)
        parts.append(f"{k}={v}")
    return "|".join(parts)


def scenario_id_from_key(key: str) -> str:
    """Stable short id for filenames / joins."""
    return sha1(key.encode("utf-8")).hexdigest()[:12]


def make_base_scenarios(
    *,
    avg_payload_bytes: int,
    payload_mode: str = "fixed",
    payload_var_bytes: int = 0,
    enable_dynamic_mobility: bool = True,
    enable_obstacle_avoidance: bool = True,
    uniform_iat_us: Tuple[int, int] = (500000, 505000),
) -> List[Dict[str, Any]]:
    """Base scenarios: 2 MAC modes x traffic_rate 1..20 (Poisson).

    These are the 40 combinations requested.
    """
    scenarios: List[Dict[str, Any]] = []
    for mac in ["TDMA", "CSMA"]:
        for r in range(1, 21):
            s: Dict[str, Any] = {
                "mac_mode": mac,
                "traffic_pattern": "Poisson",
                "traffic_rate": int(r),
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
