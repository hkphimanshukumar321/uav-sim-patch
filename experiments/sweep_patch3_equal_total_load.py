"""Patch3 sweep runner (equal total offered load; multiprocessing mandatory).

Patch3 redesigns the experiment so that TDMA and CSMA are compared under
*equal total network offered load*.

We sweep TOTAL_TRAFFIC_RATE in [1..20] where TOTAL_TRAFFIC_RATE is the
aggregate packet generation rate (packets/sec) across all drones. Each drone's
Poisson rate is derived as:
    per_node_rate = total_traffic_rate / NUMBER_OF_DRONES

Runs:
  - MAC_MODE in {TDMA, CSMA}
  - TOTAL_TRAFFIC_RATE in [1..20]

Outputs:
  - results/sweep_patch3_runs.csv  (long-form, one row per run)
  - results/T_patch3.npz           (tensor T[x,y,z] + metadata)

This runner intentionally does NOT depend on pandas to avoid binary/ABI issues
in GPU/RAPIDS environments. Analysis can be done later using pandas on a clean
machine, or by reading the CSV.
"""

from __future__ import annotations

import csv
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure project root is on sys.path when running as a module or script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import multiprocessing as mp
import numpy as np
import simpy

from utils import config
from simulator.simulator import Simulator
from experiments.scenario_schema_patch3 import METRICS, make_equal_total_load_scenarios


def _apply_scenario_to_config(s: Dict[str, Any], *, n_drones: int) -> float:
    """Apply Patch3 scenario to global config and return per-node traffic rate."""
    # Traffic
    config.TRAFFIC_PATTERN = s["traffic_pattern"]
    config.LOAD_MODE = "TOTAL_NETWORK"
    config.TOTAL_TRAFFIC_RATE = float(s.get("total_traffic_rate", 0))
    per_node_rate = float(config.TOTAL_TRAFFIC_RATE) / float(max(1, n_drones))
    config.TRAFFIC_RATE = per_node_rate
    config.UNIFORM_IAT_US = tuple(s.get("uniform_iat_us", config.UNIFORM_IAT_US))

    # MAC
    config.MAC_MODE = s["mac_mode"]

    # Payload
    if s.get("payload_mode", "fixed") == "variable":
        config.VARIABLE_PAYLOAD_LENGTH = 1
        config.MAXIMUM_PAYLOAD_VARIATION = int(s.get("payload_var_bytes", 0)) * 8
    else:
        config.VARIABLE_PAYLOAD_LENGTH = 0
        config.MAXIMUM_PAYLOAD_VARIATION = int(s.get("payload_var_bytes", 0)) * 8
    config.AVERAGE_PAYLOAD_LENGTH = int(s.get("avg_payload_bytes", 1024)) * 8

    # Dynamic behaviors
    config.ENABLE_DYNAMIC_MOBILITY = bool(s.get("enable_dynamic_mobility", True))
    config.ENABLE_OBSTACLE_AVOIDANCE = bool(s.get("enable_obstacle_avoidance", True))

    # Batch settings
    config.ENABLE_PLOTS = False
    config.ENABLE_TIME_PRINTS = False

    # Optional SIM_TIME override
    sim_time_env = os.environ.get("PATCH3_SIM_TIME_US", "").strip()
    if sim_time_env:
        try:
            config.SIM_TIME = float(sim_time_env)
        except Exception:
            pass

    return per_node_rate


def _profile_snapshot() -> Dict[str, float]:
    out: Dict[str, float] = {}
    try:
        import resource

        ru = resource.getrusage(resource.RUSAGE_SELF)
        out["cpu_user_s"] = float(ru.ru_utime)
        out["cpu_sys_s"] = float(ru.ru_stime)
        out["max_rss_mb"] = float(ru.ru_maxrss) / 1024.0
    except Exception:
        out["cpu_user_s"] = float("nan")
        out["cpu_sys_s"] = float("nan")
        out["max_rss_mb"] = float("nan")
    return out


