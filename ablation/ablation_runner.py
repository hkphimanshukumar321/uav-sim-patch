"""
Ablation Study Runner

Execution engine for systematic parameter sweeps with:
- Parameter injection into config module
- Grid/random search support
- Multi-seed experiments for statistical validity
- CSV/JSON output with all parameters logged
- **Multiprocessing support for faster execution**

Usage:
    # From command line
    python -m ablation.ablation_runner --sweep quick_channel --output results/
    python -m ablation.ablation_runner --sweep quick_channel --workers 4  # Parallel
    
    # Programmatic usage
    from ablation.ablation_runner import AblationRunner
    
    runner = AblationRunner()
    runner.run_sweep("quick_channel", seeds=[2025, 2026, 2027])
"""

import os
import sys
import csv
import json
import math
import argparse
import itertools
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import simpy

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import config
from simulator.simulator import Simulator
from ablation.ablation_config import AblationConfig, SWEEP_PRESETS
from utils.multiprocessing_utils import (
    ParallelRunner, print_cpu_info, print_performance_summary
)


def _run_single_task(params: Dict[str, Any], seed: int) -> Tuple[Dict[str, Any], float]:
    """
    Standalone worker function for parallel execution.
    
    Must be at module level for pickling.
    
    Args:
        params: Parameter dictionary to inject
        seed: Random seed for this run
        
    Returns:
        Tuple of (result_dict, elapsed_time)
    """
    start_time = time.time()
    
    # Inject parameters
    for param_name, value in params.items():
        if hasattr(config, param_name):
            setattr(config, param_name, value)
        else:
            setattr(config, param_name, value)
    
    # Batch mode settings
    config.ENABLE_PLOTS = False
    config.ENABLE_TIME_PRINTS = False
    
    # Create simulation environment
    env = simpy.Environment()
    channel_states = {i: simpy.Resource(env, capacity=1) 
                     for i in range(config.NUMBER_OF_DRONES)}
    
    # Run simulation
    sim = Simulator(seed=seed, env=env, channel_states=channel_states, 
                   n_drones=config.NUMBER_OF_DRONES)
    env.run(until=config.SIM_TIME)
    
    elapsed_time = time.time() - start_time
    
    # Collect results
    result = sim.metrics.to_dict()
    result.update(params)
    result["seed"] = seed
    result["timestamp"] = datetime.now().isoformat()
    result["inference_time_s"] = elapsed_time
    
    # Handle non-finite values
    for k, v in list(result.items()):
        if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
            result[k] = str(v)
    
    # Print progress
    mac_mode = params.get("MAC_MODE", getattr(config, "MAC_MODE", "Unknown"))
    param_str = ", ".join(f"{k}={v}" for k, v in params.items())
    print(f"  [OK] MAC={mac_mode} | {param_str}, seed={seed} completed in {elapsed_time:.2f}s")
    
    return result, elapsed_time


