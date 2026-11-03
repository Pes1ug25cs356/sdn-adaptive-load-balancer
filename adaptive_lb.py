from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.addresses import IPAddr, EthAddr
import threading
import time
from pox.lib.recoco import Timer
import json
import os

log = core.getLogger()

TELEMETRY_FILE = "/tmp/sdn_telemetry.json"
HEALTH_FILE = "/tmp/server_status.json"
CONFIG_FILE = "/tmp/sdn_config.json"
RESET_FILE = "/tmp/sdn_reset.flag"

class AdaptiveLeastConnectionsLB(object):
    def __init__(self):
        core.openflow.addListeners(self)
        self.VIP = "10.0.0.100"
        self.VMAC = "00:00:00:00:01:00"

        self.servers = [
            {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "port": 3, "name": "Server-3 (Slow)", "delay": 0.40},
            {"ip": "10.0.0.4", "mac": "00:00:00:00:00:04", "port": 4, "name": "Server-4 (Medium)", "delay": 0.08},
            {"ip": "10.0.0.5", "mac": "00:00:00:00:00:05", "port": 5, "name": "Server-5 (Fast)", "delay": 0.01},
        ]

        self.active_conns = {IPAddr("10.0.0.3"): 0, IPAddr("10.0.0.4"): 0, IPAddr("10.0.0.5"): 0}
        self.request_counts = {"10.0.0.3": 0, "10.0.0.4": 0, "10.0.0.5": 0}
        self.recent_events = []
        self.port_bytes_previous = {}
        self.port_rates_mbps = {3: 0.0, 4: 0.0, 5: 0.0}
        self.stats_connection = None
        self.total_requests = 0

        self._sync_initial_config()

    def _sync_initial_config(self):
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "w") as f:
                json.dump({"servers": self.servers}, f)

    def _check_signals(self):
        # 1. Check for Reset Command
        if os.path.exists(RESET_FILE):
            try:
                os.remove(RESET_FILE)
                self.total_requests = 0
                self.recent_events = []
                for s in self.servers:
                    self.active_conns[IPAddr(s["ip"])] = 0
                    self.request_counts[s["ip"]] = 0
                log.info("TELEMETRY METRICS RESET TO 0 BY USER")
                self._export_telemetry()
            except Exception:
                pass

        # 2. Check for Dynamic Servers
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    configured = data.get("servers", [])
                    current_ips = {s["ip"] for s in self.servers}

                    for cs in configured:
                        if cs["ip"] not in current_ips:
                            log.info(f"Dynamic Node Added: {cs['name']} ({cs['ip']}) on Port {cs['port']}")
                            self.servers.append(cs)
                            ip_obj = IPAddr(cs["ip"])
                            self.active_conns[ip_obj] = 0
                            self.request_counts[cs["ip"]] = 0
                            self.port_rates_mbps[cs["port"]] = 0.0

                            if self.stats_connection:
                                msg = of.ofp_flow_mod()
                                msg.priority = 10
                                msg.match.dl_dst = EthAddr(cs["mac"])
                                msg.actions.append(of.ofp_action_output(port=cs["port"]))
                                self.stats_connection.send(msg)
            except Exception:
                pass

    def _export_telemetry(self):
        health = {}
        if os.path.exists(HEALTH_FILE):
            try:
                with open(HEALTH_FILE, "r") as f:
                    health = json.load(f)
            except Exception:
                pass

        data = {
            "total_requests": self.total_requests,
            "timestamp": time.time(),
            "recent_events": self.recent_events[-8:],
            "servers": []
        }

        for s in self.servers:
            ip_obj = IPAddr(s["ip"])
            conns = self.active_conns.get(ip_obj, 0)
            rate = self.port_rates_mbps.get(s["port"], 0.0)
            is_up = health.get(s["ip"], True)

            data["servers"].append({
                "name": s["name"],
                "ip": s["ip"],
                "port": s["port"],
                "conns": conns,
                "total_handled": self.request_counts.get(s["ip"], 0),
                "rate_mbps": round(rate, 4),
                "status": "DOWN" if not is_up else ("OVERLOADED" if conns >= 2 else "HEALTHY")
            })

        try:
            temp = TELEMETRY_FILE + ".tmp"
            with open(temp, "w") as f:
                json.dump(data, f)
            os.replace(temp, TELEMETRY_FILE)
        except Exception:
            pass

    def _handle_ConnectionUp(self, event):
        log.info("Switch s1 connected. Installing baseline rules...")
        self.stats_connection = event.connection

        host_macs = [
            (1, "00:00:00:00:00:01"),
            (2, "00:00:00:00:00:02"),
            (3, "00:00:00:00:00:03"),
            (4, "00:00:00:00:00:04"),
            (5, "00:00:00:00:00:05"),
            (6, "00:00:00:00:00:06")
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

        Timer(2, self._request_port_stats, recurring=True)
        Timer(0.5, self._export_telemetry, recurring=True)
        Timer(0.5, self._check_signals, recurring=True)

    def _request_port_stats(self):
        if self.stats_connection is None:
            return
        msg = of.ofp_stats_request()
        msg.body = of.ofp_port_stats_request()
        self.stats_connection.send(msg)

    def _handle_PortStatsReceived(self, event):
        now = time.time()
        for stat in event.stats:
            port_no = stat.port_no
            total_bytes = stat.rx_bytes + stat.tx_bytes
            previous = self.port_bytes_previous.get(port_no)
            if previous is not None:
                old_bytes, old_time = previous
                elapsed = now - old_time
                if elapsed > 0:
                    rate = max(0, total_bytes - old_bytes) * 8 / elapsed / 1_000_000
                    self.port_rates_mbps[port_no] = rate
            self.port_bytes_previous[port_no] = (total_bytes, now)
        self._export_telemetry()

    def _release_connection(self, server_ip, duration):
        time.sleep(duration)
        if self.active_conns[server_ip] > 0:
            self.active_conns[server_ip] -= 1
        self._export_telemetry()

    def _select_least_loaded_server(self):
        health = {}
        if os.path.exists(HEALTH_FILE):
            try:
                with open(HEALTH_FILE, "r") as f:
                    health = json.load(f)
            except Exception:
                pass

        healthy_servers = [s for s in self.servers if health.get(s["ip"], True)]
        if not healthy_servers:
            return None

        available = [s for s in healthy_servers if self.active_conns[IPAddr(s["ip"])] < 2]
        pool = available if available else healthy_servers

        return min(
            pool,
            key=lambda s: (self.active_conns[IPAddr(s["ip"])], self.port_rates_mbps.get(s["port"], 0.0))
        )

    def _handle_PacketIn(self, event):
        packet = event.parsed
        if not packet.parsed:
            return

        ip_pkt = packet.find('ipv4')
        tcp_pkt = packet.find('tcp')

        if ip_pkt and tcp_pkt and str(ip_pkt.dstip) == self.VIP:
            server = self._select_least_loaded_server()
            if server is None:
                return

            server_ip = IPAddr(server['ip'])
            self.active_conns[server_ip] += 1
            self.total_requests += 1
            self.request_counts[server['ip']] = self.request_counts.get(server['ip'], 0) + 1

            t_str = time.strftime("%H:%M:%S", time.localtime())
            self.recent_events.append({
                "time": t_str,
                "client": f"{ip_pkt.srcip}:{tcp_pkt.srcport}",
                "assigned": server['name'],
                "active_now": self.active_conns[server_ip]
            })

            hold_time = server.get("delay", 0.1) * 3
            threading.Thread(target=self._release_connection, args=(server_ip, hold_time), daemon=True).start()
            self._export_telemetry()

            in_port = event.port
            client_mac = str(packet.src)

            # Reverse rule
            rule_rev = of.ofp_flow_mod()
            rule_rev.priority = 100
            rule_rev.idle_timeout = 5
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

            # Forward rule
            rule_fwd = of.ofp_flow_mod()
            rule_fwd.priority = 100
            rule_fwd.idle_timeout = 5
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
