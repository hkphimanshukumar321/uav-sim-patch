"""
Channel Parameter Sweep

Predefined sweep configurations for channel/PHY layer parameters.
These affect wireless propagation, SINR calculation, and reception success.

Usage:
    python -m ablation.ablation_runner --sweep quick_channel
"""

# Quick channel sweep - 3 configurations
CHANNEL_SWEEP = {
    "quick": {
        "SNR_THRESHOLD": [4, 6, 10],
        "NOISE_POWER": [4e-11],
    },
    "noise_sensitivity": {
        "NOISE_POWER": [1e-11, 2e-11, 4e-11, 8e-11, 1e-10],
        "SNR_THRESHOLD": [6],
    },
    "snr_sensitivity": {
        "SNR_THRESHOLD": [2, 4, 6, 8, 10, 12],
        "NOISE_POWER": [4e-11],
    },
    "power_vs_noise": {
        "TRANSMITTING_POWER": [0.05, 0.1, 0.2],
        "NOISE_POWER": [1e-11, 4e-11, 1e-10],
    },
    "path_loss": {
        "PATH_LOSS_EXPONENT": [2.0, 2.5, 3.0, 3.5, 4.0],
        "TRANSMITTING_POWER": [0.1],
    },
    "path_loss_model": {
        "PATH_LOSS_MODEL": ["general", "probabilistic_los"],
        "SNR_THRESHOLD": [4, 6, 8],
    },
}

# Shortcut function
def get_channel_sweep(name: str = "quick"):
    """Get a channel sweep configuration by name"""
    return CHANNEL_SWEEP.get(name, CHANNEL_SWEEP["quick"])
