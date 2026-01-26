"""
Multiprocessing Utilities for UAV Network Simulator

Provides CPU detection, parallel execution management, and timing utilities
for accelerating simulations on multi-core processors.

Usage:
    from utils.multiprocessing_utils import ParallelRunner, print_cpu_info
    
    # Display CPU information
    print_cpu_info()
    
    # Run tasks in parallel
    with ParallelRunner(n_workers=4) as runner:
        results = runner.run(my_function, list_of_args)
"""

import os
import platform
import time
import multiprocessing as mp
from typing import Callable, List, Any, Dict, Optional, Tuple
from functools import partial
from datetime import datetime


def get_cpu_info() -> Dict[str, Any]:
    """
    Get comprehensive CPU information.
    
    Returns:
        Dictionary with:
        - name: CPU model name
        - total_cores: Total number of CPU cores
        - available_cores: Recommended cores for processing (leaves 1 free)
        - physical_cores: Physical core count (if available)
    """
    cpu_info = {
        "name": "Unknown CPU",
        "total_cores": os.cpu_count() or 1,
        "available_cores": max(1, (os.cpu_count() or 1) - 1),
        "physical_cores": None,
    }
    
    # Get CPU name
    try:
        if platform.system() == "Windows":
            import subprocess
            result = subprocess.run(
                ["wmic", "cpu", "get", "name"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                cpu_info["name"] = lines[1].strip()
        elif platform.system() == "Linux":
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        cpu_info["name"] = line.split(":")[1].strip()
                        break
        elif platform.system() == "Darwin":  # macOS
            import subprocess
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5
            )
            cpu_info["name"] = result.stdout.strip()
    except Exception:
        pass  # Keep default "Unknown CPU"
    
    # Try to get physical core count (requires psutil)
    try:
        import psutil
        cpu_info["physical_cores"] = psutil.cpu_count(logical=False)
    except ImportError:
        pass
    
    return cpu_info


def print_cpu_info(workers_used: int = None) -> Dict[str, Any]:
    """
    Print formatted CPU information banner.
    
    Args:
        workers_used: Number of worker processes that will be used
        
    Returns:
        CPU info dictionary
    """
    info = get_cpu_info()
    
    if workers_used is None:
        workers_used = info["available_cores"]
    
    print()
    print("+" + "=" * 66 + "+")
    print("|  CPU Information" + " " * 49 + "|")
    print("+" + "=" * 66 + "+")
    
    # Truncate CPU name if too long
    cpu_name = info["name"][:50] if len(info["name"]) > 50 else info["name"]
    print(f"|  Processor: {cpu_name:<52} |")
    print(f"|  Total Cores: {info['total_cores']:<52} |")
    
    if info["physical_cores"]:
        print(f"|  Physical Cores: {info['physical_cores']:<49} |")
    
    print(f"|  Available for Processing: {info['available_cores']:<38} |")
    print(f"|  Workers Used: {workers_used:<51} |")
    print("+" + "=" * 66 + "+")
    print()
    
    return info


def print_performance_summary(
    total_runs: int,
    total_time: float,
    workers_used: int,
    individual_times: List[float] = None
) -> None:
    """
    Print performance summary after parallel execution.
    
    Args:
        total_runs: Number of simulation runs completed
        total_time: Total wall-clock time in seconds
        workers_used: Number of worker processes used
        individual_times: List of individual run times (optional)
    """
    avg_time = total_time / total_runs if total_runs > 0 else 0
    
    # Estimate sequential time
    if individual_times:
        estimated_sequential = sum(individual_times)
    else:
        estimated_sequential = avg_time * total_runs
    
    speedup = estimated_sequential / total_time if total_time > 0 else 1.0
    
    print()
    print("+" + "=" * 66 + "+")
    print("|  Performance Summary" + " " * 45 + "|")
    print("+" + "=" * 66 + "+")
    print(f"|  Total Runs: {total_runs:<53} |")
    print(f"|  Total Time: {total_time:.2f}s{' ' * (50 - len(f'{total_time:.2f}'))} |")
    print(f"|  Average Time/Run: {avg_time:.2f}s{' ' * (44 - len(f'{avg_time:.2f}'))} |")
    
    if individual_times:
        print(f"|  Estimated Sequential Time: {estimated_sequential:.2f}s{' ' * (35 - len(f'{estimated_sequential:.2f}'))} |")
    
    speedup_str = f"{speedup:.2f}x (using {workers_used} workers)"
    print(f"|  Speedup: {speedup_str:<55} |")
    print("+" + "=" * 66 + "+")
    print()


class ParallelRunner:
    """
    Context manager for parallel execution of simulation tasks.
    
    Features:
    - Automatic CPU detection and worker management
    - Progress tracking
    - Timing and performance reporting
    
    Usage:
        with ParallelRunner(n_workers=4) as runner:
            results = runner.run(task_function, [(arg1,), (arg2,), ...])
    """
    
    def __init__(self, n_workers: int = None, show_progress: bool = True):
        """
        Initialize ParallelRunner.
        
        Args:
            n_workers: Number of worker processes (None = auto-detect)
            show_progress: Whether to print progress updates
        """
        cpu_info = get_cpu_info()
        
        if n_workers is None:
            self.n_workers = cpu_info["available_cores"]
        else:
            # Clamp workers to valid range
            self.n_workers = max(1, min(n_workers, cpu_info["total_cores"]))
        
        self.show_progress = show_progress
        self.cpu_info = cpu_info
        self.pool = None
        self.start_time = None
        self.individual_times = []
    
    def __enter__(self):
        """Start the process pool."""
        # Print CPU info when entering context
        print_cpu_info(self.n_workers)
        self.pool = mp.Pool(processes=self.n_workers)
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up the process pool."""
        if self.pool:
            self.pool.close()
            self.pool.join()
        return False
    
    def run(
        self, 
        func: Callable, 
        args_list: List[Tuple],
        description: str = "simulations"
    ) -> List[Any]:
        """
        Run function in parallel across all argument combinations.
        
        Args:
            func: Function to execute (must be picklable - defined at module level)
            args_list: List of argument tuples for each function call
            description: Description for progress messages
            
        Returns:
            List of results from all function calls
        """
        total = len(args_list)
        
        if self.show_progress:
            print(f"Running {total} {description} across {self.n_workers} workers...")
        
        # Use starmap for parallel execution
        results = self.pool.starmap(func, args_list)
        
        total_time = time.time() - self.start_time
        
        if self.show_progress:
            print_performance_summary(
                total_runs=total,
                total_time=total_time,
                workers_used=self.n_workers,
                individual_times=self.individual_times if self.individual_times else None
            )
        
        return results
    
    def run_with_timing(
        self, 
        func: Callable, 
        args_list: List[Tuple],
        description: str = "simulations"
    ) -> Tuple[List[Any], List[float]]:
        """
        Run function in parallel and collect individual timing data.
        
        Args:
            func: Function to execute (should return (result, elapsed_time))
            args_list: List of argument tuples
            description: Description for progress messages
            
        Returns:
            Tuple of (results list, times list)
        """
        results_with_times = self.run(func, args_list, description)
        
        # Unpack results and times
        if results_with_times and isinstance(results_with_times[0], tuple) and len(results_with_times[0]) == 2:
            results = [r[0] for r in results_with_times]
            times = [r[1] for r in results_with_times]
            self.individual_times = times
        else:
            results = results_with_times
            times = []
        
        return results, times


def timed_wrapper(func: Callable) -> Callable:
    """
    Decorator to add timing to a function.
    
    The wrapped function returns (original_result, elapsed_time).
    """
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        return result, elapsed
    return wrapper


# Convenience function for simple parallel execution
def run_parallel(
    func: Callable,
    args_list: List[Tuple],
    n_workers: int = None,
    description: str = "tasks"
) -> List[Any]:
    """
    Simple interface for parallel execution.
    
    Args:
        func: Function to execute in parallel
        args_list: List of argument tuples
        n_workers: Number of workers (None = auto)
        description: Description for progress output
        
    Returns:
        List of results
    """
    with ParallelRunner(n_workers=n_workers) as runner:
        return runner.run(func, args_list, description)
