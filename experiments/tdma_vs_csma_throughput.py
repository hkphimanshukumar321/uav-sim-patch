"""
TDMA vs CSMA/CA Throughput Comparison Experiment

This experiment compares throughput performance of TDMA and CSMA/CA under:
- Ideal channel conditions (no fading, no obstruction, no collision losses from channel)
- IEEE 802.11b parameters
- Varying traffic rates
- Starting with n=2 drones, scalable

The goal is to reproduce the theoretical throughput vs traffic rate graph:
- CSMA: peaks then drops at high traffic (due to collisions/backoff overhead)
- TDMA: linear increase, then saturates (stable, no collisions)

Author: Experiment script for UAV Network Simulator
Created: 2026-02-05
"""

import sys
import os
import copy
import json
import csv
from collections import defaultdict
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import simpy
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for batch runs
import matplotlib.pyplot as plt

# Import config FIRST and disable plots/prints BEFORE importing other modules
from utils import config
config.ENABLE_PLOTS = False
config.ENABLE_TIME_PRINTS = False

# NOW import simulator components (after config is set)
from simulator.simulator import Simulator


# =============================================================================
# THROUGHPUT OBSERVER - Tracks all packet and ACK events
# =============================================================================

class ThroughputObserver:
    """
    Observer class that tracks detailed packet/ACK timing events for both
    TDMA and CSMA protocols.
    
    Records:
    - Packet creation time
    - Packet send time (when MAC layer starts transmission)
    - Packet receive time (when destination receives)
    - ACK send time
    - ACK receive time (when sender gets ACK)
    """
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all recorded events"""
        self.events = []  # List of event dicts
        self.packets_created = 0
        self.packets_sent = 0
        self.packets_received = 0
        self.acks_sent = 0
        self.acks_received = 0
        self.total_bits_received = 0
        self.start_time = None
        self.end_time = None
    
    def record_packet_created(self, time_us, packet_id, src_id, dst_id, packet_length):
        """Record when a data packet is created"""
        self.events.append({
            'type': 'PACKET_CREATED',
            'time_us': time_us,
            'packet_id': packet_id,
            'src_id': src_id,
            'dst_id': dst_id,
            'packet_length': packet_length
        })
        self.packets_created += 1
        if self.start_time is None:
            self.start_time = time_us
    
    def record_packet_sent(self, time_us, packet_id, src_id, dst_id):
        """Record when a packet is sent by MAC layer"""
        self.events.append({
            'type': 'PACKET_SENT',
            'time_us': time_us,
            'packet_id': packet_id,
            'src_id': src_id,
            'dst_id': dst_id
        })
        self.packets_sent += 1
    
    def record_packet_received(self, time_us, packet_id, src_id, dst_id, packet_length):
        """Record when a packet is received at destination"""
        self.events.append({
            'type': 'PACKET_RECEIVED',
            'time_us': time_us,
            'packet_id': packet_id,
            'src_id': src_id,
            'dst_id': dst_id,
            'packet_length': packet_length
        })
        self.packets_received += 1
        self.total_bits_received += packet_length
        self.end_time = time_us
    
    def record_ack_sent(self, time_us, packet_id, src_id, dst_id):
        """Record when an ACK is sent"""
        self.events.append({
            'type': 'ACK_SENT',
            'time_us': time_us,
            'packet_id': packet_id,
            'src_id': src_id,
            'dst_id': dst_id
        })
        self.acks_sent += 1
    
    def record_ack_received(self, time_us, packet_id, src_id, dst_id):
        """Record when an ACK is received by sender"""
        self.events.append({
            'type': 'ACK_RECEIVED',
            'time_us': time_us,
            'packet_id': packet_id,
            'src_id': src_id,
            'dst_id': dst_id
        })
        self.acks_received += 1
    
    def calculate_throughput(self, sim_time_us):
        """Calculate throughput in Kbps"""
        if sim_time_us <= 0:
            return 0.0
        # Throughput = total bits received / simulation time (seconds)
        throughput_bps = self.total_bits_received / (sim_time_us / 1e6)
        return throughput_bps / 1000  # Convert to Kbps
    
    def calculate_pdr(self):
        """Calculate Packet Delivery Ratio in %"""
        if self.packets_created == 0:
            return 0.0
        return (self.packets_received / self.packets_created) * 100
    
    def get_summary(self, sim_time_us):
        """Get summary statistics"""
        return {
            'packets_created': self.packets_created,
            'packets_sent': self.packets_sent,
            'packets_received': self.packets_received,
            'acks_sent': self.acks_sent,
            'acks_received': self.acks_received,
            'total_bits_received': self.total_bits_received,
            'throughput_kbps': self.calculate_throughput(sim_time_us),
            'pdr_percent': self.calculate_pdr()
        }
    
    def export_events_to_csv(self, filepath):
        """Export all events to CSV for detailed analysis"""
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['type', 'time_us', 'packet_id', 'src_id', 'dst_id', 'packet_length'])
            writer.writeheader()
            for event in self.events:
                row = {k: event.get(k, '') for k in ['type', 'time_us', 'packet_id', 'src_id', 'dst_id', 'packet_length']}
                writer.writerow(row)


# Global observer instance
observer = ThroughputObserver()


# =============================================================================
# MONKEY PATCHING - Hook into simulation events without modifying core files
# =============================================================================

def patch_simulator_for_observation():
    """
    Monkey-patch the Drone class methods to record events for the observer.
    This allows us to track packet/ACK timing without modifying core files.
    """
    from entities.drone import Drone
    from entities.packet import DataPacket
    from routing.dsdv.dsdv import Dsdv
    
    # Store original methods
    original_generate_data_packet = Drone.generate_data_packet
    original_receive = Drone.receive
    
    # Patch generate_data_packet to record packet creation
    def patched_generate_data_packet(self, traffic_pattern=None):
        """Patched version that records packet creation events"""
        while True:
            if not self.sleep:
                if traffic_pattern is None:
                    traffic_pattern = getattr(config, 'TRAFFIC_PATTERN', 'Poisson')

                if traffic_pattern == 'Uniform':
                    lo, hi = getattr(config, 'UNIFORM_IAT_US', (500000, 505000))
                    yield self.env.timeout(self.rng_drone.randint(int(lo), int(hi)))
                elif traffic_pattern == 'Poisson':
                    rate = float(getattr(config, 'TRAFFIC_RATE', 10))
                    iat_us = self.rng_drone.expovariate(rate) * 1e6
                    yield self.env.timeout(int(round(iat_us)))

                config.GL_ID_DATA_PACKET += 1

                all_candidate_list = [i for i in range(config.NUMBER_OF_DRONES)]
                all_candidate_list.remove(self.identifier)
                dst_id = self.rng_drone.choice(all_candidate_list)
                destination = self.simulator.drones[dst_id]

                variable_payload = getattr(config, 'VARIABLE_PAYLOAD_LENGTH', False)
                avg_payload = getattr(config, 'AVERAGE_PAYLOAD_LENGTH', 8192)
                max_variation = getattr(config, 'MAXIMUM_PAYLOAD_VARIATION', 1024)
                
                if variable_payload:
                    fluctuation = self.rng_drone.randint(-max_variation, max_variation)
                    payload_length = avg_payload + fluctuation
                else:
                    payload_length = avg_payload

                ip_header = getattr(config, 'IP_HEADER_LENGTH', 160)
                mac_header = getattr(config, 'MAC_HEADER_LENGTH', 272)
                phy_header = getattr(config, 'PHY_HEADER_LENGTH', 128)
                
                data_packet_length = ip_header + mac_header + phy_header + payload_length

                channel_id = self.channel_assigner.channel_assign()

                pkd = DataPacket(self,
                                 dst_drone=destination,
                                 creation_time=self.env.now,
                                 data_packet_id=config.GL_ID_DATA_PACKET,
                                 data_packet_length=data_packet_length,
                                 simulator=self.simulator,
                                 channel_id=channel_id)
                pkd.transmission_mode = 0

                self.simulator.metrics.datapacket_generated_num += 1

                # === OBSERVER HOOK: Record packet creation ===
                observer.record_packet_created(
                    time_us=self.env.now,
                    packet_id=pkd.packet_id,
                    src_id=self.identifier,
                    dst_id=destination.identifier,
                    packet_length=data_packet_length
                )

                pkd.waiting_start_time = self.env.now

                if self.transmitting_queue.qsize() < self.max_queue_size:
                    self.transmitting_queue.put(pkd)
            else:
                break
    
    # Apply patches
    Drone.generate_data_packet = patched_generate_data_packet
    
    # Patch the Metrics class to record packet reception
    from simulator.metrics import Metrics
    original_calculate_metrics = Metrics.calculate_metrics
    
    def patched_calculate_metrics(self, received_packet):
        """Patched version that records packet reception events"""
        # Call original
        original_calculate_metrics(self, received_packet)
        
        # === OBSERVER HOOK: Record packet reception ===
        observer.record_packet_received(
            time_us=self.simulator.env.now,
            packet_id=received_packet.packet_id,
            src_id=getattr(received_packet, 'src_drone', None),
            dst_id=getattr(received_packet, 'dst_drone', None),
            packet_length=received_packet.packet_length
        )
    
    Metrics.calculate_metrics = patched_calculate_metrics


# =============================================================================
# EXPERIMENT CONFIGURATION
# =============================================================================

def configure_ideal_channel():
    """
    Configure the channel to be 'ideal':
    - No fading (path loss exponent = 0 means no distance decay)
    - Very low SNR threshold (all packets received successfully)
    - No obstruction effects
    """
    # Set very low SNR threshold so all packets pass
    config.SNR_THRESHOLD = -200  # dB, effectively no threshold
    
    # Disable variable payload for consistency
    config.VARIABLE_PAYLOAD_LENGTH = 0
    
    # Use standard IEEE 802.11b parameters (already set from config)
    # config.BIT_RATE is already 2 Mbps from 802.11b
    
    # Disable plots and time prints for batch runs
    config.ENABLE_PLOTS = False
    config.ENABLE_TIME_PRINTS = False
    
    # Disable dynamic TDMA for fair comparison
    config.TDMA_ENABLE_DYNAMIC = False


def run_single_experiment(mac_mode, traffic_rate, n_drones, sim_time_s, seed=2025):
    """
    Run a single experiment with specified parameters.
    
    Args:
        mac_mode: 'TDMA' or 'CSMA'
        traffic_rate: packets/sec per drone
        n_drones: number of drones
        sim_time_s: simulation time in seconds
        seed: random seed
    
    Returns:
        dict: Experiment results including throughput, PDR, etc.
    """
    # Reset observer
    observer.reset()
    
    # Configure experiment parameters
    config.MAC_MODE = mac_mode
    config.TRAFFIC_RATE = traffic_rate
    config.NUMBER_OF_DRONES = n_drones
    config.SIM_TIME = sim_time_s * 1e6  # Convert to microseconds
    config.MAX_TTL = n_drones + 1
    
    # Reset global packet counter
    config.GL_ID_DATA_PACKET = 0
    
    # Apply ideal channel configuration
    configure_ideal_channel()
    
    # Create SimPy environment
    env = simpy.Environment()
    
    # Create channel states (one resource per drone for channel access)
    channel_states = {}
    for i in range(n_drones):
        channel_states[i] = simpy.Resource(env, capacity=1)
    
    # Patch simulator for observation (only once)
    patch_simulator_for_observation()
    
    # Create and run simulator
    simulator = Simulator(seed=seed, env=env, channel_states=channel_states, n_drones=n_drones)
    env.run(until=config.SIM_TIME)
    
    # Get results from simulator metrics
    sim_metrics = simulator.metrics.to_dict()
    
    # Get observer summary
    obs_summary = observer.get_summary(config.SIM_TIME)
    
    return {
        'mac_mode': mac_mode,
        'traffic_rate': traffic_rate,
        'n_drones': n_drones,
        'sim_time_s': sim_time_s,
        'seed': seed,
        'throughput_kbps': sim_metrics['throughput_kbps'],
        'pdr_percent': sim_metrics['pdr_percent'],
        'e2e_delay_ms': sim_metrics['e2e_delay_ms'],
        'collisions': sim_metrics['collisions'],
        'packets_sent': sim_metrics['sent'],
        'packets_arrived': sim_metrics['arrived'],
        'observer_packets_created': obs_summary['packets_created'],
        'observer_packets_received': obs_summary['packets_received'],
        'observer_throughput_kbps': obs_summary['throughput_kbps']
    }


# =============================================================================
# MAIN EXPERIMENT SWEEP
# =============================================================================

def run_throughput_experiment(
    n_drones=2,
    traffic_rates=None,
    sim_time_s=30,
    seeds=None,
    output_dir='results'
):
    """
    Run the full TDMA vs CSMA throughput comparison experiment.
    
    Args:
        n_drones: Number of drones in the network
        traffic_rates: List of traffic rates to test (packets/sec per drone)
        sim_time_s: Simulation time in seconds
        seeds: List of random seeds for statistical significance
        output_dir: Directory to save results
    
    Returns:
        dict: All experiment results
    """
    if traffic_rates is None:
        # Start low, scale up
        traffic_rates = [5, 10, 20, 50, 100, 150, 200, 300, 400, 500]
    
    if seeds is None:
        seeds = [2025]  # Single seed for initial test
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    results = {
        'TDMA': defaultdict(list),
        'CSMA': defaultdict(list)
    }
    
    total_runs = len(traffic_rates) * len(seeds) * 2  # 2 MAC modes
    run_count = 0
    
    print(f"\n{'='*60}")
    print(f"TDMA vs CSMA Throughput Experiment")
    print(f"Drones: {n_drones}, Traffic Rates: {traffic_rates}")
    print(f"Simulation Time: {sim_time_s}s, Seeds: {seeds}")
    print(f"{'='*60}\n")
    
    for mac_mode in ['TDMA', 'CSMA']:
        print(f"\n--- Running {mac_mode} experiments ---")
        
        for traffic_rate in traffic_rates:
            throughputs = []
            pdrs = []
            
            for seed in seeds:
                run_count += 1
                print(f"  [{run_count}/{total_runs}] {mac_mode}, TR={traffic_rate}, seed={seed}...", end='', flush=True)
                
                try:
                    result = run_single_experiment(
                        mac_mode=mac_mode,
                        traffic_rate=traffic_rate,
                        n_drones=n_drones,
                        sim_time_s=sim_time_s,
                        seed=seed
                    )
                    
                    throughputs.append(result['throughput_kbps'])
                    pdrs.append(result['pdr_percent'])
                    
                    print(f" Throughput={result['throughput_kbps']:.2f} Kbps, PDR={result['pdr_percent']:.1f}%")
                    
                except Exception as e:
                    print(f" ERROR: {e}")
                    throughputs.append(0)
                    pdrs.append(0)
            
            # Average across seeds
            results[mac_mode]['traffic_rate'].append(traffic_rate)
            results[mac_mode]['throughput_kbps'].append(np.mean(throughputs))
            results[mac_mode]['throughput_std'].append(np.std(throughputs))
            results[mac_mode]['pdr_percent'].append(np.mean(pdrs))
    
    return results


def plot_throughput_comparison(results, output_path='results/tdma_vs_csma_throughput.png'):
    """
    Generate the throughput vs traffic rate comparison plot.
    """
    plt.figure(figsize=(10, 6))
    
    # Plot TDMA
    plt.plot(
        results['TDMA']['traffic_rate'],
        results['TDMA']['throughput_kbps'],
        'b-o', linewidth=2, markersize=8, label='TDMA'
    )
    
    # Plot CSMA
    plt.plot(
        results['CSMA']['traffic_rate'],
        results['CSMA']['throughput_kbps'],
        'r-s', linewidth=2, markersize=8, label='CSMA/CA'
    )
    
    plt.xlabel('Traffic Rate (packets/sec per drone)', fontsize=12)
    plt.ylabel('Throughput (Kbps)', fontsize=12)
    plt.title('TDMA vs CSMA/CA Throughput Comparison\n(Ideal Channel, 2 Drones)', fontsize=14)
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    print(f"\nPlot saved to: {output_path}")


def save_results_to_csv(results, output_path='results/tdma_vs_csma_data.csv'):
    """Save experiment results to CSV"""
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['MAC_Mode', 'Traffic_Rate', 'Throughput_Kbps', 'Throughput_Std', 'PDR_Percent'])
        
        for mac_mode in ['TDMA', 'CSMA']:
            for i, tr in enumerate(results[mac_mode]['traffic_rate']):
                writer.writerow([
                    mac_mode,
                    tr,
                    results[mac_mode]['throughput_kbps'][i],
                    results[mac_mode]['throughput_std'][i],
                    results[mac_mode]['pdr_percent'][i]
                ])
    
    print(f"Data saved to: {output_path}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("TDMA vs CSMA/CA Throughput Comparison Experiment")
    print("="*60)
    
    # Experiment parameters - REDUCED FOR FASTER TESTING
    N_DRONES = 2  # Start with 2 drones as specified
    TRAFFIC_RATES = [5, 20, 50, 100]  # Fewer rates for quick test
    SIM_TIME_S = 5  # 5 seconds simulation (reduced from 30)
    SEEDS = [2025]  # Single seed for quick test
    
    # Run experiment
    results = run_throughput_experiment(
        n_drones=N_DRONES,
        traffic_rates=TRAFFIC_RATES,
        sim_time_s=SIM_TIME_S,
        seeds=SEEDS
    )
    
    # Generate outputs
    plot_throughput_comparison(results)
    save_results_to_csv(results)
    
    print("\n" + "="*60)
    print("Experiment Complete!")
    print("="*60)
