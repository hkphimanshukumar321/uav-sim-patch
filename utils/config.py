import logging
from utils.ieee_802_11 import IeeeStandard

IEEE_802_11 = IeeeStandard().b_802_11

# --------------------- simulation parameters --------------------- #
MAP_LENGTH = 600  # m, length of the map
MAP_WIDTH = 600  # m, width of the map
MAP_HEIGHT = 100  # m, height of the map
SIM_TIME = 30 * 1e6  # us, total simulation time
NUMBER_OF_DRONES = 10  # number of drones in the network
GRID_RESOLUTION = 20  # grid the map for path planning
STATIC_CASE = 0  # whether to simulate a static network
HETEROGENEOUS = 0  # heterogeneous network support (in terms of speed)
LOGGING_LEVEL = logging.INFO  # whether to print the detail information during simulation

# ---------- hardware parameters of drone (rotary-wing) -----------#
PROFILE_DRAG_COEFFICIENT = 0.012
AIR_DENSITY = 1.225  # kg/m^3
ROTOR_SOLIDITY = 0.05  # defined as the ratio of the total blade area to disc area
ROTOR_DISC_AREA = 0.79  # m^2
BLADE_ANGULAR_VELOCITY = 400  # radians/second
ROTOR_RADIUS = 0.5  # m
INCREMENTAL_CORRECTION_FACTOR = 0.1
AIRCRAFT_WEIGHT = 100  # Newton
ROTOR_BLADE_TIP_SPEED = 500
MEAN_ROTOR_VELOCITY = 7.2  # mean rotor induced velocity in hover
FUSELAGE_DRAG_RATIO = 0.3
INITIAL_ENERGY = 20 * 1e3  # in joule
ENERGY_THRESHOLD = 2000  # in joule
MAX_QUEUE_SIZE = 200  # maximum size of drone's queue

# ----------------------- radio parameters ----------------------- #
TRANSMITTING_POWER = 0.1  # in Watt
LIGHT_SPEED = 3 * 1e8  # light speed (m/s)
CARRIER_FREQUENCY = IEEE_802_11['carrier_frequency']  # carrier frequency (Hz)
NOISE_POWER = 4 * 1e-11  # noise power (Watt)
RADIO_SWITCHING_TIME = 100  # us, the switching time of the transceiver mode
SNR_THRESHOLD = IEEE_802_11['snr_threshold']

# ---------------------- packet parameters ----------------------- #
VARIABLE_PAYLOAD_LENGTH = 0  # whether to consider random payload length of data packet
AVERAGE_PAYLOAD_LENGTH = 1024 * 8  # in bit, 1024 bytes
MAXIMUM_PAYLOAD_VARIATION = 1600  # in bit
MAX_TTL = NUMBER_OF_DRONES + 1  # maximum time-to-live value
PACKET_LIFETIME = 10 * 1e6  # 10s
IP_HEADER_LENGTH = 20 * 8  # header length in network layer, 20 byte
MAC_HEADER_LENGTH = 14 * 8  # header length in mac layer, 14 byte

# ---------------------- physical layer -------------------------- #
PATH_LOSS_EXPONENT = 2  # for large-scale fading
PLCP_PREAMBLE = 128 + 16  # including synchronization and SFD (start frame delimiter)
PLCP_HEADER = 8 + 8 + 16 + 16  # including signal, service, length and HEC (header error check)
PHY_HEADER_LENGTH = PLCP_PREAMBLE + PLCP_HEADER  # header length in physical layer, PLCP preamble + PLCP header

ACK_HEADER_LENGTH = 16 * 8  # header length of ACK packet, 16 byte
ACK_PACKET_LENGTH = ACK_HEADER_LENGTH + 14 * 8  # bit

HELLO_PACKET_PAYLOAD_LENGTH = 256  # bit
HELLO_PACKET_LENGTH = IP_HEADER_LENGTH + MAC_HEADER_LENGTH + PHY_HEADER_LENGTH + HELLO_PACKET_PAYLOAD_LENGTH

# define the range of "id" of different types of packets
"""
|--------------|--------------|--------------|--------------|--------------|
0            10000          20000          30000          40000    
|   data pkt   |   hello pkt  |    ack pkt   |    vf pkt    |   grad msg   |
"""
GL_ID_DATA_PACKET = 0
GL_ID_HELLO_PACKET = 10000
GL_ID_ACK_PACKET = 20000
GL_ID_VF_PACKET = 30000
GL_ID_GRAD_MESSAGE = 40000

# ------------------ physical layer parameters ------------------- #
BIT_RATE = IEEE_802_11['bit_rate']
BIT_TRANSMISSION_TIME = 1/BIT_RATE * 1e6
BANDWIDTH = IEEE_802_11['bandwidth']
SENSING_RANGE = 750  # in meter, defines the area where a sending node can disturb a transmission from a third node

# --------------------- mac layer parameters --------------------- #
SLOT_DURATION = IEEE_802_11['slot_duration']
SIFS_DURATION = IEEE_802_11['SIFS']
DIFS_DURATION = SIFS_DURATION + (2 * SLOT_DURATION)
CW_MIN = 31  # initial contention window size
ACK_TIMEOUT = ACK_PACKET_LENGTH / BIT_RATE * 1e6 + SIFS_DURATION + 100  # maximum waiting time for ACK, in us
MAX_RETRANSMISSION_ATTEMPT = 3                  # reduced for TDMA to cause sharper drop at high traffic