def _run_one(job: Tuple[Dict[str, Any], int, int]) -> Dict[str, Any]:
    scenario, seed, n_drones = job

    per_node_rate = _apply_scenario_to_config(scenario, n_drones=n_drones)

    t0 = time.perf_counter()
    status = "ok"
    error_msg = ""

    try:
        env = simpy.Environment()
        channel_states = {i: simpy.Resource(env, capacity=1) for i in range(config.NUMBER_OF_DRONES)}

        # Silence verbose worker prints
        import contextlib

        devnull = open(os.devnull, "w")
        with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            sim = Simulator(seed=int(seed), env=env, channel_states=channel_states, n_drones=n_drones)
            env.run(until=config.SIM_TIME)
            m = sim.metrics.to_dict()
        devnull.close()
    except Exception as e:
        status = "error"
        error_msg = repr(e)
        m = {
            "sent": 0,
            "arrived": 0,
            "pdr_percent": float("nan"),
            "e2e_delay_ms": float("nan"),
            "routing_load": float("nan"),
            "throughput_kbps": float("nan"),
            "hop_count": float("nan"),
            "collisions": int(0),
            "mac_delay_ms": float("nan"),
        }

    t1 = time.perf_counter()
    prof = _profile_snapshot()

    row: Dict[str, Any] = {
        "scenario_id": scenario["scenario_id"],
        "scenario_key": scenario["scenario_key"],
        "mac_mode": scenario["mac_mode"],
        "traffic_pattern": scenario["traffic_pattern"],
        "total_traffic_rate": int(scenario.get("total_traffic_rate", -1)),
        "per_node_rate": float(per_node_rate),
        "n_drones": int(n_drones),
        "uniform_iat_us": str(scenario.get("uniform_iat_us", "")),
        "payload_mode": scenario.get("payload_mode", "fixed"),
        "avg_payload_bytes": int(scenario.get("avg_payload_bytes", -1)),
        "payload_var_bytes": int(scenario.get("payload_var_bytes", 0)),
        "enable_dynamic_mobility": bool(scenario.get("enable_dynamic_mobility", True)),
        "enable_obstacle_avoidance": bool(scenario.get("enable_obstacle_avoidance", True)),
        "seed": int(seed),
        "status": status,
        "error_msg": error_msg,
        "wall_s": float(t1 - t0),
        "cpu_user_s": float(prof.get("cpu_user_s", float("nan"))),
        "cpu_sys_s": float(prof.get("cpu_sys_s", float("nan"))),
        "max_rss_mb": float(prof.get("max_rss_mb", float("nan"))),
    }
    row.update(m)
    return row


def _build_tensor_from_rows(rows: List[Dict[str, Any]], seeds: List[int]) -> Tuple[np.ndarray, Dict[str, Any]]:
    # Deterministic ordering by scenario_key
    uniq = {}
    for r in rows:
        sid = r["scenario_id"]
        if sid not in uniq:
            uniq[sid] = r["scenario_key"]
    scenario_items = sorted(uniq.items(), key=lambda kv: kv[1])  # (sid, key)
    scenario_ids = [sid for sid, _ in scenario_items]
    scenario_keys = [key for _, key in scenario_items]
    sid_to_x = {sid: i for i, sid in enumerate(scenario_ids)}
    seed_to_z = {s: i for i, s in enumerate(seeds)}

    Nx, Ny, Nz = len(scenario_ids), len(METRICS), len(seeds)
    T = np.full((Nx, Ny, Nz), np.nan, dtype=np.float64)

    for r in rows:
        if r.get("status") != "ok":
            continue
        sid = r["scenario_id"]
        s = int(r["seed"])
        if sid not in sid_to_x or s not in seed_to_z:
            continue
        x = sid_to_x[sid]
        z = seed_to_z[s]
        for y, m in enumerate(METRICS):
            try:
                T[x, y, z] = float(r.get(m, np.nan))
            except Exception:
                T[x, y, z] = np.nan

    meta = {
        "scenario_ids": np.array(scenario_ids, dtype=object),
        "scenario_keys": np.array(scenario_keys, dtype=object),
        "metrics": np.array(METRICS, dtype=object),
        "seeds": np.array(seeds, dtype=int),
    }
    return T, meta


