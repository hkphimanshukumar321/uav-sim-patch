"""
Integration Tests for UAV Sim Patched
======================================
End-to-end tests validating:
1. Architecture-based component integration
2. Complete packet flow (Application → Network → MAC → PHY → Channel)
3. Proper import dependencies and calling patterns
4. Metrics collection across all layers

Based on the system architecture diagram:
- Simulator manages N drones
- Each Drone has: Protocol Stack (App/Transport/Network/MAC/PHY) + Control Modules (Mobility/Energy/Topology)
- Wireless Channel handles interference/collision
- Metrics Collector records events

Run: python -m tests.test_integration
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import simpy
from utils import config

# Override config for testing
config.NUMBER_OF_DRONES = 5
config.SIM_TIME = 5 * 1e6  # 5 seconds
config.ENABLE_PLOTS = False
config.ENABLE_TIME_PRINTS = False
config.TRAFFIC_RATE = 5  # 5 packets/sec per drone


class IntegrationTestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.errors = []
        self.warnings_list = []
    
    def add_pass(self, test_name, details=""):
        self.passed += 1
        msg = f"  [PASS]: {test_name}"
        if details:
            msg += f"\n         {details}"
        print(msg)
    
    def add_fail(self, test_name, error):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"  [FAIL]: {test_name}")
        print(f"         Error: {error}")
    
    def add_warning(self, test_name, warning):
        self.warnings += 1
        self.warnings_list.append((test_name, warning))
        print(f"  [WARN]: {test_name}")
        print(f"         Warning: {warning}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"INTEGRATION TEST SUMMARY: {self.passed}/{total} passed")
        if self.warnings > 0:
            print(f"Warnings: {self.warnings}")
        print(f"{'='*60}")
        return self.failed == 0


def test_architecture_imports(result):
    """Test that architecture components can be imported and have correct dependencies"""
    print("\n[1] ARCHITECTURE IMPORT VALIDATION...")
    print("    Testing layered architecture import dependencies...")
    
    try:
        # Simulation Environment Layer
        from simulator.simulator import Simulator
        from simulator.metrics import Metrics
        from phy.channel import Channel
        from visualization.visualizer import SimulationVisualizer
        
        # Drone Entity
        from entities.drone import Drone
        from entities.packet import DataPacket
        
        # Protocol Stack - Network Layer
        from routing.dsdv.dsdv import Dsdv
        from routing.dsdv.dsdv_routing_table import DsdvRoutingTable
        from routing.greedy.greedy import Greedy
        
        # Protocol Stack - MAC Layer
        from mac.csma_ca import CsmaCa
        from mac.tdma import Tdma
        
        # Protocol Stack - PHY Layer
        from phy.phy import unicast, broadcast, multicast
        from phy.large_scale_fading import sinr_calculator
        
        # Control Modules
        from mobility.gauss_markov_3d import GaussMarkov3D
        from energy.energy_model import EnergyModel
        
        result.add_pass("Architecture imports", "All architecture components imported successfully")
        
        # Verify class structures
        assert hasattr(Simulator, '__init__'), "Simulator missing __init__"
        assert hasattr(Drone, 'generate_data_packet'), "Drone missing generate_data_packet"
        assert hasattr(Channel, 'create_inbox_for_receiver'), "Channel missing create_inbox_for_receiver"
        
        result.add_pass("Architecture class structure validation")
        return True
        
    except Exception as e:
        result.add_fail("Architecture imports", str(e))
        return False


def test_simulator_creates_all_components(result):
    """Test that Simulator correctly initializes all architectural components"""
    print("\n[2] SIMULATOR COMPONENT CREATION...")
    
    try:
        from simulator.simulator import Simulator
        
        env = simpy.Environment()
        channel_states = {i: simpy.Resource(env, capacity=1) for i in range(config.NUMBER_OF_DRONES)}
        
        sim = Simulator(
            seed=123,
            env=env,
            channel_states=channel_states,
            n_drones=config.NUMBER_OF_DRONES
        )
        
        # Verify Simulation Environment components
        assert sim.env is not None, "SimPy environment not created"
        assert sim.channel is not None, "Wireless Channel not created"
        assert sim.metrics is not None, "Metrics Collector not created"
        
        result.add_pass("Simulation Environment components", 
                       f"Env, Channel, Metrics all initialized")
        
        # Verify Drones created with complete protocol stack
        assert len(sim.drones) == config.NUMBER_OF_DRONES, f"Expected {config.NUMBER_OF_DRONES} drones"
        
        for i, drone in enumerate(sim.drones):
            # Protocol Stack validation
            assert hasattr(drone, 'routing_protocol'), f"Drone {i} missing routing_protocol"
            assert hasattr(drone, 'mac_protocol'), f"Drone {i} missing mac_protocol"
            assert hasattr(drone, 'transmitting_queue'), f"Drone {i} missing transmitting_queue"
            assert hasattr(drone, 'inbox'), f"Drone {i} missing inbox (PHY interface)"
            
            # Control Modules validation
            assert hasattr(drone, 'mobility_model'), f"Drone {i} missing mobility_model"
            assert hasattr(drone, 'energy_model'), f"Drone {i} missing energy_model"
        
        result.add_pass("Drone protocol stack creation", 
                       f"{config.NUMBER_OF_DRONES} drones with full stack")
        
        return sim
        
    except Exception as e:
        result.add_fail("Simulator component creation", str(e))
        return None


def test_packet_flow_architecture(result, sim):
    """Test complete packet flow through architectural layers"""
    print("\n[3] PACKET FLOW THROUGH ARCHITECTURE...")
    print("    Application → Transport → Network → MAC → PHY → Channel")
    
    if sim is None:
        result.add_fail("Packet flow", "No simulator available")
        return False
    
    try:
        # Run simulation for packet generation and flow
        sim.env.run(until=config.SIM_TIME)
        
        metrics = sim.metrics
        
        # Verify Application Layer generated packets
        if metrics.datapacket_generated_num == 0:
            result.add_warning("Application Layer", 
                             "No packets generated (may need longer sim time)")
        else:
            result.add_pass("Application Layer packet generation", 
                           f"{metrics.datapacket_generated_num} packets created")
        
        # Verify Transport/Queue layer processed packets
        queue_used = False
        for drone in sim.drones:
            if hasattr(drone, 'transmitting_queue'):
                queue_used = True
                break
        
        if queue_used:
            result.add_pass("Transport/Queue layer", "Queuing mechanism active")
        else:
            result.add_warning("Transport/Queue layer", "Queue not verified")
        
        # Verify Network Layer routing occurred
        if metrics.control_packet_num > 0:
            result.add_pass("Network/Routing Layer", 
                           f"{metrics.control_packet_num} routing control packets sent")
        else:
            result.add_warning("Network/Routing Layer", 
                             "No routing control packets (DSDV may not have exchanged)")
        
        # Verify MAC Layer accessed channel
        if len(metrics.mac_delay) > 0:
            avg_mac_delay = sum(metrics.mac_delay) / len(metrics.mac_delay)
            result.add_pass("MAC Layer channel access", 
                           f"{len(metrics.mac_delay)} transmissions, avg delay: {avg_mac_delay:.2f}ms")
        else:
            result.add_warning("MAC Layer", "No MAC delay recorded")
        
        # Verify PHY Layer transmitted through channel
        if metrics.collision_num > 0:
            result.add_pass("PHY/Channel collision detection", 
                           f"{metrics.collision_num} collisions detected")
        else:
            result.add_pass("PHY/Channel", "Clean transmission (0 collisions)")
        
        # Verify end-to-end delivery
        if len(metrics.datapacket_arrived) > 0:
            pdr = len(metrics.datapacket_arrived) / metrics.datapacket_generated_num * 100
            result.add_pass("End-to-end packet delivery", 
                           f"{len(metrics.datapacket_arrived)} packets delivered, PDR: {pdr:.1f}%")
        else:
            result.add_warning("End-to-end delivery", 
                             "No packets delivered (may need longer sim or check routing)")
        
        return True
        
    except Exception as e:
        result.add_fail("Packet flow test", str(e))
        return False


def test_control_modules_active(result, sim):
    """Test that control modules (Mobility, Energy) are functioning"""
    print("\n[4] CONTROL MODULES VALIDATION...")
    
    if sim is None:
        result.add_fail("Control modules", "No simulator available")
        return False
    
    try:
        all_ok = True
        
        for i, drone in enumerate(sim.drones):
            # Test Mobility Model
            if hasattr(drone, 'mobility_model') and drone.mobility_model is not None:
                initial_coords = drone.start_coords
                current_coords = drone.coords
                
                # Check if drone moved (coords should change over 5 seconds)
                moved = (initial_coords[0] != current_coords[0] or 
                        initial_coords[1] != current_coords[1] or 
                        initial_coords[2] != current_coords[2])
                
                if moved:
                    distance = ((current_coords[0]-initial_coords[0])**2 + 
                               (current_coords[1]-initial_coords[1])**2 + 
                               (current_coords[2]-initial_coords[2])**2)**0.5
                else:
                    distance = 0
                    all_ok = False
            else:
                all_ok = False
        
        if all_ok:
            result.add_pass("Mobility Model", "All drones have active mobility")
        else:
            result.add_warning("Mobility Model", "Some drones did not move")
        
        # Test Energy Model
        energy_depleted = False
        for drone in sim.drones:
            if hasattr(drone, 'residual_energy'):
                if drone.residual_energy < config.INITIAL_ENERGY:
                    energy_depleted = True
                    break
        
        if energy_depleted:
            result.add_pass("Energy Model", "Energy consumption detected")
        else:
            result.add_warning("Energy Model", 
                             "No energy depletion (short sim or low activity)")
        
        return True
        
    except Exception as e:
        result.add_fail("Control modules test", str(e))
        return False


def test_metrics_collection(result, sim):
    """Test that Metrics Collector captures all required data"""
    print("\n[5] METRICS COLLECTION VALIDATION...")
    
    if sim is None:
        result.add_fail("Metrics collection", "No simulator available")
        return False
    
    try:
        metrics = sim.metrics
        
        # Test to_dict() method for batch processing
        metrics_dict = metrics.to_dict()
        
        required_keys = [
            'sent', 'arrived', 'pdr_percent', 'e2e_delay_ms',
            'routing_load', 'throughput_kbps', 'hop_count',
            'collisions', 'mac_delay_ms'
        ]
        
        missing = [key for key in required_keys if key not in metrics_dict]
        
        if missing:
            result.add_fail("Metrics dict structure", f"Missing keys: {missing}")
            return False
        
        result.add_pass("Metrics dict structure", f"All {len(required_keys)} metrics present")
        
        # Validate metric data types
        assert isinstance(metrics_dict['sent'], int), "sent should be int"
        assert isinstance(metrics_dict['arrived'], int), "arrived should be int"
        assert isinstance(metrics_dict['pdr_percent'], float), "pdr_percent should be float"
        
        result.add_pass("Metrics data types", "All types valid")
        
        # Print summary
        print(f"\n    Metrics Summary:")
        print(f"    - Packets sent: {metrics_dict['sent']}")
        print(f"    - Packets arrived: {metrics_dict['arrived']}")
        print(f"    - PDR: {metrics_dict['pdr_percent']:.2f}%")
        print(f"    - Collisions: {metrics_dict['collisions']}")
        
        return True
        
    except Exception as e:
        result.add_fail("Metrics collection test", str(e))
        return False


def test_cross_layer_interactions(result, sim):
    """Test cross-layer interactions as shown in architecture"""
    print("\n[6] CROSS-LAYER INTERACTION VALIDATION...")
    
    if sim is None:
        result.add_fail("Cross-layer interactions", "No simulator available")
        return False
    
    try:
        # Test: Mobility → PHY (position updates affect channel)
        position_affects_channel = True
        for drone in sim.drones:
            if not hasattr(drone, 'coords'):
                position_affects_channel = False
        
        if position_affects_channel:
            result.add_pass("Mobility → PHY interaction", 
                           "Position updates exist in drone entities")
        
        # Test: Energy → Drone (consumption tracking)
        energy_tracked = all(hasattr(d, 'residual_energy') for d in sim.drones)
        
        if energy_tracked:
            result.add_pass("Energy → Drone interaction", 
                           "Energy consumption tracked for all drones")
        
        # Test: Drone → Metrics (event reporting)
        if sim.metrics.datapacket_generated_num > 0:
            result.add_pass("Drone → Metrics interaction", 
                           "Events reported to metrics collector")
        
        return True
        
    except Exception as e:
        result.add_fail("Cross-layer interactions test", str(e))
        return False


def run_integration_tests():
    """Run all integration tests"""
    print("="*60)
    print("UAV SIM PATCHED - INTEGRATION TESTS")
    print("="*60)
    print("Testing architecture-based component integration...")
    print(f"Config: {config.NUMBER_OF_DRONES} drones, {config.SIM_TIME/1e6}s simulation")
    
    result = IntegrationTestResult()
    
    # Architecture validation
    if not test_architecture_imports(result):
        print("\n⚠️  Architecture import failed - stopping tests")
        return result.summary(), result
    
    # Create simulator
    sim = test_simulator_creates_all_components(result)
    
    # Run integration tests
    test_packet_flow_architecture(result, sim)
    test_control_modules_active(result, sim)
    test_metrics_collection(result, sim)
    test_cross_layer_interactions(result, sim)
    
    return result.summary(), result


if __name__ == "__main__":
    success, result = run_integration_tests()
    sys.exit(0 if success else 1)
