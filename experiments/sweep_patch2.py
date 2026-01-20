"""Patch2 sweep runner (multiprocessing mandatory).

Runs 40 combinations:
  - MAC_MODE in {TDMA, CSMA}
  - TRAFFIC_RATE in [1..20]
using Poisson traffic.

Outputs:
  - results/sweep_patch2_runs.csv  (long-form, one row per run)
  - results/T_patch2.npz           (tensor T[x,y,z] + metadata)

Designed to be notebook-friendly:
  - adds project root to sys.path when run as a script
  - uses multiprocessing 'spawn'
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import multiprocessing as mp
import numpy as np

try:
    import pandas as pd
except ImportError as e:
    raise ImportError(
        "pandas is required for Patch2 sweeps. Install with `pip install pandas`."
    ) from e

import simpy

from utils import config
from simulator.simulator import Simulator
from experiments.scenario_schema import METRICS, make_base_scenarios


def _apply_scenario_to_config(s: Dict[str, Any]) -> None:
    """Apply scenario knobs to global config.

    Each worker process has its own interpreter, so mutating global config is safe.
    """
    # Traffic
    config.TRAFFIC_PATTERN = s["traffic_pattern"]
    config.TRAFFIC_RATE = int(s.get("traffic_rate", config.TRAFFIC_RATE))
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

    # Worker-safe SIM_TIME override (spawned workers do not execute main())
    sim_time_env = os.environ.get("PATCH2_SIM_TIME_US", "").strip()
    if sim_time_env:
        try:
            config.SIM_TIME = float(sim_time_env)
        except Exception:
            pass


def _profile_snapshot() -> Dict[str, float]:
    """Lightweight per-process resource snapshot (Linux-friendly)."""
    out: Dict[str, float] = {}
    try:
        import resource

        ru = resource.getrusage(resource.RUSAGE_SELF)
        out["cpu_user_s"] = float(ru.ru_utime)
        out["cpu_sys_s"] = float(ru.ru_stime)

        # ru_maxrss units: kilobytes on Linux.
        out["max_rss_mb"] = float(ru.ru_maxrss) / 1024.0
    except Exception:
        out["cpu_user_s"] = float("nan")
        out["cpu_sys_s"] = float("nan")
        out["max_rss_mb"] = float("nan")
    return out


def _run_one(job: Tuple[Dict[str, Any], int, int]) -> Dict[str, Any]:
    """Worker: run one simulation.

    job = (scenario_dict, seed, n_drones)
    """
    scenario, seed, n_drones = job

    _apply_scenario_to_config(scenario)

    t0 = time.perf_counter()
    prof0 = _profile_snapshot()
    status = "ok"
    error_msg = ""

    try:
        env = simpy.Environment()
        channel_states = {i: simpy.Resource(env, capacity=1) for i in range(config.NUMBER_OF_DRONES)}

        # IMPORTANT: silence verbose prints inside worker processes.
        # (Some modules print per-drone initialization info which can deadlock the pool.
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
    prof1 = _profile_snapshot()

    row: Dict[str, Any] = {
        "scenario_id": scenario["scenario_id"],
        "scenario_key": scenario["scenario_key"],
        "mac_mode": scenario["mac_mode"],
        "traffic_pattern": scenario["traffic_pattern"],
        "traffic_rate": int(scenario.get("traffic_rate", -1)),
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
        "cpu_user_s": float(prof1.get("cpu_user_s", float("nan"))),
        "cpu_sys_s": float(prof1.get("cpu_sys_s", float("nan"))),
        "max_rss_mb": float(prof1.get("max_rss_mb", float("nan"))),
    }
    row.update(m)
    return row


def build_tensor(df: "pd.DataFrame", seeds: List[int]) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Build tensor T[x,y,z] from a long-form DataFrame."""
    # Scenario ordering must be deterministic.
    scenarios = (
        df[["scenario_id", "scenario_key"]]
        .drop_duplicates()
        .sort_values("scenario_key")
        .reset_index(drop=True)
    )
    scenario_ids = scenarios["scenario_id"].tolist()
    sid_to_x = {sid: i for i, sid in enumerate(scenario_ids)}
    seed_to_z = {s: i for i, s in enumerate(seeds)}

    Nx = len(scenario_ids)
    Ny = len(METRICS)
    Nz = len(seeds)

    T = np.full((Nx, Ny, Nz), np.nan, dtype=np.float64)

    for _, r in df.iterrows():
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
                T[x, y, z] = float(r[m])
            except Exception:
                T[x, y, z] = np.nan

    meta = {
        "scenario_ids": np.array(scenario_ids, dtype=object),
        "scenario_keys": scenarios["scenario_key"].to_numpy(dtype=object),
        "metrics": np.array(METRICS, dtype=object),
        "seeds": np.array(seeds, dtype=int),
    }
    return T, meta


