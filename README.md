Software-Defined Networking (SDN) Dynamic Load Balancer
An OpenFlow-based Layer 2/3 Software-Defined Networking (SDN) Load Balancer implemented using the POX Controller (Control Plane) and Mininet (Data Plane).
The system abstracts a pool of heterogeneous backend application servers behind a single Virtual IP (VIP). Incoming client flows are intercepted, dynamically translated via bidirectional OpenFlow 1.0 packet rewriting (NAT), and balanced across backend servers.
The project evaluates and benchmarks two distinct load-balancing paradigms:
 * Deliverable 1 (D1): Static Round-Robin (Baseline)
 * Deliverable 2 (D2): Adaptive Least-Connections (Dynamic Feedback)
📌 System Architecture
The topology is deployed on Open vSwitch (s1) operating in secure fail-mode with five connected virtual hosts:
               +----------------------------------+
               |       POX Controller (c0)        |
               | (lb_controller.py / adaptive_lb) |
               +-----------------+----------------+
                                 | OpenFlow 1.0 (Port 6633)
               +-----------------+----------------+
               |        Open vSwitch (s1)         |
               +--+--------+--------+--------+----+
                  | Port 1 | Port 2 | Port 3 | Port 4 | Port 5
                  |        |        |        |        |
         +--------+   +----+---+ +--+-----+ +-+------+ +-+------+
         |   h1   |   |   h2   | |   h3   | |   h4   | |   h5   |
         +--------+   +--------+ +--------+ +--------+ +--------+
          Clients (Requesters)     Backend Servers (Workers)

Network Addressing & Topology Specifications
 * Virtual IP (VIP): 10.0.0.100 | Virtual MAC (VMAC): 00:00:00:00:01:00
 * Clients:
   * h1: 10.0.0.1 | 00:00:00:00:00:01 (Port 1)
   * h2: 10.0.0.2 | 00:00:00:00:00:02 (Port 2)
 * Backend Pool (Asymmetric Processing Latencies):
   * h3 (Server-3): 10.0.0.3 | 00:00:00:00:00:03 (Port 3) — Slow Worker (0.40s synthetic delay)
   * h4 (Server-4): 10.0.0.4 | 00:00:00:00:00:04 (Port 4) — Medium Worker (0.08s synthetic delay)
   * h5 (Server-5): 10.0.0.5 | 00:00:00:00:00:05 (Port 5) — Fast Worker (0.01s synthetic delay)
⚙️ OpenFlow Forwarding & Two-Way NAT
The POX controller operates as a transparent Layer 2/3 NAT middlebox via OpenFlow ofp_flow_mod instructions:
 * Client Request Interception:
   * A client transmits a TCP SYN packet to 10.0.0.100:8000.
   * Switch s1 matches destination IP 10.0.0.100 and generates an ofp_packet_in event to POX.
 * Forward Translation (Client to Backend):
   * The controller selects a backend server according to the active policy (Round-Robin modulo index or Least-Connections table).
   * Installs flow rules on s1:
     * Rewrite Destination IP: 10.0.0.100 -> Chosen Server IP
     * Rewrite Destination MAC: 00:00:00:00:01:00 -> Chosen Server MAC
     * Output: Port assigned to the selected server.
 * Reverse Translation (Backend to Client):
   * The backend server responds directly to the client IP.
   * Switch s1 intercepts the return traffic:
     * Rewrite Source IP: Server IP -> 10.0.0.100 (VIP)
     * Rewrite Source MAC: Server MAC -> 00:00:00:00:01:00 (VMAC)
     * Output: Port connected to the requesting client.
   * Preserves TCP state across the communication path, preventing client-side RST drops.
📂 Repository Structure
├── lb_controller.py      # D1: Static Round-Robin POX OpenFlow controller
├── adaptive_lb.py        # D2: Dynamic Least-Connections POX OpenFlow controller
├── topo.py               # Mininet custom topology (1 switch, 5 hosts, static ARP)
├── server.py             # Asymmetric HTTP server script with synthetic processing delays
├── benchmark.py          # Multi-threaded HTTP benchmark client
├── plot_metrics.py       # Matplotlib visualization script for D1 vs D2 comparison
├── .gitignore            # Git exclusion rules
└── README.md             # Project documentation & run manual

