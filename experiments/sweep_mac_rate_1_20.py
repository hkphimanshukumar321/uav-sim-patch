"""Sweep TRAFFIC_RATE=1..20 for MAC_MODE in {TDMA, CSMA} and export a tabular CSV.

Run from repo root:
    python3 experiments/sweep_mac_rate_1_20.py

Notebook cell equivalent:
    !python3 experiments/sweep_mac_rate_1_20.py
"""

import csv
import math
import simpy

from utils import config
from simulator.simulator import Simulator


def run_once(seed: int, mac_mode: str, rate: int):
    # Experiment knobs
    config.MAC_MODE = mac_mode
    config.TRAFFIC_PATTERN = "Poisson"
    config.TRAFFIC_RATE = rate

    # Batch-friendly
    config.ENABLE_PLOTS = False
    config.ENABLE_TIME_PRINTS = False

    env = simpy.Environment()
    channel_states = {i: simpy.Resource(env, capacity=1) for i in range(config.NUMBER_OF_DRONES)}

    sim = Simulator(seed=seed, env=env, channel_states=channel_states, n_drones=config.NUMBER_OF_DRONES)
    env.run(until=config.SIM_TIME)

    row = sim.metrics.to_dict()
    row.update({"mac_mode": mac_mode, "rate": rate, "seed": seed})

    # Replace non-finite values for CSV safety
    for k, v in list(row.items()):
        if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
            row[k] = str(v)

    return row


def main():
    seed = 2025
    rows = []

    for mac_mode in ("TDMA", "CSMA"):
        for rate in range(1, 21):
            print(f"Running MAC={mac_mode}, TRAFFIC_RATE={rate} ...")
            rows.append(run_once(seed=seed, mac_mode=mac_mode, rate=rate))

    # Column order
    fieldnames = [
        "mac_mode", "rate", "seed",
        "sent", "arrived",
        "pdr_percent", "e2e_delay_ms",
        "routing_load", "throughput_kbps",
        "hop_count", "collisions", "mac_delay_ms",
    ]

    out_csv = "sweep_mac_rate_1_20.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})

    # Console table (compact)
    print("\n=== SUMMARY (first 10 rows) ===")
    for r in rows[:10]:
        print(
            f"{r['mac_mode']:4s} rate={r['rate']:2d} "
            f"PDR={r['pdr_percent']:.2f}% "
            f"Delay={r['e2e_delay_ms']:.2f}ms "
            f"RL={r['routing_load']:.3f} "
            f"Thr={r['throughput_kbps']:.2f}Kbps "
            f"Coll={r['collisions']}"
        )

    print(f"\nSaved CSV: {out_csv}")


if __name__ == "__main__":
    main()
