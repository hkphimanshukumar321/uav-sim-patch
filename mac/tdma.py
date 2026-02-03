import simpy
import random
from collections import defaultdict
from simulator.log import logger
from phy.phy import Phy
from utils import config
from utils.util_function import check_channel_availability


class Tdma:
    """
    Medium access control protocol: TDMA (Time Division Multiple Access) following IEEE 802.11
    
    The basic flow of TDMA is as follows:
        1) Time is divided into frames, and each frame is divided into time slots
        2) Each node is assigned one or more time slots within a frame
        3) A node can only transmit during its assigned time slot(s)
        4) The node must wait for its slot even if the channel is idle
        5) ACK is sent in the same slot or in a designated ACK period
        
    Main attributes:
        my_drone: the drone that installed the TDMA protocol
        simulator: the simulation platform that contains everything
        rng_mac: a Random class for generating random numbers
        env: simulation environment created by simpy
        phy: the installed physical layer
        channel_states: used to determine if the channel is idle
        enable_ack: use ack or not
        slot_assignment: dictionary mapping drone IDs to their assigned slots
        frame_duration: duration of one TDMA frame
        slot_duration: duration of one time slot
        current_slot: the current slot number in the frame
        
    References:
        
        [1] A. Boukerche, "Algorithms and Protocols for Wireless, Mobile Ad Hoc Networks,"
            Wiley-IEEE Press, 2008.
       
    
    Author: Based on CSMA/CA implementation
    Created at: 2025/1/13
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

        # TDMA-specific attributes with DYNAMIC FRAME SIZING
        # For throughput improvement: slots_per_frame = number of drones
        total_drones = len(self.simulator.drones)
        
        self.slot_duration = getattr(config, 'TDMA_SLOT_DURATION', 5200)  # optimized: packet + ACK + margin
        
        # DYNAMIC FRAME: 1 slot per drone for minimum wait time
        self.slots_per_frame = getattr(config, 'TDMA_SLOTS_PER_FRAME', None)
        if self.slots_per_frame is None or self.slots_per_frame == 0:
            self.slots_per_frame = total_drones  # Dynamic: match drone count
        
        self.frame_duration = self.slot_duration * self.slots_per_frame
        self.guard_time = getattr(config, 'TDMA_GUARD_TIME', 10)  # reduced from 50 to 10 us
        
        from simulator.log import logger
        logger.info(f'TDMA initialized: {total_drones} drones, {self.slots_per_frame} slots/frame, {self.frame_duration} us frame')
        
        # Dynamic TDMA attributes
        self.enable_dynamic_allocation = getattr(config, 'TDMA_ENABLE_DYNAMIC', True)
        self.queue_depth_history = defaultdict(list)
        self.dynamic_realloc_interval = 500 * 1e3  # 500ms between reallocation checks
        self.max_slots_per_drone = getattr(config, 'TDMA_MAX_SLOTS_PER_DRONE', 3)
        
        # Slot assignment - can be static or dynamic
        self.slot_assignment = self._initialize_slot_assignment()
        
        # Start frame synchronization process
        self.env.process(self._frame_sync())
        
        # Start dynamic reallocation process if enabled
        if self.enable_dynamic_allocation:
            self.env.process(self._dynamic_slot_reallocation())

    def _initialize_slot_assignment(self):
        """
        Initialize slot assignments for all drones
        Strategy: Round-robin assignment based on TDMA_SLOTS_PER_DRONE
        :return: dictionary mapping drone_id to list of assigned slot numbers
        """
        slot_assignment = {}
        total_drones = len(self.simulator.drones)
        slots_per_drone = getattr(config, 'TDMA_SLOTS_PER_DRONE', 1)
        
        # Assign slots to each drone
        for i, drone in enumerate(self.simulator.drones):
            assigned_slots = []
            for slot_idx in range(slots_per_drone):
                slot_num = (i + slot_idx * total_drones) % self.slots_per_frame
                assigned_slots.append(slot_num)
            slot_assignment[drone.identifier] = assigned_slots
        
        logger.info('TDMA slot assignment initialized: %s', slot_assignment)
        return slot_assignment

    def _frame_sync(self):
        """
        Maintain frame and slot synchronization
        This process runs continuously to track the current slot
        :return: none
        """
        while True:
            for slot_num in range(self.slots_per_frame):
                self.current_slot = slot_num
                logger.debug('At time: %s (us) ---- Frame slot: %s', self.env.now, slot_num)
                yield self.env.timeout(self.slot_duration)

    def _dynamic_slot_reallocation(self):
        """
        Periodically reallocate slots based on queue depths (like real TDMA systems).
        Drones with deeper queues get more slots, drones with empty queues give them up.
        This enables TDMA to adapt to traffic patterns like CSMA does.
        :return: none
        """
        while True:
            yield self.env.timeout(self.dynamic_realloc_interval)
            
            try:
                self._reallocate_slots()
            except Exception as e:
                logger.warning('At time: %s (us) ---- Dynamic reallocation failed: %s',
                             self.env.now, str(e))
    
    def _reallocate_slots(self):
        """
        Reallocate slots based on current queue depths.
        Strategy: Queue-aware allocation (busier drones get more slots)
        :return: none
        """
        # Collect queue depths from all drones
        queue_depths = {}
        total_queue = 0
        
        for drone in self.simulator.drones:
            queue_depth = drone.transmitting_queue.qsize()
            queue_depths[drone.identifier] = queue_depth
            total_queue += queue_depth
        
        if total_queue == 0:
            # All queues empty, use round-robin
            self._redistribute_slots_roundrobin()
            return
        
        # Allocate slots proportionally to queue depth
        new_assignment = {}
        available_slots = list(range(self.slots_per_frame))
        self.rng_mac.shuffle(available_slots)
        
        slot_idx = 0
        for drone in self.simulator.drones:
            queue_depth = queue_depths[drone.identifier]
            
            # Calculate how many slots this drone should get
            if total_queue > 0:
                proportion = queue_depth / total_queue
            else:
                proportion = 1.0 / len(self.simulator.drones)
            
            desired_slots = max(1, min(
                int(proportion * self.slots_per_frame),
                self.max_slots_per_drone
            ))
            
            assigned_slots = []
            for _ in range(min(desired_slots, len(available_slots))):
                if available_slots:
                    assigned_slots.append(available_slots.pop())
            
            if not assigned_slots and available_slots:
                assigned_slots.append(available_slots.pop())
            
            new_assignment[drone.identifier] = assigned_slots
        
        # Check if assignment changed
        if new_assignment != self.slot_assignment:
            self.slot_assignment = new_assignment
            logger.info('At time: %s (us) ---- TDMA dynamic reallocation (queue depths: %s): %s',
                       self.env.now, queue_depths, self.slot_assignment)
    
    def _redistribute_slots_roundrobin(self):
        """
        When all queues are empty, redistribute slots evenly (round-robin).
        :return: none
        """
        assignment = {}
        total_drones = len(self.simulator.drones)
        
        for i, drone in enumerate(self.simulator.drones):
            assigned_slots = []
            for slot_idx in range(self.max_slots_per_drone):
                slot_num = (i + slot_idx * total_drones) % self.slots_per_frame
                assigned_slots.append(slot_num)
            assignment[drone.identifier] = assigned_slots
        
        if assignment != self.slot_assignment:
            self.slot_assignment = assignment

    def _get_next_slot_start_time(self):
        """
        Calculate the start time of the next assigned slot for this drone
        :return: time to wait until next slot (in us)
        """
        my_slots = self.slot_assignment.get(self.my_drone.identifier, [])
        
        if not my_slots:
            logger.warning('UAV: %s has no assigned slots!', self.my_drone.identifier)
            return self.frame_duration  # wait one full frame
        
        current_time_in_frame = self.env.now % self.frame_duration
        current_slot = int(current_time_in_frame / self.slot_duration)
        
        # Find the next available slot
        for slot in sorted(my_slots):
            slot_start_time = slot * self.slot_duration
            if slot_start_time > current_time_in_frame:
                return slot_start_time - current_time_in_frame
        
        # If no slot found in current frame, get first slot in next frame
        next_slot = sorted(my_slots)[0]
        time_to_frame_end = self.frame_duration - current_time_in_frame
        time_to_next_slot = next_slot * self.slot_duration
        return time_to_frame_end + time_to_next_slot

    def mac_send(self, pkd):
        """
        Control when drone can send packet using TDMA
        :param pkd: the packet that needs to send
        :return: none
        """
        transmission_attempt = pkd.number_retransmission_attempt[self.my_drone.identifier]

        logger.info('At time: %s (us) ---- UAV: %s queues packet: %s for TDMA transmission (attempt: %s)',
                    self.env.now, self.my_drone.identifier, pkd.packet_id, transmission_attempt)

        # Wait for the assigned time slot
        time_to_slot = self._get_next_slot_start_time()
        
        logger.info('At time: %s (us) ---- UAV: %s must wait %s us for its time slot',
                    self.env.now, self.my_drone.identifier, time_to_slot)

        yield self.env.timeout(time_to_slot)

        # Add guard time at the beginning of the slot
        yield self.env.timeout(self.guard_time)

        if pkd.number_retransmission_attempt[self.my_drone.identifier] == 1:
            """
            Record the time when packet first attempts transmission
            """
            pkd.first_attempt_time = self.env.now

        key = ''.join(['mac_send', str(self.my_drone.identifier), '_', str(pkd.packet_id)])
        self.my_drone.mac_process_finish[key] = 1  # mark the process as "finished"

        # Occupy the channel to send packet (in TDMA, collision is avoided by design)
        with self.channel_states[self.my_drone.identifier].request() as req:
            yield req

            logger.info('At time: %s (us) ---- UAV: %s transmits in its TDMA slot (pkd id: %s)',
                        self.env.now, self.my_drone.identifier, pkd.packet_id)

            pkd.transmitting_start_time = self.env.now
            transmission_mode = pkd.transmission_mode

            if transmission_mode == 0:  # for unicast
                next_hop_id = pkd.next_hop_id

                pkd.increase_ttl()
                self.phy.unicast(pkd, next_hop_id)
                yield self.env.timeout(pkd.packet_length / config.BIT_RATE * 1e6)  # transmission delay

                logger.info('At time: %s (us) ---- UAV: %s starts to wait ACK for packet: %s',
                            self.env.now, self.my_drone.identifier, pkd.packet_id)

                if self.enable_ack:
                    key2 = ''.join(['wait_ack', str(self.my_drone.identifier), '_', str(pkd.packet_id)])

                    self.wait_ack_process = self.env.process(self.wait_ack(pkd))
                    self.wait_ack_process_dict[key2] = self.wait_ack_process
                    self.wait_ack_process_finish[key2] = 0

                    # Wait for ACK within the same slot (SIFS + ACK transmission time)
                    yield self.env.timeout(config.SIFS_DURATION + config.ACK_PACKET_LENGTH / config.BIT_RATE * 1e6)

            elif transmission_mode == 1:  # for broadcast
                pkd.increase_ttl()
                self.phy.broadcast(pkd)
                yield self.env.timeout(pkd.packet_length / config.BIT_RATE * 1e6)

        # Verify we didn't exceed slot duration
        time_in_slot = (self.env.now % self.frame_duration) % self.slot_duration
        if time_in_slot > self.slot_duration - self.guard_time:
            logger.warning('At time: %s (us) ---- UAV: %s transmission exceeded slot boundary!',
                          self.env.now, self.my_drone.identifier)

    def wait_ack(self, pkd):
        """
        If ACK is received within the specified time, the transmission is successful, otherwise,
        a re-transmission will be scheduled for the next available slot
        :param pkd: the data packet that waits for ACK
        :return: none
        """
        try:
            yield self.env.timeout(config.ACK_TIMEOUT)
            self.my_drone.routing_protocol.penalize(pkd)

            logger.info('At time: %s (us) ---- ACK timeout of packet: %s in TDMA slot',
                        self.env.now, pkd.packet_id)

            if pkd.number_retransmission_attempt[self.my_drone.identifier] < config.MAX_RETRANSMISSION_ATTEMPT:
                # Re-queue packet for transmission in next available slot
                yield self.env.process(self.my_drone.packet_coming(pkd))
            else:
                self.simulator.metrics.mac_delay.append((self.simulator.env.now - pkd.first_attempt_time) / 1e3)

                key2 = ''.join(['wait_ack', str(self.my_drone.identifier), '_', str(pkd.packet_id)])
                self.my_drone.mac_protocol.wait_ack_process_finish[key2] = 1

                logger.info('At time: %s (us) ---- Packet: %s is dropped after max retransmissions!',
                            self.env.now, pkd.packet_id)

        except simpy.Interrupt:
            # receive ACK in time
            logger.info('At time: %s (us) ---- UAV: %s receives the ACK for data packet: %s',
                        self.env.now, self.my_drone.identifier, pkd.packet_id)

    def wait_idle_channel(self, sender_drone, drones):
        """
        In TDMA, we don't need to wait for idle channel as slots are pre-assigned
        This method is kept for interface compatibility but does nothing in TDMA
        :param sender_drone: the drone that is about to send packet
        :param drones: a list, which contains all the drones in the simulation
        :return: none
        """
        # In TDMA, channel access is deterministic based on time slots
        # No carrier sensing is needed
        yield self.env.timeout(0)

    def listen(self, channel_states, drones, pkd):
        """
        In TDMA, continuous listening is not required during assigned slots
        This method is kept for interface compatibility but does nothing in TDMA
        :param channel_states: a dictionary, indicates the use of the channel by different drones
        :param drones: a list, contains all drones in the simulation
        :param pkd: the packet being transmitted
        :return: none
        """
        # In TDMA, no listening/carrier sensing is needed
        # Each drone transmits only in its assigned slot
        yield self.env.timeout(0)

    def update_slot_assignment(self, new_assignment):
        """
        Update slot assignments dynamically (for adaptive TDMA)
        :param new_assignment: new slot assignment dictionary
        :return: none
        """
        self.slot_assignment = new_assignment
        logger.info('At time: %s (us) ---- TDMA slot assignment updated: %s',
                    self.env.now, new_assignment)

    def get_slot_utilization(self):
        """
        Calculate the utilization of assigned slots
        :return: utilization percentage
        """
        my_slots = self.slot_assignment.get(self.my_drone.identifier, [])
        return (len(my_slots) / self.slots_per_frame) * 100