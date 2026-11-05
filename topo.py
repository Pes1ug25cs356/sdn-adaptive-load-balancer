#!/usr/bin/env python3
"""
Topology: 1 Switch, 2 Clients (h1, h2), 3 Backend Servers (h3, h4, h5)
Remote POX Controller on 127.0.0.1:6633
Pre-populates static ARP entries and disables checksum offloading on veth interfaces.
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def run_topology():
    net = Mininet(controller=RemoteController, switch=OVSSwitch)

    info('*** Adding Remote Controller\n')
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6633)

    info('*** Adding Switch\n')
    s1 = net.addSwitch('s1')

    info('*** Adding Hosts\n')
    h1 = net.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
    h3 = net.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
    h4 = net.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')
    h5 = net.addHost('h5', ip='10.0.0.5/24', mac='00:00:00:00:00:05')

    info('*** Adding Links (port mapping: 1->h1, 2->h2, 3->h3, 4->h4, 5->h5)\n')
    net.addLink(h1, s1, port2=1)
    net.addLink(h2, s1, port2=2)
    net.addLink(h3, s1, port2=3)
    net.addLink(h4, s1, port2=4)
    net.addLink(h5, s1, port2=5)

    info('*** Starting Network\n')
    net.build()
    c0.start()
    s1.start([c0])

    info('*** Configuring Static ARP Tables and Disabling Checksum Offloading\n')
    hosts = [h1, h2, h3, h4, h5]
    vip = '10.0.0.100'
    vmac = '00:00:00:00:01:00'

    for h in hosts:
        # Disable checksum offloading so OpenFlow IP rewrites don't cause SYN drops
        h.cmd(f'ethtool -K {h.name}-eth0 rx off tx off')

        # Static ARP entry for the Virtual IP (VIP)
        h.setARP(vip, vmac)

        # Static ARP entries for all other hosts
        for target in hosts:
            if target != h:
                h.setARP(target.IP(), target.MAC())

    info('*** Network topology is ready.\n')
    CLI(net)

    info('*** Stopping Network\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run_topology()
