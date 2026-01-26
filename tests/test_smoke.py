"""
Smoke Tests for UAV Sim Patched
================================
Validates:
1. Python syntax for all .py files
2. All module imports resolve correctly
3. Configuration loads without errors

Run: python -m tests.test_smoke
"""

import sys
import os
import py_compile
import importlib
import traceback
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

class SmokeTestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_pass(self, test_name):
        self.passed += 1
        print(f"  [PASS]: {test_name}")
    
    def add_fail(self, test_name, error):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"  [FAIL]: {test_name}")
        print(f"         Error: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"SMOKE TEST SUMMARY: {self.passed}/{total} passed")
        print(f"{'='*60}")
        return self.failed == 0


def test_syntax_all_files(result):
    """Check Python syntax for all .py files"""
    print("\n[1] SYNTAX CHECK - Compiling all Python files...")
    
    root = Path(__file__).parent.parent
    py_files = list(root.rglob("*.py"))
    
    # Exclude test files themselves
    py_files = [f for f in py_files if "tests" not in str(f)]
    
    syntax_errors = []
    for py_file in py_files:
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as e:
            syntax_errors.append((py_file.name, str(e)))
    
    if syntax_errors:
        for filename, error in syntax_errors:
            result.add_fail(f"Syntax: {filename}", error)
    else:
        result.add_pass(f"Syntax check for {len(py_files)} Python files")
    
    return len(syntax_errors) == 0


def test_core_imports(result):
    """Test that core modules can be imported"""
    print("\n[2] IMPORT CHECK - Testing module imports...")
    
    # Core modules that MUST import successfully (Architecture components)
    core_modules = [
        # Simulation Environment
        ("simulator.simulator", "Simulator"),
        ("simulator.metrics", "Metrics"),
        ("phy.channel", "Channel"),
        ("visualization.visualizer", "SimulationVisualizer"),
        
        # Drone Entity & Protocol Stack
        ("entities.drone", "Drone"),
        ("entities.packet", "DataPacket"),
        
        # Network/Routing Layer
        ("routing.dsdv.dsdv", "Dsdv"),
        ("routing.greedy.greedy", "Greedy"),
        
        # MAC Layer
        ("mac.csma_ca", "CsmaCa"),
        ("mac.tdma", "Tdma"),
        
        # Physical Layer
        ("phy.phy", None),
        ("phy.large_scale_fading", "sinr_calculator"),
        
        # Control Modules
        ("mobility.gauss_markov_3d", "GaussMarkov3D"),
        ("energy.energy_model", "EnergyModel"),
        
        # Utils
        ("utils.config", None),
        ("utils.util_function", None),
    ]
    
    all_ok = True
    for module_name, class_name in core_modules:
        try:
            mod = importlib.import_module(module_name)
            if class_name:
                if not hasattr(mod, class_name):
                    result.add_fail(f"Import {module_name}.{class_name}", f"Class/function '{class_name}' not found")
                    all_ok = False
                else:
                    result.add_pass(f"Import {module_name}.{class_name}")
            else:
                result.add_pass(f"Import {module_name}")
        except Exception as e:
            result.add_fail(f"Import {module_name}", str(e))
            all_ok = False
    
    return all_ok


def test_config_load(result):
    """Test configuration file loads correctly"""
    print("\n[3] CONFIG CHECK - Validating configuration parameters...")
    
    try:
        from utils import config
        
        # Required config parameters (based on architecture)
        required_params = [
            'NUMBER_OF_DRONES',
            'SIM_TIME',
            'MAP_LENGTH',
            'MAP_WIDTH',
            'MAP_HEIGHT',
            'TRANSMITTING_POWER',
            'BIT_RATE',
            'MAX_RETRANSMISSION_ATTEMPT',
            'TRAFFIC_PATTERN',
            'MAC_MODE',
        ]
        
        missing = []
        for param in required_params:
            if not hasattr(config, param):
                missing.append(param)
        
        if missing:
            result.add_fail("Config parameters", f"Missing: {missing}")
            return False
        else:
            result.add_pass(f"Config has all {len(required_params)} required parameters")
        
        # Validate param types/ranges
        if config.NUMBER_OF_DRONES < 1:
            result.add_fail("Config validation", "NUMBER_OF_DRONES must be >= 1")
            return False
        
        if config.SIM_TIME <= 0:
            result.add_fail("Config validation", "SIM_TIME must be > 0")
            return False
            
        result.add_pass("Config parameter validation")
        return True
        
    except Exception as e:
        result.add_fail("Config load", str(e))
        return False


def run_smoke_tests():
    """Run all smoke tests"""
    print("="*60)
    print("UAV SIM PATCHED - SMOKE TESTS")
    print("="*60)
    
    result = SmokeTestResult()
    
    test_syntax_all_files(result)
    test_core_imports(result)
    test_config_load(result)
    
    return result.summary(), result


if __name__ == "__main__":
    success, result = run_smoke_tests()
    sys.exit(0 if success else 1)
