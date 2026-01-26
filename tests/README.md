# UAV Sim Patched - Test Suite

This directory contains comprehensive tests for the UAV simulator.

## Test Structure

```
tests/
├── __init__.py               # Tests package
├── test_smoke.py             # Smoke tests (syntax, imports, config)
├── test_functional.py        # Functional tests (simulator, components)
├── test_integration.py       # Integration tests (end-to-end flows)
└── run_all_tests.py          # Test runner
```

## Running Tests

### Run All Tests
```powershell
cd "c:/Users/hkphi/Downloads/UAV NET SIM PATCHES/uavnetsim_sweep_patched/uav_sim_patched"
python -m tests.run_all_tests
```

### Run Individual Test Suites

**Smoke Tests** (syntax and imports):
```powershell
python -m tests.test_smoke
```

**Functional Tests** (core functionality):
```powershell
python -m tests.test_functional
```

**Integration Tests** (end-to-end):
```powershell
python -m tests.test_integration
```

## What Each Test Suite Validates

### 1. Smoke Tests (`test_smoke.py`)
- ✓ Python syntax for all 78+ .py files
- ✓ Module imports resolve correctly
- ✓ Configuration parameters are valid
- ✓ Core architecture components can be imported

### 2. Functional Tests (`test_functional.py`)
- ✓ Simulator initializes without errors
- ✓ All drones created with required components
- ✓ Simulation runs to completion
- ✓ Metrics collection works

### 3. Integration Tests (`test_integration.py`)
- ✓ Architecture-based import dependencies
- ✓ Complete packet flow: App → Transport → Network → MAC → PHY → Channel
- ✓ Control modules active (Mobility, Energy)
- ✓ Cross-layer interactions
- ✓ End-to-end packet delivery
- ✓ Metrics collector captures all data

## Test Configuration

Tests use reduced scope for speed:
- **Smoke**: Static analysis only
- **Functional**: 3 drones, 1 second simulation
- **Integration**: 5 drones, 5 seconds simulation

Plots and verbose logging are disabled during testing.

## Future Updates

Before running the main simulation after updates:
1. Run `python -m tests.run_all_tests`
2. Ensure all tests pass
3. Review any warnings
4. If tests fail, fix issues before deployment
