"""
Experiment Tests for UAV Sim Patched
=====================================
Validates experiment functionality:
1. Experiment module imports
2. Scenario schema functions
3. Experiment execution (small-scale)
4. Config isolation
5. Output format validation

Run: python -m tests.test_experiments
"""

import sys
import csv
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import simpy
from utils import config

# Save original config values for restoration
ORIGINAL_CONFIG = {}


class ExperimentTestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
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
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"EXPERIMENT TEST SUMMARY: {self.passed}/{total} passed")
        print(f"{'='*60}")
        return self.failed == 0


def save_original_config():
    """Save original config values before tests"""
    global ORIGINAL_CONFIG
    ORIGINAL_CONFIG = {
        'MAC_MODE': config.MAC_MODE,
        'TRAFFIC_PATTERN': config.TRAFFIC_PATTERN,
        'TRAFFIC_RATE': config.TRAFFIC_RATE,
        'ENABLE_PLOTS': config.ENABLE_PLOTS,
        'ENABLE_TIME_PRINTS': config.ENABLE_TIME_PRINTS,
        'SIM_TIME': config.SIM_TIME,
        'NUMBER_OF_DRONES': config.NUMBER_OF_DRONES,
    }


def restore_original_config():
    """Restore original config values after tests"""
    for key, value in ORIGINAL_CONFIG.items():
        setattr(config, key, value)


def test_experiment_imports(result):
    """Test that experiment modules can be imported"""
    print("\n[1] EXPERIMENT MODULE IMPORTS...")
    
    try:
        # Import experiment modules
        from experiments import scenario_schema
        from experiments import sweep_mac_rate_1_20
        
        result.add_pass("Experiment module imports", "All experiment modules imported")
        return True
        
    except Exception as e:
        result.add_fail("Experiment module imports", str(e))
        return False


def test_scenario_schema_functions(result):
    """Test scenario_schema utility functions"""
    print("\n[2] SCENARIO SCHEMA VALIDATION...")
    
    try:
        from experiments.scenario_schema import (
            scenario_key, 
            scenario_id_from_key,
            make_base_scenarios,
            SCENARIO_FIELDS,
            METRICS
        )
        
        # Test scenario_key generation
        test_dict = {
            "mac_mode": "TDMA",
            "traffic_pattern": "Poisson",
            "traffic_rate": 10,
            "uniform_iat_us": (500000, 505000),
            "payload_mode": "fixed",
            "avg_payload_bytes": 1024,
            "payload_var_bytes": 0,
            "enable_dynamic_mobility": True,
            "enable_obstacle_avoidance": True,
        }
        
        key = scenario_key(test_dict)
        assert isinstance(key, str), "scenario_key should return string"
        assert "mac_mode=TDMA" in key, "scenario_key should contain mac_mode"
        
        result.add_pass("scenario_key generation", f"Generated key: {key[:50]}...")
        
        # Test scenario_id generation
        sid = scenario_id_from_key(key)
        assert isinstance(sid, str), "scenario_id should be string"
        assert len(sid) == 12, "scenario_id should be 12 chars"
        
        result.add_pass("scenario_id generation", f"Generated ID: {sid}")
        
        # Test make_base_scenarios
        scenarios = make_base_scenarios(avg_payload_bytes=1024)
        assert isinstance(scenarios, list), "make_base_scenarios should return list"
        assert len(scenarios) == 40, "Should generate 40 scenarios (2 MAC × 20 rates)"
        
        # Verify all scenarios have required fields
        for s in scenarios:
            assert "scenario_key" in s, "Scenario missing scenario_key"
            assert "scenario_id" in s, "Scenario missing scenario_id"
            assert "mac_mode" in s, "Scenario missing mac_mode"
        
        result.add_pass("make_base_scenarios", f"Generated {len(scenarios)} scenarios")
        
        # Verify METRICS and SCENARIO_FIELDS are defined
        assert len(METRICS) > 0, "METRICS should not be empty"
        assert len(SCENARIO_FIELDS) > 0, "SCENARIO_FIELDS should not be empty"
        
        result.add_pass("Schema constants", f"{len(METRICS)} metrics, {len(SCENARIO_FIELDS)} fields")
        
        return True
        
    except Exception as e:
        result.add_fail("Scenario schema validation", str(e))
        return False


