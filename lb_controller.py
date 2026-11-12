from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.addresses import IPAddr, EthAddr

log = core.getLogger()

class RoundRobinLoadBalancer(object):
    def __init__(self):
        core.openflow.addListeners(self)
        self.VIP = "10.0.0.100"
        self.VMAC = "00:00:00:00:01:00"

        # Backend server pool
        self.servers = [
            {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "port": 3},
            {"ip": "10.0.0.4", "mac": "00:00:00:00:00:04", "port": 4},
            {"ip": "10.0.0.5", "mac": "00:00:00:00:00:05", "port": 5},
        ]
        self.rr_index = 0

    def _handle_ConnectionUp(self, event):
        log.info("Switch s1 connected. Installing baseline forwarding rules...")

        # Host MAC-to-Port direct mapping rules
        host_macs = [
            (1, "00:00:00:00:00:01"),
            (2, "00:00:00:00:00:02"),
            (3, "00:00:00:00:00:03"),
            (4, "00:00:00:00:00:04"),
            (5, "00:00:00:00:00:05")
        ]
        for port_num, mac_str in host_macs:
            msg = of.ofp_flow_mod()
            msg.priority = 10
            msg.match.dl_dst = EthAddr(mac_str)
            msg.actions.append(of.ofp_action_output(port=port_num))
            event.connection.send(msg)

        # Intercept all TCP traffic aimed at VIP
        msg_lb = of.ofp_flow_mod()
        msg_lb.priority = 50
        msg_lb.match.dl_type = 0x0800
        msg_lb.match.nw_proto = 6
        msg_lb.match.nw_dst = IPAddr(self.VIP)
        msg_lb.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))
        event.connection.send(msg_lb)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        if not packet.parsed:
            return

        ip_pkt = packet.find('ipv4')
        tcp_pkt = packet.find('tcp')

        if ip_pkt and tcp_pkt and str(ip_pkt.dstip) == self.VIP:
            server = self.servers[self.rr_index]
            self.rr_index = (self.rr_index + 1) % len(self.servers)
            server_ip = IPAddr(server['ip'])

            log.info("New TCP flow -> Round-Robin picked %s", server['ip'])

            in_port = event.port
            client_mac = str(packet.src)

            # 1. Reverse rule (Server -> Client)
            rule_rev = of.ofp_flow_mod()
            rule_rev.priority = 100
            rule_rev.idle_timeout = 10
            rule_rev.match.dl_type = 0x0800
            rule_rev.match.nw_proto = 6
            rule_rev.match.nw_src = server_ip
            rule_rev.match.nw_dst = ip_pkt.srcip
            rule_rev.match.tp_src = tcp_pkt.dstport
            rule_rev.match.tp_dst = tcp_pkt.srcport
            rule_rev.actions.append(of.ofp_action_dl_addr.set_src(EthAddr(self.VMAC)))
            rule_rev.actions.append(of.ofp_action_dl_addr.set_dst(EthAddr(client_mac)))
            rule_rev.actions.append(of.ofp_action_nw_addr.set_src(IPAddr(self.VIP)))
            rule_rev.actions.append(of.ofp_action_output(port=in_port))
            event.connection.send(rule_rev)

            # 2. Forward rule (Client -> Server)
            rule_fwd = of.ofp_flow_mod()
            rule_fwd.priority = 100
            rule_fwd.idle_timeout = 10
            rule_fwd.match.dl_type = 0x0800
            rule_fwd.match.nw_proto = 6
            rule_fwd.match.nw_src = ip_pkt.srcip
            rule_fwd.match.nw_dst = IPAddr(self.VIP)
            rule_fwd.match.tp_src = tcp_pkt.srcport
            rule_fwd.match.tp_dst = tcp_pkt.dstport
            rule_fwd.actions.append(of.ofp_action_dl_addr.set_dst(EthAddr(server['mac'])))
            rule_fwd.actions.append(of.ofp_action_nw_addr.set_dst(server_ip))
            rule_fwd.actions.append(of.ofp_action_output(port=server['port']))
            event.connection.send(rule_fwd)

            # 3. PacketOut: use of.NO_BUFFER
            pkt_out = of.ofp_packet_out()
            if event.ofp.buffer_id != of.NO_BUFFER:
                pkt_out.buffer_id = event.ofp.buffer_id
            else:
                pkt_out.data = event.data
            pkt_out.in_port = in_port
            pkt_out.actions.append(of.ofp_action_dl_addr.set_dst(EthAddr(server['mac'])))
            pkt_out.actions.append(of.ofp_action_nw_addr.set_dst(server_ip))
            pkt_out.actions.append(of.ofp_action_output(port=server['port']))
            event.connection.send(pkt_out)

def launch():
    core.registerNew(RoundRobinLoadBalancer)
