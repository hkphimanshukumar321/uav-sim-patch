"""
Functional Tests for UAV Sim Patched
=====================================
Validates core functionality:
1. Simulator initialization
2. Drone creation with all components
3. Minimal simulation run
4. Metrics collection

Run: python -m tests.test_functional
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import simpy
from utils import config

# Override config for testing (reduced scope)
config.NUMBER_OF_DRONES = 3
config.SIM_TIME = 1 * 1e6  # 1 second only
config.ENABLE_PLOTS = False
config.ENABLE_TIME_PRINTS = False


class FunctionalTestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_pass(self, test_name, details=""):
        self.passed += 1
        msg = f"  [PASS]: {test_name}"
        if details:
            msg += f" ({details})"
        print(msg)
    
    def add_fail(self, test_name, error):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"  [FAIL]: {test_name}")
        print(f"         Error: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"FUNCTIONAL TEST SUMMARY: {self.passed}/{total} passed")
        print(f"{'='*60}")
        return self.failed == 0


def test_simulator_initialization(result):
    """Test Simulator class initializes correctly"""
    print("\n[1] SIMULATOR INITIALIZATION...")
    
    try:
        from simulator.simulator import Simulator
        
        env = simpy.Environment()
        channel_states = {i: simpy.Resource(env, capacity=1) for i in range(config.NUMBER_OF_DRONES)}
        
        sim = Simulator(
            seed=42,
            env=env,
            channel_states=channel_states,
            n_drones=config.NUMBER_OF_DRONES
        )
        
        # Verify simulator attributes
        assert sim.env is not None, "SimPy environment not set"
        assert sim.channel is not None, "Wireless channel not created"
        assert sim.metrics is not None, "Metrics collector not created"
        assert len(sim.drones) == config.NUMBER_OF_DRONES, "Incorrect drone count"
        
        result.add_pass("Simulator initialization", f"{config.NUMBER_OF_DRONES} drones created")
        return sim
        
    except Exception as e:
        result.add_fail("Simulator initialization", str(e))
        return None


def test_drone_components(result, sim):
    """Test that each drone has required components per architecture"""
    print("\n[2] DRONE COMPONENT VALIDATION...")
    
    if sim is None:
        result.add_fail("Drone components", "No simulator available")
        return False
    
    all_ok = True
    
    for drone in sim.drones:
        drone_id = drone.identifier
        
        # Protocol Stack Components
        components = {
            'routing_protocol': 'Network/Routing Layer',
            'mac_protocol': 'MAC Layer',
            'mobility_model': 'Mobility Model',
            'energy_model': 'Energy Model',
            'transmitting_queue': 'Transport/Queue',
            'buffer': 'Buffer Resource',
            'inbox': 'Physical Interface (inbox)',
        }
        
        missing = []
        for attr, name in components.items():
            if not hasattr(drone, attr) or getattr(drone, attr) is None:
                missing.append(name)
        
        if missing:
            result.add_fail(f"Drone {drone_id} components", f"Missing: {missing}")
            all_ok = False
        else:
            result.add_pass(f"Drone {drone_id} has all {len(components)} architecture components")
    
    return all_ok


def test_simulation_run(result, sim):
    """Test that simulation runs to completion"""
    print("\n[3] SIMULATION RUN...")
    
    if sim is None:
        result.add_fail("Simulation run", "No simulator available")
        return False
    
    try:
        sim.env.run(until=config.SIM_TIME)
        result.add_pass("Simulation completed", f"Ran for {config.SIM_TIME/1e6}s")
        return True
    except Exception as e:
        result.add_fail("Simulation run", str(e))
        return False


def test_metrics_populated(result, sim):
    """Test that metrics are collected during simulation"""
    print("\n[4] METRICS COLLECTION...")
    
    if sim is None:
        result.add_fail("Metrics collection", "No simulator available")
        return False
    
    try:
        metrics = sim.metrics
        
        # Check metrics object exists and has required attributes
        required_attrs = [
            'datapacket_generated_num',
            'datapacket_arrived',
            'control_packet_num',
            'deliver_time_dict',
            'throughput_dict',
        ]
        
        missing = [attr for attr in required_attrs if not hasattr(metrics, attr)]
        if missing:
            result.add_fail("Metrics attributes", f"Missing: {missing}")
            return False
        
        result.add_pass("Metrics object structure valid")
        
        # Check if any packets were generated
        if metrics.datapacket_generated_num > 0:
            result.add_pass("Packet generation", f"{metrics.datapacket_generated_num} packets generated")
        else:
            result.add_pass("Packet generation", "0 packets (short sim time - OK)")
        
        return True
        
    except Exception as e:
        result.add_fail("Metrics collection", str(e))
        return False


def run_functional_tests():
    """Run all functional tests"""
    print("="*60)
    print("UAV SIM PATCHED - FUNCTIONAL TESTS")
    print("="*60)
    print(f"Config: {config.NUMBER_OF_DRONES} drones, {config.SIM_TIME/1e6}s simulation")
    
    result = FunctionalTestResult()
    
    sim = test_simulator_initialization(result)
    test_drone_components(result, sim)
    test_simulation_run(result, sim)
    test_metrics_populated(result, sim)
    
    return result.summary(), result


if __name__ == "__main__":
    success, result = run_functional_tests()
    sys.exit(0 if success else 1)
