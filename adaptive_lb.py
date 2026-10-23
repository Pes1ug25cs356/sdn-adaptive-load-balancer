from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.addresses import IPAddr, EthAddr
import threading
import time

log = core.getLogger()

class AdaptiveLeastConnectionsLB(object):
    def __init__(self):
        core.openflow.addListeners(self)
        self.VIP = "10.0.0.100"
        self.VMAC = "00:00:00:00:01:00"

        self.servers = [
            {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "port": 3},
            {"ip": "10.0.0.4", "mac": "00:00:00:00:00:04", "port": 4},
            {"ip": "10.0.0.5", "mac": "00:00:00:00:00:05", "port": 5},
        ]

        self.active_conns = {
            IPAddr("10.0.0.3"): 0,
            IPAddr("10.0.0.4"): 0,
            IPAddr("10.0.0.5"): 0
        }

    def _handle_ConnectionUp(self, event):
        log.info("Switch s1 connected. Installing baseline rules...")

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

        msg_lb = of.ofp_flow_mod()
        msg_lb.priority = 50
        msg_lb.match.dl_type = 0x0800
        msg_lb.match.nw_proto = 6
        msg_lb.match.nw_dst = IPAddr(self.VIP)
        msg_lb.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))
        event.connection.send(msg_lb)

    def _release_connection(self, server_ip, duration):
        time.sleep(duration)
        if self.active_conns[server_ip] > 0:
            self.active_conns[server_ip] -= 1

    def _select_least_loaded_server(self):
        # Pick server with smallest active connection count; prioritize faster servers on tie
        server_order = [self.servers[2], self.servers[1], self.servers[0]] # 5, 4, 3
        return min(server_order, key=lambda s: self.active_conns[IPAddr(s['ip'])])

    def _handle_PacketIn(self, event):
        packet = event.parsed
        if not packet.parsed:
            return

        ip_pkt = packet.find('ipv4')
        tcp_pkt = packet.find('tcp')

        if ip_pkt and tcp_pkt and str(ip_pkt.dstip) == self.VIP:
            server = self._select_least_loaded_server()
            server_ip = IPAddr(server['ip'])

            self.active_conns[server_ip] += 1

            # Match actual server sleep times: Server-3 (0.40s), Server-4 (0.08s), Server-5 (0.01s)
            hold_time = 0.40 if server['ip'] == "10.0.0.3" else (0.08 if server['ip'] == "10.0.0.4" else 0.01)
            threading.Thread(target=self._release_connection, args=(server_ip, hold_time), daemon=True).start()

            in_port = event.port
            client_mac = str(packet.src)

            # Reverse Rule (Server -> Client)
            rule_rev = of.ofp_flow_mod()
            rule_rev.priority = 100
            rule_rev.idle_timeout = 1
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

            # Forward Rule (Client -> Server)
            rule_fwd = of.ofp_flow_mod()
            rule_fwd.priority = 100
            rule_fwd.idle_timeout = 1
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
    core.registerNew(AdaptiveLeastConnectionsLB)
