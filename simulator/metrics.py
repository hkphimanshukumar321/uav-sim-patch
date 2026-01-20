import numpy as np
from collections import defaultdict
from openpyxl import load_workbook


class Metrics:
    """
    Tools for statistics of network performance

    1. Packet Delivery Ratio (PDR): is the ratio of number of packets received at the destinations to the number
       of packets sent from the sources
    2. Average end-to-end (E2E) delay: is the time a packet takes to route from a source to its destination through
       the network. It is the time the data packet reaches the destination minus the time the data packet was generated
       in the source node
    3. Routing Load: is calculated as the ratio between the numbers of control Packets transmitted
       to the number of packets actually received. NRL can reflect the average number of control packets required to
       successfully transmit a data packet and reflect the efficiency of the routing protocol
    4. Throughput: it can be defined as a measure of how fast the data is sent from its source to its intended
       destination without loss. In our simulation, each time the destination receives a data packet, the throughput is
       calculated and finally averaged
    5. Hop count: used to record the number of router output ports through which the packet should pass.

    References:
        [1] Rani. N, Sharma. P, Sharma. P., "Performance Comparison of Various Routing Protocols in Different Mobility
            Models," in arXiv preprint arXiv:1209.5507, 2012.
        [2] Gulati M K, Kumar K. "Performance Comparison of Mobile Ad Hoc Network Routing Protocols," International
            Journal of Computer Networks & Communications. vol. 6, no. 2, pp. 127, 2014.

    Author: Zihao Zhou, eezihaozhou@gmail.com
    Created at: 2024/1/11
    Updated at: 2025/4/22
    """

    def __init__(self, simulator):
        self.simulator = simulator

        self.control_packet_num = 0

        self.datapacket_generated = set()  # all data packets generated
        self.datapacket_arrived = set()  # all data packets that arrives the destination
        self.datapacket_generated_num = 0

        self.delivery_time = []
        self.deliver_time_dict = defaultdict()

        self.throughput = []
        self.throughput_dict = defaultdict()

        self.hop_cnt = []
        self.hop_cnt_dict = defaultdict()

        self.mac_delay = []

        self.collision_num = 0

    def calculate_metrics(self, received_packet):
        """Calculate the corresponding metrics when the destination receives a data packet successfully"""
        latency = self.simulator.env.now - received_packet.creation_time  # in us

        self.deliver_time_dict[received_packet.packet_id] = latency
        self.throughput_dict[received_packet.packet_id] = received_packet.packet_length / (latency / 1e6)
        self.hop_cnt_dict[received_packet.packet_id] = received_packet.get_current_ttl()
        self.datapacket_arrived.add(received_packet.packet_id)

    def print_metrics(self):
        # calculate the average end-to-end delay
        e2e_delay = np.mean(list(self.deliver_time_dict.values())) / 1e3

        # calculate the packet delivery ratio
        pdr = len(self.datapacket_arrived) / self.datapacket_generated_num * 100  # in %

        # calculate the throughput
        throughput = np.mean(list(self.throughput_dict.values())) / 1e3

        # calculate the hop count
        hop_cnt = np.mean(list(self.hop_cnt_dict.values()))

        # calculate the routing load
        rl = self.control_packet_num / len(self.datapacket_arrived)

        # channel access delay
        average_mac_delay = np.mean(self.mac_delay)

        print('Totally send: ', self.datapacket_generated_num, ' data packets')
        print('Packet delivery ratio is: ', pdr, '%')
        print('Average end-to-end delay is: ', e2e_delay, 'ms')
        print('Routing load is: ', rl)
        print('Average throughput is: ', throughput, 'Kbps')
        print('Average hop count is: ', hop_cnt)
        print('Collision num is: ', self.collision_num)
        print('Average mac delay is: ', average_mac_delay, 'ms')


    def to_dict(self):
        """Export key metrics as a dict (batch-friendly)."""
        arrived = len(self.datapacket_arrived)
        sent = int(self.datapacket_generated_num)

        if arrived > 0:
            e2e_delay_ms = float(np.mean(list(self.deliver_time_dict.values())) / 1e3)
            throughput_kbps = float(np.mean(list(self.throughput_dict.values())) / 1e3)
            hop_cnt = float(np.mean(list(self.hop_cnt_dict.values())))
            routing_load = float(self.control_packet_num / arrived)
        else:
            e2e_delay_ms = float('nan')
            throughput_kbps = 0.0
            hop_cnt = float('nan')
            routing_load = float('inf')

        pdr_percent = (arrived / sent * 100.0) if sent > 0 else 0.0
        average_mac_delay_ms = float(np.mean(self.mac_delay)) if len(self.mac_delay) > 0 else float('nan')

        return {
            'sent': sent,
            'arrived': arrived,
            'pdr_percent': pdr_percent,
            'e2e_delay_ms': e2e_delay_ms,
            'routing_load': routing_load,
            'throughput_kbps': throughput_kbps,
            'hop_count': hop_cnt,
            'collisions': int(self.collision_num),
            'mac_delay_ms': average_mac_delay_ms,
        }
