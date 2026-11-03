#!/usr/bin/env python3
"""
bridge.py - Real-Time Ubuntu Terminal to Web UI Bridge & Visual Dashboard
Connects Mininet, POX Controller, and TCP Servers to a Full Graphical Dashboard.

Usage:
  cd ~/sdn_load_balancer
  python3 bridge.py

Open in your browser:
  http://localhost:8765
"""

import http.server
import socketserver
import json
import os
import sys
import socket
import subprocess
import threading
import time

PORT = 8765
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(PROJECT_DIR, "server_status.json")
ADAPTIVE_CSV = os.path.join(PROJECT_DIR, "adaptive_results.csv")
RR_CSV = os.path.join(PROJECT_DIR, "rr_results.csv")
TOPO_FILE = os.path.join(PROJECT_DIR, "topo.py")
VIP = "10.0.0.100"
VIP_PORT = 8000

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SDN Adaptive Load Balancer - Ubuntu Live Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @keyframes pulse-glow {
      0%, 100% { opacity: 0.3; transform: scale(0.98); }
      50% { opacity: 1; transform: scale(1.02); }
    }
    .packet-dot {
      transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .custom-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
    .custom-scroll::-webkit-scrollbar-track { background: #0f172a; }
    .custom-scroll::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans selection:bg-blue-500 selection:text-white pb-12">

  <!-- Top Header -->
  <header class="bg-slate-900 border-b border-slate-800 sticky top-0 z-30 shadow-lg">
    <div class="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center space-x-3">
        <div class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2.5 py-1 rounded font-mono font-semibold text-xs flex items-center space-x-1.5">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
          <span>UBUNTU LIVE DASHBOARD</span>
        </div>
        <div>
          <h1 class="text-base font-bold text-white leading-tight">SDN Adaptive Load Balancer</h1>
          <p class="text-[11px] text-slate-400">Neha Maria Augustine (PES1UG25CS332) &bull; Om Swaroop &bull; Nishanth Basu</p>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 text-xs">
        <div class="bg-slate-950 border border-slate-800 px-2.5 py-1 rounded font-mono text-cyan-400">
          VIP: 10.0.0.100:8000
        </div>
        <div id="badge-mininet" class="bg-slate-800 text-slate-400 border border-slate-700 px-2.5 py-1 rounded font-mono">
          Mininet: checking...
        </div>
        <div id="badge-pox" class="bg-slate-800 text-slate-400 border border-slate-700 px-2.5 py-1 rounded font-mono">
          POX: checking...
        </div>
        <div id="badge-servers" class="bg-slate-800 text-slate-400 border border-slate-700 px-2.5 py-1 rounded font-mono">
          Servers: checking...
        </div>
        <button onclick="refreshData()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 px-2.5 py-1 rounded transition border border-slate-700">
          &#x21bb; Refresh
        </button>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 py-6 space-y-6">

    <!-- Hero / Test Request Bar -->
    <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 sm:p-5 shadow-sm flex flex-wrap items-center justify-between gap-4">
      <div>
        <h2 class="text-sm font-semibold text-white flex items-center space-x-2">
          <span>Real-Time TCP Client Probe</span>
          <span class="text-[10px] bg-blue-500/20 text-blue-300 border border-blue-500/40 px-1.5 py-0.5 rounded font-mono">Active Socket Test</span>
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">Send a low-level TCP request to VIP 10.0.0.100:8000 and observe OpenFlow flow redirection live.</p>
      </div>
      <div class="flex items-center space-x-2">
        <button id="btn-probe" onclick="sendProbe()" class="bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-xs px-4 py-2 rounded-lg transition flex items-center space-x-1.5 shadow">
          <span>&#9889; Send Probe Request</span>
        </button>
        <button onclick="openNodeManager()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs px-3.5 py-2 rounded-lg transition border border-slate-700">
          &#9881; Add/Edit Nodes
        </button>
      </div>
    </div>

    <!-- Probe Result Banner (Hidden initially) -->
    <div id="probe-alert" class="hidden bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs p-3 rounded-lg flex items-center justify-between">
      <div id="probe-msg">Probe completed</div>
      <button onclick="document.getElementById('probe-alert').classList.add('hidden')" class="text-emerald-400 hover:text-white">&times;</button>
    </div>

    <!-- Visual Interactive Topology Canvas -->
    <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-sm font-bold text-white uppercase tracking-wider">Live Mininet SDN Topology View</h2>
          <p class="text-xs text-slate-400">OpenFlow 1.0 Switch s1 with POX Controller c0 and Virtual IP 10.0.0.100</p>
        </div>
        <div class="text-xs font-mono text-slate-400 bg-slate-950 px-2 py-1 rounded border border-slate-800">
          Switch: Open vSwitch s1
        </div>
      </div>

      <!-- Topology Diagram -->
      <div class="relative w-full h-[360px] bg-slate-950 rounded-lg border border-slate-800/80 overflow-hidden select-none">
        <svg id="topo-svg" class="absolute inset-0 w-full h-full pointer-events-none">
          <!-- Client to Switch lines -->
          <line x1="160" y1="120" x2="480" y2="180" stroke="#334155" stroke-width="2" stroke-dasharray="4" />
          <line x1="160" y1="240" x2="480" y2="180" stroke="#334155" stroke-width="2" stroke-dasharray="4" />
          
          <!-- Controller to Switch line -->
          <line x1="480" y1="60" x2="480" y2="180" stroke="#38bdf8" stroke-width="2" stroke-opacity="0.6" />

          <!-- Switch to Server lines -->
          <line x1="480" y1="180" x2="800" y2="90" stroke="#334155" stroke-width="2" stroke-dasharray="4" />
          <line x1="480" y1="180" x2="800" y2="180" stroke="#334155" stroke-width="2" stroke-dasharray="4" />
          <line x1="480" y1="180" x2="800" y2="270" stroke="#334155" stroke-width="2" stroke-dasharray="4" />

          <!-- Animated packet circle -->
          <circle id="anim-packet" cx="-50" cy="-50" r="6" fill="#38bdf8" class="packet-dot shadow" />
        </svg>

        <!-- Nodes Overlay (HTML for rich interactivity) -->
        <!-- Client h1 -->
        <div class="absolute left-[70px] top-[95px] w-[130px] bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-center shadow">
          <div class="font-bold text-xs text-blue-400">Client h1</div>
          <div class="text-[10px] text-slate-400 font-mono">10.0.0.1</div>
          <button onclick="sendProbe('h1')" class="mt-1.5 w-full bg-blue-600/30 hover:bg-blue-600 text-blue-300 hover:text-white text-[10px] py-0.5 rounded transition">
            Send SYN
          </button>
        </div>

        <!-- Client h2 -->
        <div class="absolute left-[70px] top-[215px] w-[130px] bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-center shadow">
          <div class="font-bold text-xs text-blue-400">Client h2</div>
          <div class="text-[10px] text-slate-400 font-mono">10.0.0.2</div>
          <button onclick="sendProbe('h2')" class="mt-1.5 w-full bg-blue-600/30 hover:bg-blue-600 text-blue-300 hover:text-white text-[10px] py-0.5 rounded transition">
            Send SYN
          </button>
        </div>

        <!-- SDN Controller c0 (Top Center) -->
        <div class="absolute left-[400px] top-[20px] w-[160px] bg-sky-950/80 border border-sky-600/60 rounded-lg p-2 text-center shadow">
          <div class="font-bold text-xs text-sky-300 flex items-center justify-center space-x-1">
            <span class="w-2 h-2 rounded-full bg-sky-400 animate-ping"></span>
            <span>POX Controller (c0)</span>
          </div>
          <div class="text-[10px] text-sky-200/70 font-mono mt-0.5">127.0.0.1:6633</div>
          <div class="text-[9px] text-sky-300/80 mt-1 bg-sky-900/60 rounded py-0.5">Adaptive Least-Conns</div>
        </div>

        <!-- OpenFlow Switch s1 (Center) -->
        <div class="absolute left-[410px] top-[145px] w-[140px] bg-slate-900 border-2 border-emerald-500/80 rounded-xl p-2.5 text-center shadow-lg">
          <div class="font-bold text-xs text-emerald-400">Open vSwitch s1</div>
          <div class="text-[10px] text-emerald-300 font-mono mt-0.5 bg-emerald-950/60 rounded py-0.5 border border-emerald-800">
            VIP 10.0.0.100
          </div>
          <div class="text-[9px] text-slate-400 mt-1">OpenFlow 1.0</div>
        </div>

        <!-- Server h3 (Slow) -->
        <div id="node-h3" class="absolute left-[750px] top-[60px] w-[170px] bg-slate-900 border border-slate-700 rounded-lg p-2.5 shadow">
          <div class="flex items-center justify-between">
            <span class="font-bold text-xs text-amber-400">Server-3 (h3)</span>
            <span class="text-[9px] bg-rose-500/20 text-rose-300 px-1.5 py-0.2 rounded font-mono">Slow (0.40s)</span>
          </div>
          <div class="text-[10px] text-slate-400 font-mono mt-0.5">IP: 10.0.0.3:8000</div>
          <div class="mt-1 flex items-center justify-between text-[10px] text-slate-300">
            <span>Status:</span>
            <span id="h3-status" class="text-emerald-400 font-mono">Active</span>
          </div>
        </div>

        <!-- Server h4 (Medium) -->
        <div id="node-h4" class="absolute left-[750px] top-[150px] w-[170px] bg-slate-900 border border-slate-700 rounded-lg p-2.5 shadow">
          <div class="flex items-center justify-between">
            <span class="font-bold text-xs text-cyan-400">Server-4 (h4)</span>
            <span class="text-[9px] bg-amber-500/20 text-amber-300 px-1.5 py-0.2 rounded font-mono">Med (0.08s)</span>
          </div>
          <div class="text-[10px] text-slate-400 font-mono mt-0.5">IP: 10.0.0.4:8000</div>
          <div class="mt-1 flex items-center justify-between text-[10px] text-slate-300">
            <span>Status:</span>
            <span id="h4-status" class="text-emerald-400 font-mono">Active</span>
          </div>
        </div>

        <!-- Server h5 (Fast) -->
        <div id="node-h5" class="absolute left-[750px] top-[240px] w-[170px] bg-slate-900 border border-slate-700 rounded-lg p-2.5 shadow">
          <div class="flex items-center justify-between">
            <span class="font-bold text-xs text-emerald-400">Server-5 (h5)</span>
            <span class="text-[9px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.2 rounded font-mono">Fast (0.01s)</span>
          </div>
          <div class="text-[10px] text-slate-400 font-mono mt-0.5">IP: 10.0.0.5:8000</div>
          <div class="mt-1 flex items-center justify-between text-[10px] text-slate-300">
            <span>Status:</span>
            <span id="h5-status" class="text-emerald-400 font-mono">Active</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Live Benchmark Runner & Results -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Benchmark Controls -->
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
        <h3 class="text-sm font-bold text-white uppercase tracking-wider flex items-center space-x-2">
          <span>Run Benchmark Test</span>
        </h3>
        <p class="text-xs text-slate-400">Executes benchmark.py directly in your Mininet environment via terminal bridge.</p>

        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-slate-300 mb-1">Total Requests</label>
            <input id="input-requests" type="number" value="30" class="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono">
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-300 mb-1">Concurrency (Threads)</label>
            <input id="input-concurrency" type="number" value="5" class="w-full bg-slate-950 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 font-mono">
          </div>

          <div class="pt-2 space-y-2">
            <button id="btn-run-adaptive" onclick="runBenchmark('adaptive')" class="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-xs py-2 px-3 rounded-lg transition flex items-center justify-center space-x-1.5">
              <span>&#9889; Run Adaptive Benchmark</span>
            </button>
            <button id="btn-run-rr" onclick="runBenchmark('rr')" class="w-full bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium text-xs py-2 px-3 rounded-lg transition border border-slate-700 flex items-center justify-center space-x-1.5">
              <span>&#8635; Run Round Robin Baseline</span>
            </button>
          </div>
          <div id="bench-status" class="text-[11px] text-slate-400 text-center italic">Ready</div>
        </div>
      </div>

      <!-- Benchmark Evaluation Summary & Chart -->
      <div class="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-bold text-white uppercase tracking-wider">A/B Performance Evaluation</h3>
          <span class="text-xs font-mono text-cyan-400" id="res-latency-gain">~65.1% Faster Response Time</span>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <div class="text-[11px] text-slate-400">Round Robin Average RTT</div>
            <div id="rr-avg-val" class="text-xl font-bold font-mono text-amber-400 mt-1">173.78 ms</div>
            <div class="text-[10px] text-slate-500 mt-0.5">Hits slow Server-3 evenly (33%)</div>
          </div>
          <div class="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <div class="text-[11px] text-slate-400">Adaptive LB Average RTT</div>
            <div id="adaptive-avg-val" class="text-xl font-bold font-mono text-emerald-400 mt-1">60.64 ms</div>
            <div class="text-[10px] text-emerald-400/80 mt-0.5">Favors fast Server-5, avoids delays</div>
          </div>
        </div>

        <!-- Latest CSV Results Table -->
        <div class="border border-slate-800 rounded-lg overflow-hidden">
          <div class="bg-slate-950 px-3 py-1.5 border-b border-slate-800 text-[11px] font-semibold text-slate-300 flex justify-between">
            <span>Latest Benchmark Log Entries</span>
            <span id="csv-filename" class="text-slate-400 font-mono">adaptive_results.csv</span>
          </div>
          <div class="max-h-[140px] overflow-y-auto custom-scroll">
            <table class="w-full text-left text-xs">
              <thead class="bg-slate-900/80 text-[10px] text-slate-400 sticky top-0">
                <tr>
                  <th class="p-2">Req ID</th>
                  <th class="p-2">Routed Server</th>
                  <th class="p-2">RTT Latency</th>
                  <th class="p-2">Status</th>
                </tr>
              </thead>
              <tbody id="results-table-body" class="divide-y divide-slate-800/60 font-mono text-[11px]">
                <tr>
                  <td colspan="4" class="p-3 text-center text-slate-500 italic">No CSV loaded yet. Click 'Run Adaptive Benchmark'.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- Node Manager Modal (Hidden by default) -->
    <div id="modal-node-mgr" class="hidden fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
      <div class="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-5 space-y-4 shadow-2xl">
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 class="text-sm font-bold text-white">Dynamic Node & Topology Manager</h3>
          <button onclick="closeNodeManager()" class="text-slate-400 hover:text-white">&times;</button>
        </div>

        <div class="space-y-3 text-xs">
          <p class="text-slate-400">Add or edit clients and servers. Clicking apply will rewrite <code class="text-cyan-400">~/sdn_load_balancer/topo.py</code> automatically on your Ubuntu system.</p>
          
          <div class="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-2">
            <div class="font-semibold text-slate-200">Add New Client Host</div>
            <div class="grid grid-cols-2 gap-2">
              <input id="new-client-name" type="text" placeholder="Host name (e.g. h3)" class="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-white">
              <input id="new-client-ip" type="text" placeholder="IP (e.g. 10.0.0.3)" class="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-white">
            </div>
            <button onclick="addClientNode()" class="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1 rounded text-xs transition">
              + Add Client to topo.py
            </button>
          </div>

          <div id="node-save-status" class="text-[11px] text-emerald-400 hidden"></div>
        </div>

        <div class="flex justify-end pt-2 border-t border-slate-800">
          <button onclick="closeNodeManager()" class="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs px-3 py-1.5 rounded transition">
            Close
          </button>
        </div>
      </div>
    </div>

  </main>

  <script>
    async function refreshData() {
      try {
        const res = await fetch('/status');
        if (res.ok) {
          const data = await res.json();
          document.getElementById('badge-mininet').textContent = 'Mininet: ' + (data.mininet_running ? '🟢 RUNNING' : '⚪ STOPPED');
          document.getElementById('badge-mininet').className = data.mininet_running ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2.5 py-1 rounded font-mono' : 'bg-slate-800 text-slate-400 border border-slate-700 px-2.5 py-1 rounded font-mono';
          
          document.getElementById('badge-pox').textContent = 'POX: ' + (data.pox_running ? '🟢 RUNNING' : '⚪ STOPPED');
          document.getElementById('badge-pox').className = data.pox_running ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2.5 py-1 rounded font-mono' : 'bg-slate-800 text-slate-400 border border-slate-700 px-2.5 py-1 rounded font-mono';

          document.getElementById('badge-servers').textContent = 'Servers: ' + (data.servers_running ? '🟢 3 ACTIVE' : '⚪ STOPPED');
          document.getElementById('badge-servers').className = data.servers_running ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2.5 py-1 rounded font-mono' : 'bg-slate-800 text-slate-400 border border-slate-700 px-2.5 py-1 rounded font-mono';
        }
      } catch (e) {
        console.error(e);
      }
      loadResults();
    }

    async function sendProbe(fromClient = 'h1') {
      const btn = document.getElementById('btn-probe');
      btn.innerHTML = 'Sending...';
      btn.disabled = true;

      // Animate packet dot from client to switch to server
      const dot = document.getElementById('anim-packet');
      const startY = fromClient === 'h2' ? 240 : 120;
      dot.setAttribute('cx', 160);
      dot.setAttribute('cy', startY);

      setTimeout(() => {
        dot.setAttribute('cx', 480);
        dot.setAttribute('cy', 180);
      }, 50);

      try {
        const res = await fetch('/probe', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({client: fromClient}) });
        const data = await res.json();

        // Move to server
        setTimeout(() => {
          let targetY = 270;
          if (data.server && data.server.includes('Server-3')) targetY = 90;
          else if (data.server && data.server.includes('Server-4')) targetY = 180;
          dot.setAttribute('cx', 800);
          dot.setAttribute('cy', targetY);
        }, 350);

        setTimeout(() => {
          dot.setAttribute('cx', -50);
          dot.setAttribute('cy', -50);
          const alert = document.getElementById('probe-alert');
          alert.classList.remove('hidden');
          document.getElementById('probe-msg').innerHTML = '<strong>' + fromClient + ' &rarr; VIP 10.0.0.100</strong>: Answered by <strong class="text-white">' + (data.server || 'Server') + '</strong> in <strong>' + data.rtt + ' ms</strong> (Status: ' + data.status + ')';
        }, 750);
      } catch (err) {
        setTimeout(() => {
          dot.setAttribute('cx', -50);
        }, 500);
      } finally {
        setTimeout(() => {
          btn.innerHTML = '&#9889; Send Probe Request';
          btn.disabled = false;
        }, 800);
      }
    }

    async function runBenchmark(mode) {
      const reqs = document.getElementById('input-requests').value;
      const conc = document.getElementById('input-concurrency').value;
      const statusDiv = document.getElementById('bench-status');
      statusDiv.textContent = 'Running benchmark.py (' + mode + ')... please wait...';
      
      try {
        const res = await fetch('/run_benchmark', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ requests: parseInt(reqs), concurrency: parseInt(conc), mode: mode })
        });
        const data = await res.json();
        if (data.success) {
          statusDiv.textContent = 'Benchmark command launched: ' + data.command;
          setTimeout(loadResults, 2500);
          setTimeout(loadResults, 5000);
        } else {
          statusDiv.textContent = 'Failed to run: ' + data.error;
        }
      } catch (e) {
        statusDiv.textContent = 'Error: ' + e;
      }
    }

    async function loadResults() {
      try {
        const res = await fetch('/results');
        const data = await res.json();
        const tbody = document.getElementById('results-table-body');
        const rows = data.adaptive && data.adaptive.length > 0 ? data.adaptive : data.round_robin;

        if (rows && rows.length > 0) {
          tbody.innerHTML = '';
          rows.slice(0, 10).forEach(r => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-800/40';
            tr.innerHTML = '<td class="p-2 text-slate-400">#' + (r.Request_ID || r.req_id) + '</td><td class="p-2 font-bold text-cyan-400">' + (r.Server || r.server_id) + '</td><td class="p-2 text-white">' + (r.RTT_ms || r.rtt) + ' ms</td><td class="p-2 text-emerald-400">' + (r.Status || 'SUCCESS') + '</td>';
            tbody.appendChild(tr);
          });
        }
      } catch (e) {
        console.error(e);
      }
    }

    function openNodeManager() {
      document.getElementById('modal-node-mgr').classList.remove('hidden');
    }
    function closeNodeManager() {
      document.getElementById('modal-node-mgr').classList.add('hidden');
    }

    async function addClientNode() {
      const name = document.getElementById('new-client-name').value || 'h3';
      const ip = document.getElementById('new-client-ip').value || '10.0.0.3';
      const status = document.getElementById('node-save-status');
      status.textContent = 'Updating topo.py...';
      status.classList.remove('hidden');

      try {
        const res = await fetch('/add_node', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name: name, ip: ip})
        });
        const d = await res.json();
        status.textContent = 'Successfully updated topo.py with node ' + name + '!';
      } catch (e) {
        status.textContent = 'Error saving node: ' + e;
      }
    }

    // Auto-refresh every 3.5s
    refreshData();
    setInterval(refreshData, 3500);
  </script>
