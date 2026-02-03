"""
Ablation Plotting Utilities

Generate plots similar to research figures showing:
- Throughput vs Delay (for different MAC protocols)
- Throughput vs Traffic Rate (load)
- Contention level comparison

Usage:
    from ablation.plot_results import plot_mac_comparison
    plot_mac_comparison("ablation_results/sweep_results.csv", output_dir="plots/")
"""

import os
import csv
import glob
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Optional


def find_latest_results(results_dir: str = "results") -> Optional[str]:
    """
    Find the most recent results CSV file in the results directory.
    
    Looks for:
    1. Latest run_YYYYMMDD_HHMMSS/results.csv in run directories
    2. Latest ablation_YYYYMMDD_HHMMSS.csv files (legacy format)
    
    Returns:
        Path to the latest results CSV file, or None if not found
    """
    if not os.path.exists(results_dir):
        print(f"Results directory not found: {results_dir}")
        return None
    
    # Look for run directories first (new format)
    run_dirs = glob.glob(os.path.join(results_dir, "run_*"))
    run_csvs = []
    for run_dir in run_dirs:
        csv_path = os.path.join(run_dir, "results.csv")
        if os.path.exists(csv_path):
            run_csvs.append(csv_path)
    
    # Look for legacy format CSV files
    legacy_csvs = glob.glob(os.path.join(results_dir, "ablation_*.csv"))
    
    # Combine all CSVs and sort by modification time
    all_csvs = run_csvs + legacy_csvs
    
    if not all_csvs:
        print(f"No results CSV files found in {results_dir}")
        return None
    
    # Sort by modification time (newest first)
    all_csvs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    latest = all_csvs[0]
    print(f"Auto-discovered latest results: {latest}")
    return latest


def load_results(csv_path: str = None) -> List[Dict]:
    """
    Load results from CSV file.
    
    If csv_path is None, auto-discovers the latest results file.
    """
    if csv_path is None:
        csv_path = find_latest_results()
        if csv_path is None:
            return []
    
    results = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric fields
            numeric_fields = ['throughput_kbps', 'e2e_delay_ms', 'pdr_percent', 
                            'collisions', 'mac_delay_ms', 'hop_count', 
                            'sent', 'arrived', 'routing_load', 'rate', 'seed']
            for field in numeric_fields:
                if field in row and row[field]:
                    try:
                        row[field] = float(row[field])
                    except ValueError:
                        pass
            results.append(row)
    return results


