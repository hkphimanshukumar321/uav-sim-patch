import simpy
import argparse
import time
from utils import config
from simulator.simulator import Simulator
from visualization.visualizer import SimulationVisualizer
from utils.multiprocessing_utils import (
    ParallelRunner, print_cpu_info, print_performance_summary, get_cpu_info
)

"""
  _   _                   _   _          _     ____    _             
 | | | |   __ _  __   __ | \ | |   ___  | |_  / ___|  (_)  _ __ ___  
 | | | |  / _` | \ \ / / |  \| |  / _ \ | __| \___ \  | | | '_ ` _ \ 
 | |_| | | (_| |  \ V /  | |\  | |  __/ | |_   ___) | | | | | | | | |
  \___/   \__,_|   \_/   |_| \_|  \___|  \__| |____/  |_| |_| |_| |_|
                                                                                                                                                                                                                                                                                           
"""

def run_simulation(seed: int, enable_visualizer: bool = True):
    """Run simulation with specified seed"""
    print(f"\n{'='*60}")
    print(f"Running simulation with SEED = {seed}")
    print(f"{'='*60}\n")
    
    # Simulation setup
    env = simpy.Environment()
    channel_states = {i: simpy.Resource(env, capacity=1) for i in range(config.NUMBER_OF_DRONES)}
    sim = Simulator(seed=seed, env=env, channel_states=channel_states, n_drones=config.NUMBER_OF_DRONES)
    
    if enable_visualizer:
        # Add the visualizer to the simulator
        # Use 20000 microseconds (0.02s) as the visualization frame interval
        visualizer = SimulationVisualizer(sim, output_dir=".", vis_frame_interval=20000)
        visualizer.run_visualization()
    
    # Run simulation
    env.run(until=config.SIM_TIME)
    
    if enable_visualizer:
        # Finalize visualization
        visualizer.finalize()
    
    return sim


def run_simulation_worker(seed: int):
    """
    Worker function for parallel execution.
    
    Creates a fresh simulation instance (required for multiprocessing).
    Returns (seed, metrics_dict, elapsed_time).
    """
    start_time = time.time()
    
    # Disable plots and prints in worker
    config.ENABLE_PLOTS = False
    config.ENABLE_TIME_PRINTS = False
    
    # Create fresh simulation
    env = simpy.Environment()
    channel_states = {i: simpy.Resource(env, capacity=1) for i in range(config.NUMBER_OF_DRONES)}
    sim = Simulator(seed=seed, env=env, channel_states=channel_states, n_drones=config.NUMBER_OF_DRONES)
    
    # Run simulation
    env.run(until=config.SIM_TIME)
    
    elapsed_time = time.time() - start_time
    
    # Get metrics
    metrics = sim.metrics.to_dict() if hasattr(sim.metrics, 'to_dict') else {}
    metrics['seed'] = seed
    metrics['inference_time_s'] = elapsed_time
    
    print(f"  [OK] Seed {seed} completed in {elapsed_time:.2f}s")
    
    return seed, metrics, elapsed_time


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="UAV Network Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                     # Run with default seed (2025)
  python main.py --seed 2026         # Run with specific seed
  python main.py --seed 9999 --no-vis # Run without visualizer
  python main.py --seeds 2025 2026 2027 --no-vis  # Multiple seeds (batch)
  python main.py --seeds 2025 2026 2027 2028 --no-vis --workers 4  # Parallel batch
        """
    )
    
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=2025,
        help="Random seed for reproducibility (default: 2025)"
    )
    
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        help="Multiple seeds for batch runs (disables visualizer)"
    )
    
    parser.add_argument(
        "--no-vis",
        action="store_true",
        help="Disable visualizer (for batch runs)"
    )
    
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=None,
        help="Number of parallel workers for batch runs (default: auto-detect)"
    )
    
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Force sequential execution even with multiple seeds"
    )
    
    args = parser.parse_args()
    
    if args.seeds:
        # Multiple seeds mode (batch)
        print(f"\n{'='*60}")
        print(f"UAV Network Simulator - Batch Mode")
        print(f"{'='*60}")
        print(f"Seeds: {args.seeds}")
        
        if args.sequential or len(args.seeds) == 1:
            # Sequential execution
            print_cpu_info(workers_used=1)
            print("Running in sequential mode...")
            
            start_time = time.time()
            individual_times = []
            
            for seed in args.seeds:
                seed_start = time.time()
                run_simulation(seed, enable_visualizer=False)
                individual_times.append(time.time() - seed_start)
            
            total_time = time.time() - start_time
            print_performance_summary(
                total_runs=len(args.seeds),
                total_time=total_time,
                workers_used=1,
                individual_times=individual_times
            )
        else:
            # Parallel execution
            with ParallelRunner(n_workers=args.workers, show_progress=False) as runner:
                print(f"Running {len(args.seeds)} simulations in parallel...")
                
                # Prepare arguments for parallel execution
                args_list = [(seed,) for seed in args.seeds]
                
                start_time = time.time()
                results = runner.pool.starmap(run_simulation_worker, args_list)
                total_time = time.time() - start_time
                
                # Extract timing info
                individual_times = [r[2] for r in results]
                
                print_performance_summary(
                    total_runs=len(args.seeds),
                    total_time=total_time,
                    workers_used=runner.n_workers,
                    individual_times=individual_times
                )
                
                # Print results summary
                print("\nResults Summary:")
                print("-" * 60)
                for seed, metrics, elapsed in results:
                    pdr = metrics.get('pdr_percent', 'N/A')
                    delay = metrics.get('e2e_delay_ms', 'N/A')
                    if isinstance(pdr, float):
                        pdr = f"{pdr:.2f}%"
                    if isinstance(delay, float):
                        delay = f"{delay:.2f}ms"
                    print(f"  Seed {seed}: PDR={pdr}, Delay={delay}, Time={elapsed:.2f}s")
    else:
        # Single seed mode
        print_cpu_info(workers_used=1)
        start_time = time.time()
        run_simulation(args.seed, enable_visualizer=not args.no_vis)
        elapsed = time.time() - start_time
        print(f"\nInference Time: {elapsed:.2f}s")