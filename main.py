import simpy
import argparse
from utils import config
from simulator.simulator import Simulator
from visualization.visualizer import SimulationVisualizer

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
    
    args = parser.parse_args()
    
    if args.seeds:
        # Multiple seeds mode (batch)
        print(f"Running batch with seeds: {args.seeds}")
        for seed in args.seeds:
            run_simulation(seed, enable_visualizer=False)
    else:
        # Single seed mode
        run_simulation(args.seed, enable_visualizer=not args.no_vis)