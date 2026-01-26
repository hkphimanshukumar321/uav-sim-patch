"""
Mobility Parameter Sweep

Predefined sweep configurations for mobility model parameters.
These affect drone movement patterns, randomness, and dynamics.

Usage:
    python -m ablation.ablation_runner --sweep quick_mobility
"""

# Mobility sweep configurations
MOBILITY_SWEEP = {
    "quick": {
        "MOBILITY_ALPHA": [0.5, 0.85, 0.99],
        "CIRCULAR_RADIUS": [50],
    },
    "alpha_sensitivity": {
        "MOBILITY_ALPHA": [0.0, 0.25, 0.5, 0.75, 0.85, 0.95, 1.0],
    },
    "update_intervals": {
        "MOBILITY_POSITION_UPDATE_INTERVAL": [5e4, 1e5, 2e5],
        "MOBILITY_DIRECTION_UPDATE_INTERVAL": [2.5e5, 5e5, 1e6],
    },
    "circular_patterns": {
        "CIRCULAR_RADIUS": [25, 50, 75, 100, 150],
        "CIRCULAR_PATTERN_DURATION": [10e6, 15e6, 30e6],
    },
    "switch_intervals": {
        "MOBILITY_SWITCH_INTERVAL": [15e6, 30e6, 60e6],
        "CIRCULAR_PATTERN_DURATION": [10e6, 15e6, 20e6],
    },
    "static_vs_mobile": {
        "STATIC_CASE": [0, 1],
        "MOBILITY_ALPHA": [0.5, 0.85],
    },
    "boundary_effects": {
        "MOBILITY_BOUNDARY_BUFFER": [1, 5, 10, 20],
        "MOBILITY_ALPHA": [0.85],
    },
}


def get_mobility_sweep(name: str = "quick"):
    """Get a mobility sweep configuration by name"""
    return MOBILITY_SWEEP.get(name, MOBILITY_SWEEP["quick"])