def test_sweep_execution_small_scale(result):
    """Test sweep experiment with minimal config"""
    print("\n[3] SMALL-SCALE SWEEP EXECUTION...")
    
    try:
        from simulator.simulator import Simulator
        from experiments.sweep_mac_rate_1_20 import run_once
        
        # Override to small scale
        original_sim_time = config.SIM_TIME
        original_drones = config.NUMBER_OF_DRONES
        
        config.SIM_TIME = 1 * 1e6  # 1 second only
        config.NUMBER_OF_DRONES = 3  # 3 drones
        config.ENABLE_PLOTS = False
        config.ENABLE_TIME_PRINTS = False
        
        # Run one experiment (TDMA, rate=5)
        row = run_once(seed=123, mac_mode="TDMA", rate=5)
        
        # Verify output structure
        required_keys = ['mac_mode', 'rate', 'seed', 'sent', 'arrived', 
                        'pdr_percent', 'e2e_delay_ms', 'routing_load', 
                        'throughput_kbps', 'hop_count', 'collisions', 'mac_delay_ms']
        
        missing = [k for k in required_keys if k not in row]
        if missing:
            result.add_fail("Sweep output structure", f"Missing keys: {missing}")
            return False
        
        result.add_pass("Sweep execution", 
                       f"MAC={row['mac_mode']}, rate={row['rate']}, sent={row['sent']}")
        
        # Verify data types
        assert isinstance(row['sent'], int), "sent should be int"
        assert isinstance(row['arrived'], int), "arrived should be int"
        assert isinstance(row['pdr_percent'], float), "pdr_percent should be float"
        
        result.add_pass("Sweep output data types")
        
        # Restore config
        config.SIM_TIME = original_sim_time
        config.NUMBER_OF_DRONES = original_drones
        
        return True
        
    except Exception as e:
        result.add_fail("Sweep execution", str(e))
        return False


def test_config_isolation(result):
    """Test that config changes are properly isolated"""
    print("\n[4] CONFIG ISOLATION TEST...")
    
    try:
        # Record current config
        before_mac = config.MAC_MODE
        before_rate = config.TRAFFIC_RATE
        
        # Simulate experiment modifying config
        config.MAC_MODE = "CSMA"
        config.TRAFFIC_RATE = 15
        
        # Verify changes took effect
        assert config.MAC_MODE == "CSMA", "Config change didn't apply"
        assert config.TRAFFIC_RATE == 15, "Config change didn't apply"
        
        # Restore original values
        restore_original_config()
        
        # Verify restoration worked
        if config.MAC_MODE == ORIGINAL_CONFIG['MAC_MODE']:
            result.add_pass("Config isolation", "Config properly restored after changes")
        else:
            result.add_fail("Config isolation", "Config not properly restored")
            return False
        
        return True
        
    except Exception as e:
        result.add_fail("Config isolation", str(e))
        return False


def test_csv_output_format(result):
    """Test CSV output format validation"""
    print("\n[5] CSV OUTPUT FORMAT VALIDATION...")
    
    try:
        # Create a small test CSV
        test_csv = "test_sweep_output.csv"
        test_rows = [
            {'mac_mode': 'TDMA', 'rate': 1, 'seed': 2025, 'sent': 10, 'arrived': 8,
             'pdr_percent': 80.0, 'e2e_delay_ms': 5.5, 'routing_load': 1.2,
             'throughput_kbps': 100.0, 'hop_count': 2.5, 'collisions': 0, 'mac_delay_ms': 3.2},
            {'mac_mode': 'CSMA', 'rate': 1, 'seed': 2025, 'sent': 10, 'arrived': 9,
             'pdr_percent': 90.0, 'e2e_delay_ms': 4.8, 'routing_load': 1.1,
             'throughput_kbps': 110.0, 'hop_count': 2.3, 'collisions': 1, 'mac_delay_ms': 2.9},
        ]
        
        fieldnames = ['mac_mode', 'rate', 'seed', 'sent', 'arrived',
                     'pdr_percent', 'e2e_delay_ms', 'routing_load', 
                     'throughput_kbps', 'hop_count', 'collisions', 'mac_delay_ms']
        
        # Write CSV
        with open(test_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(test_rows)
        
        # Read and validate CSV
        with open(test_csv, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            assert len(rows) == 2, "Should have 2 data rows"
            assert rows[0]['mac_mode'] == 'TDMA', "First row should be TDMA"
            assert rows[1]['mac_mode'] == 'CSMA', "Second row should be CSMA"
        
        result.add_pass("CSV output format", f"Valid CSV with {len(rows)} rows")
        
        # Clean up
        if os.path.exists(test_csv):
            os.remove(test_csv)
        
        return True
        
    except Exception as e:
        result.add_fail("CSV output format", str(e))
        return False


def run_experiment_tests():
    """Run all experiment tests"""
    print("="*60)
    print("UAV SIM PATCHED - EXPERIMENT TESTS")
    print("="*60)
    
    result = ExperimentTestResult()
    
    # Save config before tests
    save_original_config()
    
    try:
        test_experiment_imports(result)
        test_scenario_schema_functions(result)
        test_sweep_execution_small_scale(result)
        test_config_isolation(result)
        test_csv_output_format(result)
    finally:
        # Always restore config
        restore_original_config()
    
    return result.summary(), result


if __name__ == "__main__":
    success, result = run_experiment_tests()
    sys.exit(0 if success else 1)
