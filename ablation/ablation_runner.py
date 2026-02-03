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
import warnings
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Suppress the "found in sys.modules" warning (harmless, caused by python -m execution)
warnings.filterwarnings("ignore", message=".*found in sys.modules.*", category=RuntimeWarning)

# Use non-interactive backend BEFORE importing pyplot (prevents blocking figures)
import matplotlib
matplotlib.use('Agg')

import simpy

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import config
from simulator.simulator import Simulator
from ablation.ablation_config import AblationConfig, SWEEP_PRESETS
from utils.multiprocessing_utils import (
    ParallelRunner, print_cpu_info, print_performance_summary
)


class TimeEstimator:
    """
    Estimates ablation study runtime based on system specs and parameters.
    
    Provides:
    - Pre-run time estimation based on historical benchmarks
    - Live progress tracking with ETA updates
    - System resource information display
    """
    
    # Historical benchmark: seconds per simulation run (at 30s sim time)
    # Calibrated from actual runs on various systems
    BASE_TIME_PER_RUN = 270  # ~4.5 minutes per run baseline
    
    # Scaling factors
    SIM_TIME_FACTOR = 30 * 1e6  # baseline sim time (30s in microseconds)
    DRONE_SCALING_EXPONENT = 1.3  # runtime scales ~O(n^1.3) with drones
    
    def __init__(self):
        self.start_time = None
        self.completed_runs = 0
        self.total_runs = 0
        self.run_times = []
        
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Gather system information for estimation and display."""
        import platform
        
        info = {
            "os": platform.system(),
            "os_version": platform.release(),
            "processor": platform.processor() or "Unknown",
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count() or 1,
        }
        
        # Try to get more detailed CPU info
        try:
            import multiprocessing
            info["cpu_count"] = multiprocessing.cpu_count()
        except:
            pass
        
        # Try to get CPU frequency (Windows)
        try:
            import subprocess
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["wmic", "cpu", "get", "maxclockspeed"],
                    capture_output=True, text=True, timeout=5
                )
                lines = [l.strip() for l in result.stdout.split('\n') if l.strip() and not l.strip().startswith('Max')]
                if lines:
                    info["cpu_freq_mhz"] = int(lines[0])
            elif platform.system() == "Linux":
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'cpu MHz' in line:
                            info["cpu_freq_mhz"] = int(float(line.split(':')[1].strip()))
                            break
        except:
            info["cpu_freq_mhz"] = None
            
        return info
    
    def estimate_single_run_time(self, params: Dict[str, Any]) -> float:
        """
        Estimate time for a single simulation run in seconds.
        
        Args:
            params: Simulation parameters
            
        Returns:
            Estimated time in seconds
        """
        # Base time
        estimated = self.BASE_TIME_PER_RUN
        
        # Scale by simulation time
        sim_time = params.get("SIM_TIME", getattr(config, "SIM_TIME", self.SIM_TIME_FACTOR))
        estimated *= (sim_time / self.SIM_TIME_FACTOR)
        
        # Scale by number of drones
        num_drones = params.get("NUMBER_OF_DRONES", getattr(config, "NUMBER_OF_DRONES", 10))
        estimated *= (num_drones / 10) ** self.DRONE_SCALING_EXPONENT
        
        # Adjust for traffic rate (higher traffic = more messages = longer)
        traffic_rate = params.get("TRAFFIC_RATE", getattr(config, "TRAFFIC_RATE", 5))
        estimated *= (1 + 0.1 * (traffic_rate / 5))
        
        return estimated
    
    def estimate_total_time(
        self, 
        sweep_config: Dict[str, List[Any]], 
        seeds: List[int],
        n_workers: int = None
    ) -> Dict[str, Any]:
        """
        Estimate total ablation study runtime.
        
        Args:
            sweep_config: Parameter sweep configuration
            seeds: List of seeds
            n_workers: Number of parallel workers (None = auto)
            
        Returns:
            Dictionary with estimation details
        """
        import itertools
        
        # Calculate total runs
        combinations = list(itertools.product(*sweep_config.values()))
        total_runs = len(combinations) * len(seeds)
        
        # Get worker count
        if n_workers is None:
            n_workers = max(1, (os.cpu_count() or 1) - 1)
        
        # Calculate average run time based on parameter combinations
        total_sequential_time = 0
        for combo in combinations:
            params = dict(zip(sweep_config.keys(), combo))
            for _ in seeds:
                total_sequential_time += self.estimate_single_run_time(params)
        
        # Parallel speedup (with overhead factor)
        parallel_overhead = 1.15  # 15% overhead for process management
        parallel_time = (total_sequential_time / n_workers) * parallel_overhead
        
        return {
            "total_runs": total_runs,
            "configurations": len(combinations),
            "seeds_per_config": len(seeds),
            "workers": n_workers,
            "sequential_time_secs": total_sequential_time,
            "parallel_time_secs": parallel_time,
            "estimated_minutes": parallel_time / 60,
            "estimated_hours": parallel_time / 3600,
        }
    
    def print_estimation(self, estimate: Dict[str, Any], system_info: Dict[str, Any] = None):
        """Print formatted time estimation and system info."""
        if system_info is None:
            system_info = self.get_system_info()
        
        print("\n" + "="*70)
        print("ABLATION STUDY TIME ESTIMATION")
        print("="*70)
        
        # System info
        print("\n📊 SYSTEM INFORMATION:")
        print(f"   OS:           {system_info['os']} {system_info['os_version']}")
        print(f"   Processor:    {system_info['processor']}")
        if system_info.get('cpu_freq_mhz'):
            print(f"   CPU Freq:     {system_info['cpu_freq_mhz']} MHz")
        print(f"   CPU Cores:    {system_info['cpu_count']}")
        print(f"   Python:       {system_info['python_version']}")
        
        # Run configuration
        print("\n📋 RUN CONFIGURATION:")
        print(f"   Configurations: {estimate['configurations']}")
        print(f"   Seeds/Config:   {estimate['seeds_per_config']}")
        print(f"   Total Runs:     {estimate['total_runs']}")
        print(f"   Workers:        {estimate['workers']}")
        
        # Time estimate
        print("\n⏱️  TIME ESTIMATE:")
        if estimate['estimated_hours'] >= 1:
            print(f"   Estimated:      {estimate['estimated_hours']:.1f} hours ({estimate['estimated_minutes']:.0f} minutes)")
        else:
            print(f"   Estimated:      {estimate['estimated_minutes']:.1f} minutes")
        
        print(f"   Sequential:     {estimate['sequential_time_secs']/60:.1f} minutes (if 1 worker)")
        print(f"   Speedup:        {estimate['sequential_time_secs']/estimate['parallel_time_secs']:.1f}x")
        
        # Calculate completion time
        from datetime import datetime, timedelta
        completion_time = datetime.now() + timedelta(seconds=estimate['parallel_time_secs'])
        print(f"   Expected Done:  {completion_time.strftime('%H:%M:%S')}")
        
        print("="*70 + "\n")
    
    def start_tracking(self, total_runs: int):
        """Start progress tracking."""
        self.start_time = time.time()
        self.total_runs = total_runs
        self.completed_runs = 0
        self.run_times = []
    
    def record_run(self, run_time: float):
        """Record a completed run time."""
        self.completed_runs += 1
        self.run_times.append(run_time)
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress with ETA."""
        if self.start_time is None:
            return {}
        
        elapsed = time.time() - self.start_time
        
        if self.completed_runs > 0:
            avg_time = sum(self.run_times) / len(self.run_times)
            remaining_runs = self.total_runs - self.completed_runs
            eta_seconds = remaining_runs * avg_time
        else:
            eta_seconds = 0
        
        return {
            "completed": self.completed_runs,
            "total": self.total_runs,
            "percent": (self.completed_runs / self.total_runs * 100) if self.total_runs > 0 else 0,
            "elapsed_secs": elapsed,
            "eta_secs": eta_seconds,
            "avg_run_time": sum(self.run_times) / len(self.run_times) if self.run_times else 0,
        }
    
    def print_progress(self, extra_info: str = ""):
        """Print current progress with ETA."""
        prog = self.get_progress()
        if not prog:
            return
        
        elapsed_str = self._format_time(prog['elapsed_secs'])
        eta_str = self._format_time(prog['eta_secs'])
        
        bar_width = 30
        filled = int(bar_width * prog['percent'] / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        print(f"\r  [{bar}] {prog['percent']:.1f}% | "
              f"{prog['completed']}/{prog['total']} | "
              f"Elapsed: {elapsed_str} | ETA: {eta_str} {extra_info}",
              end="", flush=True)
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as human readable string."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"


# Global estimator instance
time_estimator = TimeEstimator()




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
        
        # Determine worker count for estimation
        if n_workers is None:
            actual_workers = max(1, (os.cpu_count() or 1) - 1)
        else:
            actual_workers = n_workers
        
        # Show time estimation BEFORE starting
        estimate = time_estimator.estimate_total_time(sweep_config, seeds, actual_workers)
        system_info = time_estimator.get_system_info()
        time_estimator.print_estimation(estimate, system_info)
        
        print(f"{'='*60}")
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
            
            # Start progress tracking
            time_estimator.start_tracking(total_runs)
            
            results = []
            individual_times = []
            run_index = 0
            start_time = time.time()
            
            for params, seed in tasks:
                run_index += 1
                
                # Show progress bar with ETA
                time_estimator.print_progress(f"| {params} seed={seed}")
                
                try:
                    result, elapsed = _run_single_task(params, seed)
                    results.append(result)
                    individual_times.append(elapsed)
                    
                    # Record for ETA calculation
                    time_estimator.record_run(elapsed)
                    
                except Exception as e:
                    print(f"\n    ERROR: {e}")
                    # Record error
                    results.append({
                        **params,
                        "seed": seed,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                
                # Reset for next run
                self.reset_config()
            
            print()  # New line after progress bar
            
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
    
    def save_results(self, filename: str = None, generate_plots: bool = True) -> str:
        """
        Save results to CSV file in a timestamped run directory.
        
        Each run creates a new directory: results/run_YYYYMMDD_HHMMSS/
        containing:
        - results.csv (the ablation results)
        - plots/ (generated plots if enabled)
        
        This preserves previous runs and keeps results organized.
        """
        if not self.results:
            print("No results to save")
            return None
        
        # Create timestamped run directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(self.output_dir, f"run_{timestamp}")
        os.makedirs(run_dir, exist_ok=True)
        
        # Create CSV filename
        if filename is None:
            filename = "results.csv"
        
        filepath = os.path.join(run_dir, filename)
        
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
        
        print(f"\n{'='*60}")
        print(f"Results saved to: {filepath}")
        
        # Generate plots if enabled
        if generate_plots:
            try:
                from ablation.plot_results import plot_mac_comparison
                plots_dir = os.path.join(run_dir, "plots")
                os.makedirs(plots_dir, exist_ok=True)
                plot_mac_comparison(filepath, plots_dir)
                print(f"Plots saved to: {plots_dir}/")
            except Exception as e:
                import traceback
                print(f"Warning: Could not generate plots: {e}")
                print("Traceback:")
                traceback.print_exc()
                print("\nTo generate plots manually, run:")
                print(f"  python -m ablation.plot_results \"{filepath}\" -o \"{os.path.join(run_dir, 'plots')}\"")
        
        print(f"{'='*60}")
        
        # Also save a copy to the main output dir with timestamp for backwards compatibility
        legacy_filepath = os.path.join(self.output_dir, f"ablation_{timestamp}.csv")
        import shutil
        shutil.copy(filepath, legacy_filepath)
        
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

