# UAV Network Simulator Ablation Study Framework

This module provides a standalone framework for systematic parameter sweeps and ablation studies.

## Quick Start

```powershell
# Run a quick channel sweep (3 configurations)
python -m ablation.ablation_runner --sweep channel --quick

# Run full factorial experiment
python -m ablation.ablation_runner --sweep full_factorial --output results/

# Dry run to see what would be executed
python -m ablation.ablation_runner --sweep mobility --dry-run
```

## Structure

```
ablation/
├── __init__.py           # Package initialization
├── README.md             # This file
├── ablation_config.py    # Parameter registry with all knobs
├── ablation_runner.py    # Execution engine
└── sweeps/
    ├── __init__.py
    ├── channel_sweep.py  # Channel parameter variations
    ├── mobility_sweep.py # Mobility model variations
    └── full_factorial.py # Full factorial design
```

## Parameters Available

### Simulation
- `NUMBER_OF_DRONES`, `SIM_TIME`, `MAP_*`

### Channel/PHY
- `TRANSMITTING_POWER`, `NOISE_POWER`, `SNR_THRESHOLD`
- `PATH_LOSS_EXPONENT`, `PATH_LOSS_MODEL`

### Mobility
- `MOBILITY_ALPHA`, `MOBILITY_*_INTERVAL`

### MAC
- `MAC_MODE`, `CONTENTION_THRESHOLD_*`

### Traffic
- `TRAFFIC_PATTERN`, `TRAFFIC_RATE`

## Output

Results are saved to CSV with all parameters logged for reproducibility.
