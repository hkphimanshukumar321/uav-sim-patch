"""
Ablation Configuration Registry

Comprehensive parameter definitions for ablation studies.
All parameters that can be varied in experiments are defined here with:
- Default values
- Valid ranges
- Type information
- Description

Usage:
    from ablation.ablation_config import AblationConfig
    
    # Get all parameters with defaults
    config = AblationConfig.get_defaults()
    
    # Get parameter metadata
    meta = AblationConfig.get_parameter_info('MOBILITY_ALPHA')
"""

from dataclasses import dataclass
from typing import Dict, Any, Tuple, Union, List
import math


@dataclass
class ParamInfo:
    """Metadata for a configuration parameter"""
    default: Any
    param_type: type
    min_val: Any = None
    max_val: Any = None
    description: str = ""
    category: str = "general"
    affects: List[str] = None  # List of modules affected
    
    def __post_init__(self):
        if self.affects is None:
            self.affects = []


class AblationConfig:
    """
    Central registry for all ablation study parameters.
    
    Categories:
    - simulation: General simulation parameters
    - channel: Wireless channel / PHY layer
    - mobility: Drone mobility models
    - drone_behavior: Dynamic drone behaviors
    - mac: MAC protocol parameters
    - traffic: Traffic generation
    - randomness: Seed control
    """
    
    # ====================== PARAMETER REGISTRY ======================
    PARAMETERS: Dict[str, ParamInfo] = {
        # -------------------- Simulation --------------------
        "NUMBER_OF_DRONES": ParamInfo(
            default=10, param_type=int, min_val=2, max_val=100,
            description="Number of drones in the network",
            category="simulation", affects=["simulator", "all"]
        ),
        "SIM_TIME": ParamInfo(
            default=30 * 1e6, param_type=float, min_val=1e6, max_val=600 * 1e6,
            description="Total simulation time in microseconds",
            category="simulation", affects=["simulator"]
        ),
        "MAP_LENGTH": ParamInfo(
            default=600, param_type=float, min_val=100, max_val=10000,
            description="Length of simulation area in meters",
            category="simulation", affects=["simulator", "mobility", "visualizer"]
        ),
        "MAP_WIDTH": ParamInfo(
            default=600, param_type=float, min_val=100, max_val=10000,
            description="Width of simulation area in meters",
            category="simulation", affects=["simulator", "mobility", "visualizer"]
        ),
        "MAP_HEIGHT": ParamInfo(
            default=100, param_type=float, min_val=10, max_val=1000,
            description="Height of simulation area in meters",
            category="simulation", affects=["simulator", "mobility", "visualizer"]
        ),
        "STATIC_CASE": ParamInfo(
            default=0, param_type=int, min_val=0, max_val=1,
            description="Whether drones are static (0=mobile, 1=static)",
            category="simulation", affects=["mobility"]
        ),
        
        # -------------------- Channel/PHY --------------------
        "TRANSMITTING_POWER": ParamInfo(
            default=0.1, param_type=float, min_val=0.01, max_val=1.0,
            description="Transmit power in Watts",
            category="channel", affects=["phy", "large_scale_fading"]
        ),
        "NOISE_POWER": ParamInfo(
            default=4e-11, param_type=float, min_val=1e-12, max_val=1e-9,
            description="Noise power in Watts",
            category="channel", affects=["phy", "large_scale_fading"]
        ),
        "SNR_THRESHOLD": ParamInfo(
            default=6, param_type=float, min_val=1, max_val=30,
            description="SNR threshold for successful reception in dB",
            category="channel", affects=["drone", "large_scale_fading"]
        ),
        "PATH_LOSS_EXPONENT": ParamInfo(
            default=2, param_type=float, min_val=2, max_val=6,
            description="Path loss exponent (2=free space, 4=urban)",
            category="channel", affects=["large_scale_fading"]
        ),
        "PATH_LOSS_MODEL": ParamInfo(
            default="general", param_type=str, min_val=None, max_val=None,
            description="Path loss model: 'general' or 'probabilistic_los'",
            category="channel", affects=["large_scale_fading"]
        ),
        "SENSING_RANGE": ParamInfo(
            default=750, param_type=float, min_val=100, max_val=2000,
            description="Range where transmission can cause interference (meters)",
            category="channel", affects=["mac"]
        ),
        
        # -------------------- Mobility --------------------
        "MOBILITY_ALPHA": ParamInfo(
            default=0.85, param_type=float, min_val=0.0, max_val=1.0,
            description="Gauss-Markov alpha (0=random, 1=deterministic)",
            category="mobility", affects=["gauss_markov_3d"]
        ),
        "MOBILITY_POSITION_UPDATE_INTERVAL": ParamInfo(
            default=1e5, param_type=float, min_val=1e4, max_val=1e6,
            description="Position update interval in microseconds",
            category="mobility", affects=["gauss_markov_3d"]
        ),
        "MOBILITY_DIRECTION_UPDATE_INTERVAL": ParamInfo(
            default=5e5, param_type=float, min_val=1e5, max_val=5e6,
            description="Direction change interval in microseconds",
            category="mobility", affects=["gauss_markov_3d"]
        ),
        "MOBILITY_BOUNDARY_BUFFER": ParamInfo(
            default=1, param_type=float, min_val=0, max_val=50,
            description="Distance from boundary to start rebounding (meters)",
            category="mobility", affects=["gauss_markov_3d"]
        ),
        
        # -------------------- Drone Dynamic Behavior --------------------
        "MOBILITY_SWITCH_INTERVAL": ParamInfo(
            default=30e6, param_type=float, min_val=5e6, max_val=120e6,
            description="Interval between mobility pattern switches (us)",
            category="drone_behavior", affects=["drone"]
        ),
        "CIRCULAR_PATTERN_DURATION": ParamInfo(
            default=15e6, param_type=float, min_val=5e6, max_val=60e6,
            description="Duration of circular mobility pattern (us)",
            category="drone_behavior", affects=["drone"]
        ),
        "CIRCULAR_RADIUS": ParamInfo(
            default=50, param_type=float, min_val=10, max_val=200,
            description="Radius of circular movement pattern (meters)",
            category="drone_behavior", affects=["drone"]
        ),
        "OBSTACLE_DETECTION_RANGE": ParamInfo(
            default=30, param_type=float, min_val=5, max_val=100,
            description="Range for detecting obstacles (meters)",
            category="drone_behavior", affects=["drone"]
        ),
        "MIN_OBSTACLE_DISTANCE": ParamInfo(
            default=10, param_type=float, min_val=1, max_val=50,
            description="Minimum safe distance from obstacles (meters)",
            category="drone_behavior", affects=["drone"]
        ),
        
        # -------------------- Adaptive MAC --------------------
        "MAC_MODE": ParamInfo(
            default="TDMA", param_type=str, min_val=None, max_val=None,
            description="MAC protocol: 'TDMA', 'CSMA', or 'ADAPTIVE'",
            category="mac", affects=["drone", "mac"]
        ),
        "MAC_SWITCH_INTERVAL": ParamInfo(
            default=20e6, param_type=float, min_val=5e6, max_val=60e6,
            description="Interval for MAC protocol evaluation (us)",
            category="mac", affects=["drone"]
        ),
        "CONTENTION_WINDOW": ParamInfo(
            default=5e6, param_type=float, min_val=1e6, max_val=30e6,
            description="Window for measuring contention level (us)",
            category="mac", affects=["drone"]
        ),
        "CONTENTION_THRESHOLD_HIGH": ParamInfo(
            default=0.7, param_type=float, min_val=0.5, max_val=0.95,
            description="Contention level to switch to TDMA",
            category="mac", affects=["drone"]
        ),
        "CONTENTION_THRESHOLD_LOW": ParamInfo(
            default=0.3, param_type=float, min_val=0.05, max_val=0.5,
            description="Contention level to switch to CSMA",
            category="mac", affects=["drone"]
        ),
        "CW_MIN": ParamInfo(
            default=31, param_type=int, min_val=7, max_val=255,
            description="Initial contention window size for CSMA",
            category="mac", affects=["csma_ca"]
        ),
        "MAX_RETRANSMISSION_ATTEMPT": ParamInfo(
            default=5, param_type=int, min_val=1, max_val=15,
            description="Maximum retransmission attempts per packet",
            category="mac", affects=["drone"]
        ),
        "TDMA_SLOT_DURATION": ParamInfo(
            default=1000, param_type=int, min_val=100, max_val=10000,
            description="TDMA slot duration in microseconds",
            category="mac", affects=["tdma"]
        ),
        "TDMA_SLOTS_PER_FRAME": ParamInfo(
            default=10, param_type=int, min_val=2, max_val=50,
            description="Number of slots per TDMA frame",
            category="mac", affects=["tdma"]
        ),
        "TDMA_GUARD_TIME": ParamInfo(
            default=10, param_type=int, min_val=1, max_val=100,
            description="Guard time between TDMA slots in microseconds",
            category="mac", affects=["tdma"]
        ),
        "ALOHA_RANDOM_BACKOFF_BASE": ParamInfo(
            default=500, param_type=int, min_val=100, max_val=5000,
            description="Base value for ALOHA random backoff in microseconds",
            category="mac", affects=["pure_aloha"]
        ),
        
        # -------------------- Traffic --------------------
        "TRAFFIC_PATTERN": ParamInfo(
            default="Poisson", param_type=str, min_val=None, max_val=None,
            description="Traffic pattern: 'Poisson' or 'Uniform'",
            category="traffic", affects=["drone"]
        ),
        "TRAFFIC_RATE": ParamInfo(
            default=10, param_type=float, min_val=0.1, max_val=100,
            description="Packets per second per drone (Poisson)",
            category="traffic", affects=["drone"]
        ),
        "AVERAGE_PAYLOAD_LENGTH": ParamInfo(
            default=8192, param_type=int, min_val=256, max_val=65536,
            description="Average payload length in bits",
            category="traffic", affects=["drone", "packet"]
        ),
        "VARIABLE_PAYLOAD_LENGTH": ParamInfo(
            default=0, param_type=int, min_val=0, max_val=1,
            description="Enable variable payload length",
            category="traffic", affects=["drone"]
        ),
        
        # -------------------- Randomness --------------------
        "MASTER_SEED": ParamInfo(
            default=2025, param_type=int, min_val=-1, max_val=2**31,
            description="Master seed for reproducibility (-1 for random)",
            category="randomness", affects=["all"]
        ),
        "ENABLE_SEED_VARIATION": ParamInfo(
            default=False, param_type=bool, min_val=None, max_val=None,
            description="Add drone ID to seed for per-drone variation",
            category="randomness", affects=["drone", "mobility"]
        ),
    }
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        """Get all parameters with default values"""
        return {name: info.default for name, info in cls.PARAMETERS.items()}
    
    @classmethod
    def get_parameter_info(cls, param_name: str) -> ParamInfo:
        """Get metadata for a specific parameter"""
        return cls.PARAMETERS.get(param_name)
    
    @classmethod
    def get_by_category(cls, category: str) -> Dict[str, ParamInfo]:
        """Get all parameters in a category"""
        return {
            name: info for name, info in cls.PARAMETERS.items()
            if info.category == category
        }
    
    @classmethod
    def validate_value(cls, param_name: str, value: Any) -> bool:
        """Validate a parameter value against its constraints"""
        info = cls.PARAMETERS.get(param_name)
        if info is None:
            return False
        
        # Type check
        if not isinstance(value, info.param_type):
            return False
        
        # Range check (for numeric types)
        if info.min_val is not None and value < info.min_val:
            return False
        if info.max_val is not None and value > info.max_val:
            return False
        
        return True
    
    @classmethod
    def get_categories(cls) -> List[str]:
        """Get list of all parameter categories"""
        return list(set(info.category for info in cls.PARAMETERS.values()))
    
    @classmethod
    def generate_sweep_values(
        cls, 
        param_name: str, 
        n_values: int = 5
    ) -> List[Any]:
        """Generate sweep values for a parameter"""
        info = cls.PARAMETERS.get(param_name)
        if info is None:
            return []
        
        if info.param_type == str:
            # String parameters - return known valid values
            if param_name == "MAC_MODE":
                return ["TDMA", "CSMA", "ADAPTIVE"]
            elif param_name == "TRAFFIC_PATTERN":
                return ["Poisson", "Uniform"]
            elif param_name == "PATH_LOSS_MODEL":
                return ["general", "probabilistic_los"]
            return [info.default]
        
        elif info.param_type == bool:
            return [False, True]
        
        elif info.param_type in (int, float):
            if info.min_val is not None and info.max_val is not None:
                step = (info.max_val - info.min_val) / (n_values - 1)
                values = [info.min_val + i * step for i in range(n_values)]
                if info.param_type == int:
                    values = [int(v) for v in values]
                return values
        
        return [info.default]