def plot_throughput_vs_delay(
    results: List[Dict], 
    output_path: str = "throughput_vs_delay.png",
    title: str = "Throughput vs Delay by MAC Protocol"
):
    """
    Plot throughput (x-axis) vs delay (y-axis) for each MAC protocol.
    Similar to the reference figure provided by user.
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Group by MAC mode
    mac_data = {}
    for row in results:
        mac = row.get('mac_mode', row.get('MAC_MODE', 'Unknown'))
        if mac not in mac_data:
            mac_data[mac] = {'throughput': [], 'delay': []}
        
        throughput = row.get('throughput_kbps', 0)
        delay = row.get('e2e_delay_ms', 0)
        
        if isinstance(throughput, (int, float)) and isinstance(delay, (int, float)):
            mac_data[mac]['throughput'].append(throughput)
            mac_data[mac]['delay'].append(delay)
    
    # Color and marker mapping
    styles = {
        'TDMA': {'color': 'red', 'marker': '^', 'linestyle': '-'},
        'CSMA': {'color': 'blue', 'marker': 'o', 'linestyle': '-'},
        'ALOHA': {'color': 'green', 'marker': 'x', 'linestyle': '-'},
        'ADAPTIVE': {'color': 'purple', 'marker': 's', 'linestyle': '--'},
    }
    
    for mac, data in mac_data.items():
        if data['throughput'] and data['delay']:
            style = styles.get(mac, {'color': 'gray', 'marker': 'o', 'linestyle': '-'})
            
            # Sort by throughput for proper line connection
            sorted_pairs = sorted(zip(data['throughput'], data['delay']))
            throughput_sorted = [p[0] for p in sorted_pairs]
            delay_sorted = [p[1] for p in sorted_pairs]
            
            ax.plot(throughput_sorted, delay_sorted, 
                   marker=style['marker'], color=style['color'], 
                   linestyle=style['linestyle'], linewidth=2,
                   markersize=8, label=mac)
    
    ax.set_xlabel('Throughput (Kbps)', fontsize=12)
    ax.set_ylabel('End-to-End Delay (ms)', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")


def plot_throughput_vs_rate(
    results: List[Dict],
    output_path: str = "throughput_vs_rate.png",
    title: str = "Throughput vs Traffic Rate by MAC Protocol"
):
    """
    Plot throughput vs traffic rate (load) for each MAC protocol.
    Shows how different MACs handle increasing load.
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Group by MAC mode
    mac_data = {}
    for row in results:
        mac = row.get('mac_mode', row.get('MAC_MODE', 'Unknown'))
        if mac not in mac_data:
            mac_data[mac] = {'rate': [], 'throughput': []}
        
        rate = row.get('rate', row.get('TRAFFIC_RATE', 0))
        throughput = row.get('throughput_kbps', 0)
        
        if isinstance(rate, (int, float)) and isinstance(throughput, (int, float)):
            mac_data[mac]['rate'].append(rate)
            mac_data[mac]['throughput'].append(throughput)
    
    styles = {
        'TDMA': {'color': 'red', 'marker': '^'},
        'CSMA': {'color': 'blue', 'marker': 'o'},
        'ALOHA': {'color': 'green', 'marker': 'x'},
        'ADAPTIVE': {'color': 'purple', 'marker': 's'},
    }
    
    for mac, data in mac_data.items():
        if data['rate'] and data['throughput']:
            style = styles.get(mac, {'color': 'gray', 'marker': 'o'})
            
            # Average by rate (in case of multiple seeds)
            rate_avg = {}
            for r, t in zip(data['rate'], data['throughput']):
                if r not in rate_avg:
                    rate_avg[r] = []
                rate_avg[r].append(t)
            
            rates = sorted(rate_avg.keys())
            throughputs = [np.mean(rate_avg[r]) for r in rates]
            
            ax.plot(rates, throughputs, 
                   marker=style['marker'], color=style['color'],
                   linewidth=2, markersize=8, label=mac)
    
    ax.set_xlabel('Traffic Rate (packets/sec/drone)', fontsize=12)
    ax.set_ylabel('Throughput (Kbps)', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")


def plot_pdr_vs_rate(
    results: List[Dict],
    output_path: str = "pdr_vs_rate.png",
    title: str = "Packet Delivery Ratio vs Traffic Rate"
):
    """
    Plot PDR vs traffic rate for each MAC protocol.
    Shows reliability under increasing load.
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    
    mac_data = {}
    for row in results:
        mac = row.get('mac_mode', row.get('MAC_MODE', 'Unknown'))
        if mac not in mac_data:
            mac_data[mac] = {'rate': [], 'pdr': []}
        
        rate = row.get('rate', row.get('TRAFFIC_RATE', 0))
        pdr = row.get('pdr_percent', 0)
        
        if isinstance(rate, (int, float)) and isinstance(pdr, (int, float)):
            mac_data[mac]['rate'].append(rate)
            mac_data[mac]['pdr'].append(pdr)
    
    styles = {
        'TDMA': {'color': 'red', 'marker': '^'},
        'CSMA': {'color': 'blue', 'marker': 'o'},
        'ALOHA': {'color': 'green', 'marker': 'x'},
        'ADAPTIVE': {'color': 'purple', 'marker': 's'},
    }
    
    for mac, data in mac_data.items():
        if data['rate'] and data['pdr']:
            style = styles.get(mac, {'color': 'gray', 'marker': 'o'})
            
            rate_avg = {}
            for r, p in zip(data['rate'], data['pdr']):
                if r not in rate_avg:
                    rate_avg[r] = []
                rate_avg[r].append(p)
            
            rates = sorted(rate_avg.keys())
            pdrs = [np.mean(rate_avg[r]) for r in rates]
            
            ax.plot(rates, pdrs,
                   marker=style['marker'], color=style['color'],
                   linewidth=2, markersize=8, label=mac)
    
    ax.set_xlabel('Traffic Rate (packets/sec/drone)', fontsize=12)
    ax.set_ylabel('Packet Delivery Ratio (%)', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 105)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")


def plot_collisions_vs_rate(
    results: List[Dict],
    output_path: str = "collisions_vs_rate.png",
    title: str = "Collisions vs Traffic Rate"
):
    """
    Plot collision count vs traffic rate.
    Shows contention behavior under load.
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    
    mac_data = {}
    for row in results:
        mac = row.get('mac_mode', row.get('MAC_MODE', 'Unknown'))
        if mac not in mac_data:
            mac_data[mac] = {'rate': [], 'collisions': []}
        
        rate = row.get('rate', row.get('TRAFFIC_RATE', 0))
        collisions = row.get('collisions', 0)
        
        if isinstance(rate, (int, float)) and isinstance(collisions, (int, float)):
            mac_data[mac]['rate'].append(rate)
            mac_data[mac]['collisions'].append(collisions)
    
    styles = {
        'TDMA': {'color': 'red', 'marker': '^'},
        'CSMA': {'color': 'blue', 'marker': 'o'},
        'ALOHA': {'color': 'green', 'marker': 'x'},
        'ADAPTIVE': {'color': 'purple', 'marker': 's'},
    }
    
    for mac, data in mac_data.items():
        if data['rate'] and data['collisions']:
            style = styles.get(mac, {'color': 'gray', 'marker': 'o'})
            
            rate_avg = {}
            for r, c in zip(data['rate'], data['collisions']):
                if r not in rate_avg:
                    rate_avg[r] = []
                rate_avg[r].append(c)
            
            rates = sorted(rate_avg.keys())
            colls = [np.mean(rate_avg[r]) for r in rates]
            
            ax.plot(rates, colls,
                   marker=style['marker'], color=style['color'],
                   linewidth=2, markersize=8, label=mac)
    
    ax.set_xlabel('Traffic Rate (packets/sec/drone)', fontsize=12)
    ax.set_ylabel('Number of Collisions', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")


def plot_mac_comparison(csv_path: str, output_dir: str = "plots"):
    """
    Generate all comparison plots from a results CSV file.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    results = load_results(csv_path)
    
    if not results:
        print(f"No results found in {csv_path}")
        return
    
    print(f"Loaded {len(results)} results from {csv_path}")
    
    # Generate all plots
    plot_throughput_vs_delay(results, os.path.join(output_dir, "throughput_vs_delay.png"))
    plot_throughput_vs_rate(results, os.path.join(output_dir, "throughput_vs_rate.png"))
    plot_pdr_vs_rate(results, os.path.join(output_dir, "pdr_vs_rate.png"))
    plot_collisions_vs_rate(results, os.path.join(output_dir, "collisions_vs_rate.png"))
    
    print(f"\nAll plots saved to {output_dir}/")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate ablation study plots")
    parser.add_argument("csv_path", nargs='?', default=None, 
                       help="Path to results CSV file (optional, auto-discovers latest if not provided)")
    parser.add_argument("--output", "-o", default="plots", help="Output directory")
    parser.add_argument("--results-dir", "-r", default="results", 
                       help="Directory to search for results (when csv_path not provided)")
    args = parser.parse_args()
    
    # Auto-discover CSV if not provided
    csv_path = args.csv_path
    if csv_path is None:
        csv_path = find_latest_results(args.results_dir)
        if csv_path is None:
            print("Error: No results file found and none specified")
            exit(1)
    
    plot_mac_comparison(csv_path, args.output)