def main() -> int:
    # ------------ configuration of sweep ------------
    # Seeds: default single-seed to match your requested cross-verification.
    # Override via env var, e.g.: PATCH2_SEEDS="0,21,42,84,168"
    seeds_env = os.environ.get("PATCH2_SEEDS", "2025").strip()
    seeds = [int(s) for s in seeds_env.split(",") if s.strip()]

    n_drones = int(getattr(config, "NUMBER_OF_DRONES", 10))
    avg_payload_bytes = int(getattr(config, "AVERAGE_PAYLOAD_LENGTH", 1024 * 8) / 8)

    scenarios = make_base_scenarios(
        avg_payload_bytes=avg_payload_bytes,
        payload_mode="fixed",
        payload_var_bytes=0,
        enable_dynamic_mobility=bool(getattr(config, "ENABLE_DYNAMIC_MOBILITY", True)),
        enable_obstacle_avoidance=bool(getattr(config, "ENABLE_OBSTACLE_AVOIDANCE", True)),
        uniform_iat_us=tuple(getattr(config, "UNIFORM_IAT_US", (500000, 505000))),
    )

    # Optional: override SIM_TIME for quick smoke tests
    # e.g.: PATCH2_SIM_TIME_US=200000
    sim_time_env = os.environ.get("PATCH2_SIM_TIME_US","").strip()
    if sim_time_env:
        try:
            config.SIM_TIME = float(sim_time_env)
        except Exception:
            pass

    # Optional: limit number of scenarios for quick smoke tests
    # e.g.: PATCH2_LIMIT_SCENARIOS=2
    lim_env = os.environ.get("PATCH2_LIMIT_SCENARIOS", "").strip()
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

    # ------------ multiprocessing ------------
    # Use spawn for notebook safety.
    ctx = mp.get_context("spawn")
    # Default worker count: up to 16, but never more than number of jobs.
    default_workers = min(max(1, (os.cpu_count() or 2) - 1), 16)
    default_workers = min(default_workers, len(jobs))

    # Optional override: PATCH2_WORKERS
    workers_env = os.environ.get("PATCH2_WORKERS", "").strip()
    if workers_env:
        try:
            workers = max(1, int(workers_env))
            workers = min(workers, len(jobs))
        except Exception:
            workers = default_workers
    else:
        workers = default_workers

    print(f"Patch2 sweep: {len(scenarios)} scenarios x {len(seeds)} seeds = {len(jobs)} runs")
    print(f"Using {workers} worker processes (spawn)")

    with ctx.Pool(processes=workers) as pool:
        rows = list(pool.imap_unordered(_run_one, jobs, chunksize=1))

    df = pd.DataFrame(rows)

    # ------------ outputs ------------
    out_dir = PROJECT_ROOT / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "sweep_patch2_runs.csv"
    df.to_csv(csv_path, index=False)

    # Tensor export
    T, meta = build_tensor(df, seeds=seeds)
    npz_path = out_dir / "T_patch2.npz"
    np.savez_compressed(npz_path, T=T, **meta)

    # ------------ Pandas summary (mean over seeds) ------------
    # For single seed, mean == value.
    ok_df = df[df["status"] == "ok"].copy()
    if len(ok_df) == 0:
        print("No successful runs. Inspect error rows in CSV.")
        print(f"Wrote: {csv_path}")
        return 1

    summary = ok_df.groupby(["mac_mode", "traffic_rate"])[METRICS + ["wall_s"]].mean().reset_index()
    print("\nMean metrics by (mac_mode, traffic_rate):")
    print(summary.to_string(index=False))

    print(f"\nWrote: {csv_path}")
    print(f"Wrote: {npz_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