def _mean_by_group(rows: List[Dict[str, Any]], group_keys: Tuple[str, ...], metric_keys: List[str]) -> List[Dict[str, Any]]:
    """Compute mean of metrics over rows grouped by group_keys."""
    agg: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for r in rows:
        if r.get("status") != "ok":
            continue
        g = tuple(r.get(k) for k in group_keys)
        if g not in agg:
            agg[g] = {k: r.get(k) for k in group_keys}
            agg[g]["_n"] = 0
            for mk in metric_keys:
                agg[g][mk] = 0.0
        agg[g]["_n"] += 1
        for mk in metric_keys:
            try:
                agg[g][mk] += float(r.get(mk, 0.0))
            except Exception:
                agg[g][mk] += 0.0
    out: List[Dict[str, Any]] = []
    for g, a in agg.items():
        n = max(1, int(a.pop("_n")))
        for mk in metric_keys:
            a[mk] = float(a[mk]) / float(n)
        out.append(a)
    # Sort by group keys for pretty printing
    out.sort(key=lambda d: tuple(d.get(k) for k in group_keys))
    return out


def main() -> int:
    seeds_env = os.environ.get("PATCH3_SEEDS", "2025").strip()
    seeds = [int(s) for s in seeds_env.split(",") if s.strip()]

    n_drones = int(getattr(config, "NUMBER_OF_DRONES", 10))
    avg_payload_bytes = int(getattr(config, "AVERAGE_PAYLOAD_LENGTH", 1024 * 8) / 8)

    scenarios = make_equal_total_load_scenarios(
        avg_payload_bytes=avg_payload_bytes,
        payload_mode="fixed",
        payload_var_bytes=0,
        enable_dynamic_mobility=bool(getattr(config, "ENABLE_DYNAMIC_MOBILITY", True)),
        enable_obstacle_avoidance=bool(getattr(config, "ENABLE_OBSTACLE_AVOIDANCE", True)),
        uniform_iat_us=tuple(getattr(config, "UNIFORM_IAT_US", (500000, 505000))),
        total_rate_range=(1, 20),
    )

    # Optional: limit scenarios for quick smoke tests
    lim_env = os.environ.get("PATCH3_LIMIT_SCENARIOS", "").strip()
    if lim_env:
        try:
            lim = max(1, int(lim_env))
            scenarios = scenarios[:lim]
        except Exception:
            pass

    jobs: List[Tuple[Dict[str, Any], int, int]] = []
    for s in scenarios:
        for seed in seeds:
            jobs.append((s, int(seed), n_drones))

    total_runs = len(jobs)
    workers_env = os.environ.get("PATCH3_WORKERS", "").strip()
    if workers_env:
        try:
            workers = max(1, int(workers_env))
        except Exception:
            workers = max(1, min(16, (os.cpu_count() or 4)))
    else:
        workers = max(1, min(16, (os.cpu_count() or 4)))

    print(f"Patch3 sweep: {len(scenarios)} scenarios x {len(seeds)} seeds = {total_runs} runs")
    print(f"Using {workers} worker processes (spawn)\n")

    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        rows = list(pool.imap_unordered(_run_one, jobs, chunksize=1))

    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    csv_path = results_dir / "sweep_patch3_runs.csv"

    # Stable header ordering
    fieldnames = sorted({k for r in rows for k in r.keys()})
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Saved: {csv_path}")

    T, meta = _build_tensor_from_rows(rows, seeds)
    npz_path = results_dir / "T_patch3.npz"
    np.savez_compressed(npz_path, T=T, **meta)
    print(f"Saved: {npz_path}\n")

    # Print mean metrics by group (mac_mode, total_traffic_rate)
    mean_rows = _mean_by_group(rows, ("mac_mode", "total_traffic_rate"), METRICS + ["wall_s"])
    print("Mean metrics by (mac_mode, total_traffic_rate):")

    # Pretty print fixed columns
    cols = ["mac_mode", "total_traffic_rate"] + METRICS + ["wall_s"]
    header = " ".join([f"{c:>16}" for c in cols])
    print(header)
    for r in mean_rows:
        line_parts = []
        for c in cols:
            v = r.get(c)
            if isinstance(v, float):
                line_parts.append(f"{v:16.6f}")
            else:
                line_parts.append(f"{str(v):>16}")
        print(" ".join(line_parts))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