🚀 Setup & Execution Guide
1. Prerequisites (Ubuntu Linux)
Install Mininet, Open vSwitch, networking utilities, and Matplotlib:
sudo apt update
sudo apt install -y mininet openvswitch-switch net-tools ethtool python3-matplotlib git
sudo systemctl enable --now openvswitch-switch

2. POX Controller Setup
Ensure POX is cloned and set to the Python 3 compatible branch:
cd ~
git clone https://github.com/noxrepo/pox.git
cd ~/pox
git checkout gar-experimental

Deploy the controller files into the POX directory:
cp ~/sdn_load_balancer/lb_controller.py ~/pox/pox/misc/
cp ~/sdn_load_balancer/adaptive_lb.py ~/pox/pox/misc/

3. Deliverable 1: Static Round-Robin (Baseline)
Terminal 1 — Controller:
python3 ~/pox/pox.py openflow.of_01 misc.lb_controller

Terminal 2 — Mininet Network:
sudo mn -c
cd ~/sdn_load_balancer
sudo python3 topo.py

Inside the Mininet CLI:
# Launch backend servers in background
mininet> h3 python3 server.py 10.0.0.3 8000 Server-3 0.40 &
mininet> h4 python3 server.py 10.0.0.4 8000 Server-4 0.08 &
mininet> h5 python3 server.py 10.0.0.5 8000 Server-5 0.01 &

# Execute Round-Robin Benchmark (30 requests, concurrency level 10)
mininet> h1 python3 benchmark.py 30 10 rr_results.csv

4. Deliverable 2: Adaptive Least-Connections
 * In Terminal 1, press Ctrl + C to stop the D1 controller.
 * Launch the adaptive controller:
python3 ~/pox/pox.py openflow.of_01 misc.adaptive_lb

 * In Terminal 2 (inside the active Mininet CLI), run the adaptive benchmark:
mininet> h1 python3 benchmark.py 30 10 adaptive_results.csv

5. Generate Comparative Visualization
In a standard Ubuntu terminal outside Mininet:
cd ~/sdn_load_balancer
python3 plot_metrics.py rr_results.csv adaptive_results.csv
xdg-open d2_performance_comparison.png

📊 Comparative Performance Results
| Metric | Deliverable 1: Round-Robin | Deliverable 2: Least-Connections |
|---|---|---|
| Routing Algorithm | Modulo Counter (N mod 3) | Active Socket Connection State Tracking |
| Workload Awareness | Oblivious to server delays | Closed-loop load feedback |
| Request Allocation (30 Reqs) | Exact 1:1:1 Split (10 / 10 / 10) | Biased to Fast Nodes (h5: ~23, h4: ~6, h3: ~1) |
| Server-3 Saturation | 33.3% of total traffic | ~3.3% of traffic (Protected from bottleneck) |
| Average Latency (RTT) | ~165 ms – 170 ms | ~40 ms – 45 ms (~75% reduction) |
🛠 Key Technical Challenges & Optimizations
 * TCP Checksum Offloading Bug Fix:
   * Problem: In virtual interfaces (veth), Open vSwitch rewrote IP and MAC headers without updating offloaded checksums. The Linux kernel TCP stack silently dropped packets, causing an initial 1000 ms SYN retransmission timeout penalty.
   * Resolution: Disabled hardware checksum offload directly inside topo.py:
     ethtool -K <interface> rx off tx off

 * Static ARP Pre-Population:
   * Prevented ARP packet floods and early handshake drops by pre-populating ARP tables on all hosts for peer interfaces and the VIP (10.0.0.100 -> 00:00:00:00:01:00).
 * OpenFlow Buffer Safety:
   * Enforced explicit of.NO_BUFFER checks when handling packet-out events in POX, preventing dropped client connections during high-concurrency bursts.
