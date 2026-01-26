"""
Quick test for multiprocessing utilities.
This verifies the multiprocessing module works correctly.
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.multiprocessing_utils import (
    get_cpu_info, print_cpu_info, print_performance_summary,
    ParallelRunner, run_parallel
)


def simple_task(x, delay=0.1):
    """Simple task for testing parallel execution."""
    time.sleep(delay)
    return x * x


def test_cpu_info():
    """Test CPU info detection."""
    print("=" * 60)
    print("TEST 1: CPU Information")
    print("=" * 60)
    
    info = get_cpu_info()
    print(f"  CPU Name: {info['name']}")
    print(f"  Total Cores: {info['total_cores']}")
    print(f"  Available Cores: {info['available_cores']}")
    print(f"  Physical Cores: {info['physical_cores']}")
    print("[PASS] CPU info retrieved")
    return True


def test_parallel_runner():
    """Test ParallelRunner context manager."""
    print("\n" + "=" * 60)
    print("TEST 2: ParallelRunner")
    print("=" * 60)
    
    # Prepare tasks: compute squares of 1-8
    args_list = [(i, 0.2) for i in range(1, 9)]  # 8 tasks, 0.2s each
    
    with ParallelRunner(n_workers=4, show_progress=False) as runner:
        print(f"Running {len(args_list)} tasks in parallel...")
        start = time.time()
        results = runner.pool.starmap(simple_task, args_list)
        elapsed = time.time() - start
    
    expected = [1, 4, 9, 16, 25, 36, 49, 64]
    
    if results == expected:
        print(f"  Results: {results}")
        print(f"  Time: {elapsed:.2f}s (expected ~0.4s with 4 workers)")
        print("[PASS] ParallelRunner works correctly")
        return True
    else:
        print(f"  Expected: {expected}")
        print(f"  Got: {results}")
        print("[FAIL] Results don't match")
        return False


def test_run_parallel_helper():
    """Test the run_parallel convenience function."""
    print("\n" + "=" * 60)
    print("TEST 3: run_parallel helper")
    print("=" * 60)
    
    args_list = [(i, 0.1) for i in range(1, 5)]  # 4 tasks
    
    results = run_parallel(simple_task, args_list, n_workers=2, description="test tasks")
    
    expected = [1, 4, 9, 16]
    
    if results == expected:
        print(f"  Results: {results}")
        print("[PASS] run_parallel works correctly")
        return True
    else:
        print(f"  Expected: {expected}")
        print(f"  Got: {results}")
        print("[FAIL] Results don't match")
        return False


def test_performance_summary():
    """Test performance summary output."""
    print("\n" + "=" * 60)
    print("TEST 4: Performance Summary")
    print("=" * 60)
    
    print_performance_summary(
        total_runs=10,
        total_time=5.0,
        workers_used=4,
        individual_times=[1.0] * 10
    )
    
    print("[PASS] Performance summary displayed")
    return True


def run_multiprocessing_tests():
    """Run all multiprocessing tests."""
    print("\n" + "=" * 60)
    print("MULTIPROCESSING UTILITIES - TEST SUITE")
    print("=" * 60 + "\n")
    
    passed = 0
    total = 4
    
    tests = [
        test_cpu_info,
        test_parallel_runner,
        test_run_parallel_helper,
        test_performance_summary,
    ]
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[FAIL] Test failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 60)
    
    return passed == total, passed, total


if __name__ == "__main__":
    success, _, _ = run_multiprocessing_tests()
    sys.exit(0 if success else 1)
