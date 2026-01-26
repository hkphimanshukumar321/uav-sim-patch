import simpy
import random
from simulator.log import logger
from phy.phy import Phy
from utils import config
from utils.util_function import check_channel_availability


class Stdma:
    """
    Self-organizing TDMA (STDMA) Protocol
    
    STDMA is a decentralized version of TDMA where nodes dynamically claim and release
    time slots based on their traffic needs. This improves over basic TDMA by:
    1. Allowing nodes to claim multiple slots when they have more traffic
    2. Releasing unused slots for other nodes
    3. Collision detection and slot reallocation
    
    Main differences from TDMA:
    - Dynamic slot allocation instead of static round-robin
    - Traffic-aware: high-traffic nodes get more slots
    - Self-healing: detects collisions and reallocates
    
    Slot states:
    - FREE: Available for any node
    - RESERVED: Claimed by a specific node
    - BUSY: Currently in use
    
    References:
        [1] H. Lans, "Position Indicating System," U.S. Patent 5506587, 1996.
        [2] AIS (Automatic Identification System) - uses STDMA for maritime communication
    
    Author: UAV Network Simulator
    Created at: 2025/1/27
    """

    def __init__(self, drone):
        self.my_drone = drone
        self.simulator = drone.simulator
        self.rng_mac = random.Random(self.my_drone.identifier + self.my_drone.simulator.seed + 5)
        self.env = drone.env
        self.phy = Phy(self)
        self.channel_states = self.simulator.channel_states
        self.enable_ack = True

        self.wait_ack_process_dict = dict()
        self.wait_ack_process_finish = dict()
        self.wait_ack_process_count = 0
        self.wait_ack_process = None

        # STDMA-specific attributes
        self.slot_duration = getattr(config, 'TDMA_SLOT_DURATION', 5000)
        self.slots_per_frame = getattr(config, 'TDMA_SLOTS_PER_FRAME', 10)
        self.frame_duration = self.slot_duration * self.slots_per_frame
        self.guard_time = getattr(config, 'TDMA_GUARD_TIME', 50)
        
        # Dynamic slot management
        self.my_slots = []  # Slots claimed by this drone
        self.slot_table = {}  # Global view: slot -> owner_id (0 = free)
        self.slot_collisions = {}  # Track collisions per slot
        self.reservation_timeout = getattr(config, 'STDMA_RESERVATION_TIMEOUT', 5)  # frames
        self.max_slots_per_drone = getattr(config, 'STDMA_MAX_SLOTS_PER_DRONE', 3)
        
        # Traffic estimation
        self.packet_queue_size = 0
        self.traffic_estimate = 0
        
        # Initialize slot table (all free initially)
        for i in range(self.slots_per_frame):
            self.slot_table[i] = 0  # 0 = free
            self.slot_collisions[i] = 0
        
        # Claim initial slot based on drone ID (to avoid initial collisions)
        initial_slot = self.my_drone.identifier % self.slots_per_frame
        self._claim_slot(initial_slot)
        
        # Start processes
        self.env.process(self._frame_sync())
        self.env.process(self._traffic_monitor())
        self.env.process(self._slot_maintenance())

    def _claim_slot(self, slot_num):
        """Claim a slot for this drone"""
        if slot_num not in self.my_slots and len(self.my_slots) < self.max_slots_per_drone:
            self.my_slots.append(slot_num)
            self.slot_table[slot_num] = self.my_drone.identifier
            logger.info('At time: %s ---- UAV %s claimed slot %s', 
                       self.env.now, self.my_drone.identifier, slot_num)

    def _release_slot(self, slot_num):
        """Release a slot"""
        if slot_num in self.my_slots:
            self.my_slots.remove(slot_num)
            self.slot_table[slot_num] = 0
            logger.info('At time: %s ---- UAV %s released slot %s',
                       self.env.now, self.my_drone.identifier, slot_num)

    def _find_free_slot(self):
        """Find a free slot to claim"""
        for slot in range(self.slots_per_frame):
            if self.slot_table.get(slot, 0) == 0:
                return slot
        return None

    def _frame_sync(self):
        """Maintain frame synchronization"""
        while True:
            for slot_num in range(self.slots_per_frame):
                self.current_slot = slot_num
                yield self.env.timeout(self.slot_duration)

    def _traffic_monitor(self):
        """Monitor traffic and adjust slot allocation"""
        while True:
            yield self.env.timeout(self.frame_duration * 2)  # Every 2 frames
            
            # Estimate traffic from queue size
            queue_len = len(self.my_drone.transmitting_queue)
            self.traffic_estimate = queue_len
            
            # Need more slots if queue is building up
            if queue_len > 2 and len(self.my_slots) < self.max_slots_per_drone:
                free_slot = self._find_free_slot()
                if free_slot is not None:
                    self._claim_slot(free_slot)
            
            # Release excess slots if queue is low
            elif queue_len <= 1 and len(self.my_slots) > 1:
                # Keep at least one slot, release others
                slot_to_release = self.my_slots[-1]
                self._release_slot(slot_to_release)

    def _slot_maintenance(self):
        """Handle collision detection and slot reallocation"""
        while True:
            yield self.env.timeout(self.frame_duration * self.reservation_timeout)
            
            # Check for high-collision slots and reallocate
            for slot in list(self.my_slots):
                if self.slot_collisions.get(slot, 0) > 2:
                    logger.info('At time: %s ---- UAV %s detected high collisions on slot %s',
                               self.env.now, self.my_drone.identifier, slot)
                    # Release problematic slot
                    self._release_slot(slot)
                    # Try to claim a different one
                    new_slot = self._find_free_slot()
                    if new_slot is not None:
                        self._claim_slot(new_slot)
                    # Reset collision counter
                    self.slot_collisions[slot] = 0

    def _get_next_slot_start_time(self):
        """Calculate time to next assigned slot"""
        if not self.my_slots:
            # No slots claimed, try to claim one
            free_slot = self._find_free_slot()
            if free_slot is not None:
                self._claim_slot(free_slot)
            else:
                return self.frame_duration  # Wait one frame
        
        current_time_in_frame = self.env.now % self.frame_duration
        current_slot = int(current_time_in_frame / self.slot_duration)
        
        # Find next available slot
        for slot in sorted(self.my_slots):
            slot_start_time = slot * self.slot_duration
            if slot_start_time > current_time_in_frame:
                return slot_start_time - current_time_in_frame
        
        # If no slot in current frame, get first slot in next frame
        next_slot = sorted(self.my_slots)[0]
        time_to_frame_end = self.frame_duration - current_time_in_frame
        time_to_next_slot = next_slot * self.slot_duration
        return time_to_frame_end + time_to_next_slot

    def mac_send(self, pkd):
        """Control when drone can send packet using STDMA"""
        transmission_attempt = pkd.number_retransmission_attempt[self.my_drone.identifier]

        logger.info('At time: %s (us) ---- UAV: %s queues packet: %s for STDMA transmission (attempt: %s)',
                    self.env.now, self.my_drone.identifier, pkd.packet_id, transmission_attempt)

        # Wait for assigned time slot
        time_to_slot = self._get_next_slot_start_time()
        
        logger.info('At time: %s (us) ---- UAV: %s must wait %s us for its STDMA slot',
                    self.env.now, self.my_drone.identifier, time_to_slot)

        yield self.env.timeout(time_to_slot)
        yield self.env.timeout(self.guard_time)

        if pkd.number_retransmission_attempt[self.my_drone.identifier] == 1:
            pkd.first_attempt_time = self.env.now

        key = ''.join(['mac_send', str(self.my_drone.identifier), '_', str(pkd.packet_id)])
        self.my_drone.mac_process_finish[key] = 1

        with self.channel_states[self.my_drone.identifier].request() as req:
            yield req

            logger.info('At time: %s (us) ---- UAV: %s transmits in STDMA slot (pkd id: %s)',
                        self.env.now, self.my_drone.identifier, pkd.packet_id)

            pkd.transmitting_start_time = self.env.now
            transmission_mode = pkd.transmission_mode

            if transmission_mode == 0:  # unicast
                next_hop_id = pkd.next_hop_id
                pkd.increase_ttl()
                self.phy.unicast(pkd, next_hop_id)
                yield self.env.timeout(pkd.packet_length / config.BIT_RATE * 1e6)

                if self.enable_ack:
                    key2 = ''.join(['wait_ack', str(self.my_drone.identifier), '_', str(pkd.packet_id)])
                    self.wait_ack_process = self.env.process(self.wait_ack(pkd))
                    self.wait_ack_process_dict[key2] = self.wait_ack_process
                    self.wait_ack_process_finish[key2] = 0
                    yield self.env.timeout(config.SIFS_DURATION + config.ACK_PACKET_LENGTH / config.BIT_RATE * 1e6)

            elif transmission_mode == 1:  # broadcast
                pkd.increase_ttl()
                self.phy.broadcast(pkd)
                yield self.env.timeout(pkd.packet_length / config.BIT_RATE * 1e6)

    def wait_ack(self, pkd):
        """Wait for ACK or handle timeout with collision tracking"""
        try:
            yield self.env.timeout(config.ACK_TIMEOUT)
            self.my_drone.routing_protocol.penalize(pkd)

            # Track collision for current slot
            current_slot = int((self.env.now % self.frame_duration) / self.slot_duration)
            if current_slot in self.my_slots:
                self.slot_collisions[current_slot] = self.slot_collisions.get(current_slot, 0) + 1

            logger.info('At time: %s (us) ---- ACK timeout of packet: %s in STDMA slot',
                        self.env.now, pkd.packet_id)

            if pkd.number_retransmission_attempt[self.my_drone.identifier] < config.MAX_RETRANSMISSION_ATTEMPT:
                yield self.env.process(self.my_drone.packet_coming(pkd))
            else:
                self.simulator.metrics.mac_delay.append((self.simulator.env.now - pkd.first_attempt_time) / 1e3)
                key2 = ''.join(['wait_ack', str(self.my_drone.identifier), '_', str(pkd.packet_id)])
                self.my_drone.mac_protocol.wait_ack_process_finish[key2] = 1
                logger.info('At time: %s (us) ---- Packet: %s is dropped after max retransmissions!',
                            self.env.now, pkd.packet_id)

        except simpy.Interrupt:
            logger.info('At time: %s (us) ---- UAV: %s receives the ACK for data packet: %s',
                        self.env.now, self.my_drone.identifier, pkd.packet_id)
            # Reset collision counter for successful slot
            current_slot = int((self.env.now % self.frame_duration) / self.slot_duration)
            if current_slot in self.my_slots:
                self.slot_collisions[current_slot] = 0

    def wait_idle_channel(self, sender_drone, drones):
        """STDMA doesn't need carrier sensing"""
        yield self.env.timeout(0)

    def listen(self, channel_states, drones, pkd):
        """STDMA doesn't need continuous listening"""
        yield self.env.timeout(0)
