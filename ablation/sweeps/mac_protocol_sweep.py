"""
MAC Protocol Comparison Sweep

Comprehensive sweep comparing TDMA, CSMA, and ALOHA under varying load conditions.

Usage:
    python -m ablation.sweeps.mac_protocol_sweep --quick
    python -m ablation.sweeps.mac_protocol_sweep --output results/
"""

import os
import sys

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ablation.ablation_runner import AblationRunner
from ablation.plot_results import plot_mac_comparison


# MAC Protocol Comparison Sweeps
MAC_PROTOCOL_SWEEP = {
    # Quick comparison - just 3 rates
    "quick": {
        "MAC_MODE": ["TDMA", "CSMA", "ALOHA"],
        "TRAFFIC_RATE": [5, 10, 15],
    },
    
    # Full load comparison - 1 to 20 packets/sec (all MAC protocols)
    "full_load": {
        "MAC_MODE": ["TDMA", "CSMA", "ALOHA", "STDMA"],
        "TRAFFIC_RATE": [1, 2, 5, 10, 15, 20],
    },
    
    # Improved TDMA vs CSMA comparison (the main analysis)
    "tdma_vs_csma": {
        "MAC_MODE": ["TDMA", "CSMA"],
        "TRAFFIC_RATE": [1, 2, 3, 4, 5, 7, 10, 12, 15, 17, 20],
    },
    
    # Low load - CSMA expected to perform better
    "low_load": {
        "MAC_MODE": ["TDMA", "CSMA", "ALOHA", "STDMA"],
        "TRAFFIC_RATE": [1, 2, 3, 5],
    },

    
    # High load - TDMA expected to perform better
    "high_load": {
        "MAC_MODE": ["TDMA", "CSMA", "ALOHA"],
        "TRAFFIC_RATE": [10, 15, 20, 25, 30],
    },
    
    # Contention window sensitivity (CSMA only)
    "contention_window": {
        "MAC_MODE": ["CSMA"],
        "CW_MIN": [15, 31, 63, 127],
        "TRAFFIC_RATE": [5, 10, 15],
    },
    
    # TDMA slot configuration
    "tdma_slots": {
        "MAC_MODE": ["TDMA"],
        "TDMA_SLOTS_PER_FRAME": [5, 10, 15, 20],
        "TRAFFIC_RATE": [5, 10, 15],
    },
    
    # Scalability test
    "scalability": {
        "MAC_MODE": ["TDMA", "CSMA"],
        "NUMBER_OF_DRONES": [5, 10, 15, 20],
        "TRAFFIC_RATE": [10],
    },
}


def get_mac_sweep(name: str = "quick"):
    """Get a MAC sweep configuration by name"""
    return MAC_PROTOCOL_SWEEP.get(name, MAC_PROTOCOL_SWEEP["quick"])


def run_mac_comparison(sweep_name: str = "quick", seeds: list = None, output_dir: str = "mac_comparison_results"):
    """Run MAC comparison sweep and generate plots"""
    if seeds is None:
        seeds = [2025]
    
    sweep = get_mac_sweep(sweep_name)
    
    print(f"Running MAC comparison sweep: {sweep_name}")
    print(f"Configuration: {sweep}")
    
    runner = AblationRunner(output_dir=output_dir)
    runner.run_sweep("custom", seeds=seeds, custom_sweep=sweep)
    csv_path = runner.save_results(f"mac_{sweep_name}_results.csv")
    
    if csv_path:
        plots_dir = os.path.join(output_dir, "plots")
        plot_mac_comparison(csv_path, plots_dir)
    
    return csv_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run MAC protocol comparison sweep")
    parser.add_argument(
        "--sweep", "-s",
        choices=list(MAC_PROTOCOL_SWEEP.keys()),
        default="quick",
        help="Sweep configuration to run"
    )
    parser.add_argument(
        "--seeds", "-n",
        type=int,
        nargs="+",
        default=[2025],
        help="Seeds for statistical validity"
    )
    parser.add_argument(
        "--output", "-o",
        default="mac_comparison_results",
        help="Output directory"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would run without executing"
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        sweep = get_mac_sweep(args.sweep)
        import itertools
        combinations = list(itertools.product(*sweep.values()))
        print(f"DRY RUN: {args.sweep}")
        print(f"  Parameters: {list(sweep.keys())}")
        print(f"  Total configurations: {len(combinations)}")
        print(f"  Total runs: {len(combinations) * len(args.seeds)}")
    else:
        run_mac_comparison(args.sweep, args.seeds, args.output)