# Predefined sweep configurations
SWEEP_PRESETS = {
    "quick_channel": {
        "SNR_THRESHOLD": [4, 6, 10],
        "NOISE_POWER": [1e-11, 4e-11, 1e-10],
    },
    "quick_mobility": {
        "MOBILITY_ALPHA": [0.5, 0.85, 0.99],
        "CIRCULAR_RADIUS": [25, 50, 100],
    },
    "mac_comparison": {
        "MAC_MODE": ["TDMA", "CSMA"],
        "TRAFFIC_RATE": [5, 10, 20],
    },
    # HIGH TRAFFIC: to reach TDMA/CSMA crossover point where TDMA wins
    "high_traffic_crossover": {
        "MAC_MODE": ["TDMA", "CSMA"],
        "TRAFFIC_RATE": [20, 25, 30, 35, 40],
    },
    # Extended range to confirm crossover
    "extended_traffic": {
        "MAC_MODE": ["TDMA", "CSMA"],
        "TRAFFIC_RATE": [10, 20, 30, 40, 50],
    },
    "scalability": {
        "NUMBER_OF_DRONES": [5, 10, 20, 30],
        "TRAFFIC_RATE": [5, 10 , 20],
    },
    # High drone count - TDMA should win here due to collision-free
    "dense_swarm": {
        "MAC_MODE": ["TDMA", "CSMA"],
        "NUMBER_OF_DRONES": [20, 30, 40, 50],
        "TRAFFIC_RATE": [15],
    },
    "full_factorial": {
        "MAC_MODE": ["TDMA", "CSMA"],
        "TRAFFIC_RATE": [5, 10, 15],
        "NUMBER_OF_DRONES": [5, 10],
        "MOBILITY_ALPHA": [0.5, 0.85],
    },
}