class AblationRunner:
    """
    Execution engine for ablation studies.
    
    Features:
    - Parameter injection at runtime
    - Multiple seed support for statistical validity
    - Comprehensive logging of all parameters
    - CSV output for easy analysis
    - **Multiprocessing for faster execution**
    """
    
    def __init__(self, output_dir: str = "ablation_results"):
        self.output_dir = output_dir
        self.results = []
        
    def inject_parameters(self, params: Dict[str, Any]) -> None:
        """Inject parameters into the config module at runtime"""
        for param_name, value in params.items():
            if hasattr(config, param_name):
                setattr(config, param_name, value)
            else:
                # Add new attribute if it doesn't exist
                setattr(config, param_name, value)
    
    def reset_config(self) -> None:
        """Reset config to default values"""
        defaults = AblationConfig.get_defaults()
        for param_name, value in defaults.items():
            if hasattr(config, param_name):
                setattr(config, param_name, value)
    
    def run_single(self, params: Dict[str, Any], seed: int) -> Dict[str, Any]:
        """Run a single simulation with given parameters and seed"""
        result, _ = _run_single_task(params, seed)
        return result
    
    def run_sweep(
        self, 
        sweep_name: str, 
        seeds: List[int] = None,
        custom_sweep: Dict[str, List[Any]] = None,
        n_workers: int = None,
        parallel: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Run a parameter sweep.
        
        Args:
            sweep_name: Name of preset sweep from SWEEP_PRESETS, or "custom"
            seeds: List of seeds for statistical validity
            custom_sweep: Custom sweep configuration (if sweep_name == "custom")
            n_workers: Number of parallel workers (None = auto-detect)
            parallel: Whether to use parallel execution (default True)
        
        Returns:
            List of result dictionaries
        """
        if seeds is None:
            # Default: 3 seeds for conference paper level statistical validity
            seeds = [2025, 2026, 2027]

        
        # Get sweep configuration
        if sweep_name == "custom" and custom_sweep:
            sweep_config = custom_sweep
        elif sweep_name in SWEEP_PRESETS:
            sweep_config = SWEEP_PRESETS[sweep_name]
        else:
            print(f"Unknown sweep: {sweep_name}")
            print(f"Available sweeps: {list(SWEEP_PRESETS.keys())}")
            return []
        
        # Generate all parameter combinations
        param_names = list(sweep_config.keys())
        param_values = list(sweep_config.values())
        combinations = list(itertools.product(*param_values))
        
        total_runs = len(combinations) * len(seeds)
        
        print(f"\n{'='*60}")
        print(f"Ablation Study: {sweep_name}")
        print(f"{'='*60}")
        print(f"Parameters: {param_names}")
        print(f"Configurations: {len(combinations)}")
        print(f"Seeds: {seeds}")
        print(f"Total runs: {total_runs}")
        
        # Prepare all tasks as (params_dict, seed) tuples
        tasks = []
        for combo in combinations:
            params = dict(zip(param_names, combo))
            for seed in seeds:
                tasks.append((params, seed))
        
        if parallel and len(tasks) > 1:
            # Parallel execution
            with ParallelRunner(n_workers=n_workers, show_progress=False) as runner:
                print(f"Running {total_runs} experiments in parallel...")
                
                start_time = time.time()
                results_with_times = runner.pool.starmap(_run_single_task, tasks)
                total_time = time.time() - start_time
                
                # Extract results and times
                results = [r[0] for r in results_with_times]
                individual_times = [r[1] for r in results_with_times]
                
                print_performance_summary(
                    total_runs=total_runs,
                    total_time=total_time,
                    workers_used=runner.n_workers,
                    individual_times=individual_times
                )
        else:
            # Sequential execution
            print_cpu_info(workers_used=1)
            print("Running in sequential mode...")
            
            results = []
            individual_times = []
            run_index = 0
            start_time = time.time()
            
            for params, seed in tasks:
                run_index += 1
                print(f"  [{run_index}/{total_runs}] {params} seed={seed}")
                
                try:
                    result, elapsed = _run_single_task(params, seed)
                    results.append(result)
                    individual_times.append(elapsed)
                except Exception as e:
                    print(f"    ERROR: {e}")
                    # Record error
                    results.append({
                        **params,
                        "seed": seed,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                
                # Reset for next run
                self.reset_config()
            
            total_time = time.time() - start_time
            print_performance_summary(
                total_runs=total_runs,
                total_time=total_time,
                workers_used=1,
                individual_times=individual_times
            )
        
        self.results = results
        self.print_results_table()
        return results

    def print_results_table(self):
        """Print a tabular summary of results."""
        if not self.results:
            return

        print("\n" + "="*100)
        print(f"{'ABLATION RESULTS SUMMARY':^100}")
        print("="*100)

        # Define headers
        headers = ["MAC", "Traffic", "Drones", "Seed", "PDR (%)", "Delay (ms)", "Thru (kbps)", "Collisions"]
        row_fmt = "{:<12} {:<10} {:<8} {:<6} {:<10} {:<12} {:<12} {:<10}"
        
        print(row_fmt.format(*headers))
        print("-" * 100)
        
        # Sort results by MAC/Traffic for better readability
        sorted_results = sorted(self.results, key=lambda x: (str(x.get("MAC_MODE", "")), float(x.get("TRAFFIC_RATE", 0))))

        for r in sorted_results:
            mac = str(r.get("MAC_MODE", r.get("mac_mode", "N/A")))
            traffic = str(r.get("TRAFFIC_RATE", "N/A"))
            drones = str(r.get("NUMBER_OF_DRONES", "N/A"))
            seed = str(r.get("seed", ""))
            
            try:
                pdr = f"{float(r.get('pdr_percent', 0)):.1f}"
                delay = f"{float(r.get('e2e_delay_ms', 0)):.1f}"
                thru = f"{float(r.get('throughput_kbps', 0)):.1f}"
                coll = f"{int(r.get('collisions', 0))}"
            except (ValueError, TypeError):
                pdr, delay, thru, coll = "Err", "Err", "Err", "Err"
            
            print(row_fmt.format(mac, traffic, drones, seed, pdr, delay, thru, coll))
            
        print("="*100 + "\n")
    
    def save_results(self, filename: str = None) -> str:
        """Save results to CSV file"""
        if not self.results:
            print("No results to save")
            return None
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ablation_{timestamp}.csv"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # Get all column names
        all_keys = set()
        for r in self.results:
            all_keys.update(r.keys())
        
        # Order columns: params first, then metrics
        param_keys = list(AblationConfig.PARAMETERS.keys())
        metric_keys = ["sent", "arrived", "pdr_percent", "e2e_delay_ms", 
                      "routing_load", "throughput_kbps", "hop_count", 
                      "collisions", "mac_delay_ms", "inference_time_s"]
        other_keys = ["seed", "timestamp", "error"]
        
        fieldnames = []
        for k in param_keys + metric_keys + other_keys:
            if k in all_keys:
                fieldnames.append(k)
        # Add any remaining keys
        for k in all_keys:
            if k not in fieldnames:
                fieldnames.append(k)
        
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in self.results:
                writer.writerow({k: r.get(k, "") for k in fieldnames})
        
        print(f"Results saved to: {filepath}")
        return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Run ablation studies for UAV network simulation"
    )
    parser.add_argument(
        "--sweep", "-s",
        choices=list(SWEEP_PRESETS.keys()),
        default="quick_channel",
        help="Preset sweep configuration"
    )
    parser.add_argument(
        "--seeds", "-n",
        type=int, 
        nargs="+",
        default=[2025, 2026, 2027],
        help="Seeds for runs (default: 2025-2027 for conference paper validity)"
    )

    parser.add_argument(
        "--output", "-o",
        default="ablation_results",
        help="Output directory for results"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would run without executing"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run with single seed for quick test"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=None,
        help="Number of parallel workers (default: auto-detect)"
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Force sequential execution"
    )
    
    args = parser.parse_args()
    
    if args.quick:
        args.seeds = [2025]
    
    if args.dry_run:
        sweep_config = SWEEP_PRESETS.get(args.sweep, {})
        param_names = list(sweep_config.keys())
        param_values = list(sweep_config.values())
        combinations = list(itertools.product(*param_values))
        
        print(f"DRY RUN: Sweep '{args.sweep}'")
        print(f"  Parameters: {param_names}")
        print(f"  Configurations: {len(combinations)}")
        print(f"  Seeds: {args.seeds}")
        print(f"  Total runs: {len(combinations) * len(args.seeds)}")
        print("\nConfigurations:")
        for i, combo in enumerate(combinations[:5], 1):
            print(f"  {i}. {dict(zip(param_names, combo))}")
        if len(combinations) > 5:
            print(f"  ... and {len(combinations) - 5} more")
        return
    
    runner = AblationRunner(output_dir=args.output)
    runner.run_sweep(
        args.sweep, 
        seeds=args.seeds,
        n_workers=args.workers,
        parallel=not args.sequential
    )
    runner.save_results()


if __name__ == "__main__":
    main()

