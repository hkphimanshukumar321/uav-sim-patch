"""Sweep TRAFFIC_RATE=1..20 for MAC_MODE in {TDMA, CSMA} and export a tabular CSV.

Run from repo root:
    python3 experiments/sweep_mac_rate_1_20.py
    python3 experiments/sweep_mac_rate_1_20.py --workers 4  # Parallel execution

Notebook cell equivalent:
    !python3 experiments/sweep_mac_rate_1_20.py
"""

import csv
import math
import argparse
import time
import simpy
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import config
from simulator.simulator import Simulator
from utils.multiprocessing_utils import (
    ParallelRunner, print_cpu_info, print_performance_summary
)


def run_once_worker(seed: int, mac_mode: str, rate: int):
    """
    Worker function for parallel execution.
    
    Must be defined at module level for pickling.
    Returns (result_dict, elapsed_time).
    """
    start_time = time.time()
    
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
    
    elapsed_time = time.time() - start_time
    row["inference_time_s"] = elapsed_time
    
    print(f"  [OK] MAC={mac_mode}, rate={rate} completed in {elapsed_time:.2f}s")

    return row, elapsed_time


def run_once(seed: int, mac_mode: str, rate: int):
    """Run a single experiment (sequential version)."""
    result, _ = run_once_worker(seed, mac_mode, rate)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Sweep TRAFFIC_RATE for MAC modes and export CSV"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=None,
        help="Number of parallel workers (default: auto-detect, use 1 for sequential)"
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Force sequential execution"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2025,
        help="Random seed (default: 2025)"
    )
    
    args = parser.parse_args()
    seed = args.seed
    
    # Generate all (mac_mode, rate) combinations
    combinations = []
    for mac_mode in ("TDMA", "CSMA"):
        for rate in range(1, 21):
            combinations.append((seed, mac_mode, rate))
    
    total_runs = len(combinations)
    
    print(f"\n{'='*60}")
    print(f"MAC Rate Sweep Experiment")
    print(f"{'='*60}")
    print(f"Total configurations: {total_runs}")
    print(f"MAC Modes: TDMA, CSMA")
    print(f"Traffic Rates: 1-20")
    print(f"Seed: {seed}")
    
    if args.sequential or args.workers == 1:
        # Sequential execution
        print_cpu_info(workers_used=1)
        print("Running in sequential mode...")
        
        start_time = time.time()
        rows = []
        individual_times = []
        
        for combo in combinations:
            print(f"Running MAC={combo[1]}, TRAFFIC_RATE={combo[2]} ...")
            result, elapsed = run_once_worker(*combo)
            rows.append(result)
            individual_times.append(elapsed)
        
        total_time = time.time() - start_time
        print_performance_summary(
            total_runs=total_runs,
            total_time=total_time,
            workers_used=1,
            individual_times=individual_times
        )
    else:
        # Parallel execution
        with ParallelRunner(n_workers=args.workers, show_progress=False) as runner:
            print(f"Running {total_runs} configurations in parallel...")
            
            start_time = time.time()
            results = runner.pool.starmap(run_once_worker, combinations)
            total_time = time.time() - start_time
            
            # Extract rows and times
            rows = [r[0] for r in results]
            individual_times = [r[1] for r in results]
            
            print_performance_summary(
                total_runs=total_runs,
                total_time=total_time,
                workers_used=runner.n_workers,
                individual_times=individual_times
            )

    # Column order
    fieldnames = [
        "mac_mode", "rate", "seed",
        "sent", "arrived",
        "pdr_percent", "e2e_delay_ms",
        "routing_load", "throughput_kbps",
        "hop_count", "collisions", "mac_delay_ms",
        "inference_time_s",
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
            f"Coll={r['collisions']} "
            f"Time={r['inference_time_s']:.2f}s"
        )

    print(f"\nSaved CSV: {out_csv}")


if __name__ == "__main__":
    main()