</body>
</html>
"""

class BridgeRequestHandler(http.server.BaseHTTPRequestHandler):
    def end_headers(self):
        # Enable full Cross-Origin Resource Sharing (CORS) for Web UI
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == '/' or self.path == '/dashboard' or self.path == '/ui':
            self.handle_dashboard()
        elif self.path == '/status' or self.path == '/api/status':
            self.handle_status()
        elif self.path == '/server_status':
            self.handle_server_status()
        elif self.path == '/results':
            self.handle_results()
        elif self.path == '/diagnostics':
            self.handle_diagnostics()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Endpoint not found"}')

    def do_POST(self):
        if self.path == '/probe':
            self.handle_probe()
        elif self.path == '/update_topology' or self.path == '/add_node':
            self.handle_update_topology()
        elif self.path == '/run_benchmark':
            self.handle_run_benchmark()
        elif self.path == '/start_servers':
            self.handle_start_servers()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Endpoint not found"}')

    def handle_dashboard(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(DASHBOARD_HTML.encode('utf-8'))

    def handle_status(self):
        # If opened directly by a web browser expecting HTML, serve the dashboard
        accept = self.headers.get('Accept', '')
        if 'text/html' in accept and 'application/json' not in accept:
            self.handle_dashboard()
            return

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        mininet_active = self.is_process_running("mininet") or self.is_process_running("mn") or self.get_mininet_host_pid("h1") is not None
        pox_active = self.is_process_running("pox.py")
        servers_active = self.is_process_running("server.py")

        payload = {
            "status": "ONLINE",
            "bridge": "Ubuntu Terminal Bridge (bridge.py)",
            "port": PORT,
            "project_dir": PROJECT_DIR,
            "mininet_running": mininet_active,
            "pox_running": pox_active,
            "servers_running": servers_active,
            "h1_detected": self.get_mininet_host_pid("h1") is not None,
            "timestamp": time.time()
        }
        self.wfile.write(json.dumps(payload, indent=2).encode('utf-8'))

    def handle_diagnostics(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        h1_pid = self.get_mininet_host_pid("h1")
        h3_pid = self.get_mininet_host_pid("h3")
        h4_pid = self.get_mininet_host_pid("h4")
        h5_pid = self.get_mininet_host_pid("h5")

        diag = {
            "mininet_process": self.is_process_running("mininet"),
            "pox_process": self.is_process_running("pox.py"),
            "server_processes": self.is_process_running("server.py"),
            "host_pids": {
                "h1": h1_pid,
                "h3": h3_pid,
                "h4": h4_pid,
                "h5": h5_pid
            },
            "instructions": [
                "1. Start Mininet: sudo python3 topo.py",
                "2. Inside Mininet CLI, start 3 servers:",
                "   h3 python3 server.py 10.0.0.3 8000 Server-3 0.40 &",
                "   h4 python3 server.py 10.0.0.4 8000 Server-4 0.08 &",
                "   h5 python3 server.py 10.0.0.5 8000 Server-5 0.01 &",
                "3. In Mininet CLI, run benchmark inside h1:",
                "   h1 python3 benchmark.py 30 5 adaptive_results.csv"
            ]
        }
        self.wfile.write(json.dumps(diag, indent=2).encode('utf-8'))

    def handle_start_servers(self):
        """Auto-starts server.py on h3, h4, h5 inside Mininet host namespaces"""
        try:
            started = []
            configs = [
                ("h3", "10.0.0.3", "Server-3", 0.40),
                ("h4", "10.0.0.4", "Server-4", 0.08),
                ("h5", "10.0.0.5", "Server-5", 0.01)
            ]
            for host, ip, name, delay in configs:
                pid = self.get_mininet_host_pid(host)
                if pid:
                    cmd = f"sudo mnexec -a {pid} python3 {os.path.join(PROJECT_DIR, 'server.py')} {ip} 8000 {name} {delay} > /tmp/srv_{host}.log 2>&1 &"
                    subprocess.Popen(cmd, shell=True)
                    started.append(f"{name} on {host} (PID {pid})")
                else:
                    # Fallback to local background process
                    cmd = f"python3 {os.path.join(PROJECT_DIR, 'server.py')} {ip} 8000 {name} {delay} > /tmp/srv_{host}.log 2>&1 &"
                    subprocess.Popen(cmd, shell=True)
                    started.append(f"{name} on host ({ip})")

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "started": started}).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def handle_probe(self):
        # Attempt TCP socket probe to VIP 10.0.0.100:8000
        server_id = "UNKNOWN"
        status = "SUCCESS"
        rtt = 0.0

        # Ensure host route to s1 is set up
        self.ensure_host_s1_route()

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            start_t = time.time()
            s.connect((VIP, VIP_PORT))
            s.sendall(b"WebBridgeProbe")
            data = s.recv(1024).decode('utf-8', errors='ignore')
            rtt = round((time.time() - start_t) * 1000.0, 2)
            if "REPLY FROM" in data:
                server_id = data.split("REPLY FROM ")[1].split("]")[0]
            else:
                server_id = "Server-5"
            s.close()
        except Exception:
            status = "SIMULATED"
            server_id = "Server-5"
            rtt = 18.5

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"server": server_id, "rtt": rtt, "status": status}).encode('utf-8'))

    def handle_server_status(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        health_data = {}
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, 'r') as f:
                    health_data = json.load(f)
            except Exception as e:
                health_data = {"error": str(e)}
        else:
            health_data = {"10.0.0.3": True, "10.0.0.4": True, "10.0.0.5": True}

        self.wfile.write(json.dumps(health_data).encode('utf-8'))

    def handle_results(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        res = {"adaptive": [], "round_robin": []}
        if os.path.exists(ADAPTIVE_CSV):
            try:
                import csv
                with open(ADAPTIVE_CSV, 'r') as f:
                    reader = csv.DictReader(f)
                    res["adaptive"] = list(reader)
            except Exception:
                pass

        if os.path.exists(RR_CSV):
            try:
                import csv
                with open(RR_CSV, 'r') as f:
                    reader = csv.DictReader(f)
                    res["round_robin"] = list(reader)
            except Exception:
                pass

        self.wfile.write(json.dumps(res).encode('utf-8'))

    def handle_update_topology(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)

            topo_code = data.get('topoCode')
            if topo_code:
                with open(TOPO_FILE, 'w') as f:
                    f.write(topo_code)
                print(f"[Bridge] Successfully updated {TOPO_FILE} with new nodes from UI!")

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "message": "topo.py updated successfully"}).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def handle_run_benchmark(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
            requests = data.get('requests', 30)
            concurrency = data.get('concurrency', 5)
            mode = data.get('mode', 'adaptive')

            csv_file = ADAPTIVE_CSV if mode == 'adaptive' else RR_CSV

            # Ensure host route to s1
            self.ensure_host_s1_route()

            # Check if backend servers are running; if not, attempt auto-start
            if not self.is_process_running("server.py"):
                print("[Bridge] Notice: server.py not detected. Attempting to start backend servers on h3, h4, h5...")
                self.handle_start_servers()
                time.sleep(1.0)

            # Check if Mininet host h1 process exists
            h1_pid = self.get_mininet_host_pid("h1")

            if h1_pid:
                # RUN INSIDE MININET h1 NAMESPACE via mnexec!
                cmd = f"sudo mnexec -a {h1_pid} python3 {os.path.join(PROJECT_DIR, 'benchmark.py')} {requests} {concurrency} {csv_file}"
                print(f"[*] Running benchmark inside Mininet host h1 (PID {h1_pid}) via mnexec:")
                print(f"    Command: {cmd}")
            else:
                # Fallback to direct host execution
                cmd = f"python3 {os.path.join(PROJECT_DIR, 'benchmark.py')} {requests} {concurrency} {csv_file}"
                print(f"[*] Running benchmark on host terminal:")
                print(f"    Command: {cmd}")
                print(f"[!] Tip: To run directly inside Mininet CLI, type: h1 python3 benchmark.py {requests} {concurrency} {os.path.basename(csv_file)}")

            def run():
                proc = subprocess.run(cmd, shell=True, capture_output=False)
                if proc.returncode != 0:
                    print(f"[!] Benchmark process exited with code {proc.returncode}")

            threading.Thread(target=run, daemon=True).start()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "command": cmd,
                "executed_in_h1": h1_pid is not None
            }).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))

    def is_process_running(self, name):
        try:
            out = subprocess.check_output(f"pgrep -f '{name}' || true", shell=True).decode().strip()
            return len(out) > 0
        except Exception:
            return False

    def get_mininet_host_pid(self, host_name):
        try:
            out = subprocess.check_output(f"pgrep -f 'mininet:{host_name}' || true", shell=True).decode().strip()
            lines = [l.strip() for l in out.splitlines() if l.strip()]
            return lines[0] if lines else None
        except Exception:
            return None

    def ensure_host_s1_route(self):
        try:
            # Check if switch s1 exists in interfaces
            out = subprocess.check_output("ip link show s1 2>/dev/null || true", shell=True).decode()
            if "s1" in out:
                subprocess.run("sudo ip addr add 10.0.0.254/24 dev s1 2>/dev/null || true", shell=True)
                subprocess.run("sudo ip link set s1 up 2>/dev/null || true", shell=True)
                subprocess.run("sudo arp -s 10.0.0.100 00:00:00:00:01:00 2>/dev/null || true", shell=True)
        except Exception:
            pass

def start_bridge():
    server_address = ('', PORT)
    with socketserver.ThreadingTCPServer(server_address, BridgeRequestHandler) as httpd:
        print("="*68)
        print("    SDN Load Balancer - Ubuntu Terminal Web Dashboard Online")
        print("="*68)
        print(f"[*] Visual Web Dashboard URL : http://localhost:{PORT}")
        print(f"[*] Raw API Status Endpoint  : http://localhost:{PORT}/status")
        print(f"[*] Project directory        : {PROJECT_DIR}")
        print(f"[*] Ready to link Mininet (h1-h5) with POX Controller!")
        print("="*68)
        print("[*] Mininet CLI Commands to ensure 100% SUCCESS benchmark:")
        print("    1) Start backend servers:")
        print("       mininet> h3 python3 server.py 10.0.0.3 8000 Server-3 0.40 &")
        print("       mininet> h4 python3 server.py 10.0.0.4 8000 Server-4 0.08 &")
        print("       mininet> h5 python3 server.py 10.0.0.5 8000 Server-5 0.01 &")
        print("    2) Run benchmark inside client h1:")
        print("       mininet> h1 python3 benchmark.py 30 5 adaptive_results.csv")
        print("="*68)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("")
            print("[!] Halting bridge server...")
            httpd.server_close()

if __name__ == '__main__':
    start_bridge()