# ------------------- experiment knobs (added for sweeps) ------------------- #
# Traffic generation (per-drone)
TRAFFIC_PATTERN = "Poisson"   # "Poisson" or "Uniform"
TRAFFIC_RATE = 10            # packets/sec per drone when TRAFFIC_PATTERN == "Poisson"
UNIFORM_IAT_US = (500000, 505000)  # microseconds when TRAFFIC_PATTERN == "Uniform"

# MAC mode control
MAC_MODE = "TDMA"  # "TDMA", "CSMA", "ALOHA", "STDMA", or "ADAPTIVE"


# ------------------- TDMA specific parameters ------------------- #
# NOTE: Slot must be larger than packet transmission time!
# At 2 Mbps (802.11b), 1KB packet = 8192 bits / 2Mbps = 4096 µs
# So slot must be > 4096 + SIFS + ACK_time ≈ 5000 µs
TDMA_SLOT_DURATION = 5000                        # us, duration of one time slot
TDMA_SLOTS_PER_FRAME = 20                        # number of slots per frame (increased for more capacity)
TDMA_GUARD_TIME = 50                             # us, guard time between slots
TDMA_SLOTS_PER_DRONE = 1                         # slots assigned per drone (causes saturation at high traffic)

# Dynamic TDMA (queue-aware slot allocation) - like real industrial TDMA systems
TDMA_ENABLE_DYNAMIC = True                       # enable dynamic slot reallocation based on queue depth
TDMA_MAX_SLOTS_PER_DRONE = 3                     # maximum slots a drone can claim under dynamic allocation
TDMA_REALLOC_INTERVAL = 500000                   # us (500ms), period for reallocation checks


# ------------------- CSMA/CA specific parameters ------------------- #
# CW_MIN is defined in mac layer parameters (line 84)
# CW_MAX = CW_MIN * 2^(MAX_RETRANSMISSION_ATTEMPT-1)
CSMA_ENABLE_RTS_CTS = False                      # enable RTS/CTS handshake

# ------------------- ALOHA specific parameters ------------------- #
ALOHA_RANDOM_BACKOFF_BASE = 500                  # us, base for random backoff

# ------------------- STDMA specific parameters ------------------- #
# Self-organizing TDMA - dynamic slot allocation
STDMA_RESERVATION_TIMEOUT = 5                    # frames before slot reallocation
STDMA_MAX_SLOTS_PER_DRONE = 3                    # max slots a drone can claim


# Batch mode helpers
ENABLE_PLOTS = False
ENABLE_TIME_PRINTS = False

# ------------------- mobility model parameters ------------------- #
# Gauss-Markov mobility model (gauss_markov_3d.py)
MOBILITY_POSITION_UPDATE_INTERVAL = 1 * 1e5      # us (0.1s) - how often position updates
MOBILITY_DIRECTION_UPDATE_INTERVAL = 5 * 1e5    # us (0.5s) - how often direction changes
MOBILITY_ALPHA = 0.85                            # 0-1, controls randomness (1=deterministic, 0=random)
MOBILITY_BOUNDARY_BUFFER = 1                     # meters, distance from boundary to start rebounding

# ------------------- drone dynamic behavior parameters ------------------- #
# Mobility pattern switching (drone.py)
MOBILITY_SWITCH_INTERVAL = 30 * 1e6              # us (30s) - interval between mobility pattern switches
CIRCULAR_PATTERN_DURATION = 15 * 1e6             # us (15s) - duration of circular mobility pattern
CIRCULAR_RADIUS = 50                             # meters, radius of circular movement pattern

# Obstacle detection and avoidance (drone.py)
OBSTACLE_DETECTION_RANGE = 30                    # meters, range for detecting obstacles
MIN_OBSTACLE_DISTANCE = 10                       # meters, minimum safe distance from obstacles

# Adaptive MAC switching (drone.py)
MAC_SWITCH_INTERVAL = 20 * 1e6                   # us (20s) - interval for MAC protocol evaluation
CONTENTION_WINDOW = 5 * 1e6                      # us (5s) - window for measuring contention level
CONTENTION_THRESHOLD_HIGH = 0.7                  # 0-1, switch to TDMA above this contention level
CONTENTION_THRESHOLD_LOW = 0.3                   # 0-1, switch to CSMA below this contention level

# ------------------- channel model parameters ------------------- #
# Path loss model selection (large_scale_fading.py)
PATH_LOSS_MODEL = "general"                      # "general" or "probabilistic_los"
# Probabilistic LoS parameters (only used when PATH_LOSS_MODEL = "probabilistic_los")
ETA_LOS = 0.1                                    # LoS additional loss (dB)
ETA_NLOS = 21                                    # NLoS additional loss (dB)
PROB_LOS_A = 4.88                                # Environment parameter a
PROB_LOS_B = 0.429                               # Environment parameter b

# ------------------- randomness control ------------------- #
# Seeds for reproducibility (use -1 for random seed)
MASTER_SEED = 2025                               # Master seed for all random generators
ENABLE_SEED_VARIATION = False                    # If True, add drone ID to seed for per-drone variation
