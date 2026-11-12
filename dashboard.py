#!/usr/bin/env python3
"""
dashboard.py - Real-Time Web Server with Dynamic Nodes and Metric Reset
"""

from flask import Flask, jsonify, render_template, request
import json
import os

app = Flask(__name__)
TELEMETRY_FILE = "/tmp/sdn_telemetry.json"
CONFIG_FILE = "/tmp/sdn_config.json"
RESET_FILE = "/tmp/sdn_reset.flag"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/live')
def get_live_metrics():
    if os.path.exists(TELEMETRY_FILE):
        try:
            with open(TELEMETRY_FILE, "r") as f:
                return jsonify(json.load(f))
        except Exception:
            pass
    return jsonify({"total_requests": 0, "servers": [], "recent_events": []})

@app.route('/api/reset_metrics', methods=['POST'])
def reset_metrics():
    """Signals POX to reset all counters, logs, and total handled flows back to 0"""
    try:
        with open(RESET_FILE, "w") as f:
            f.write("reset")
        return jsonify({"success": True, "message": "Telemetry metrics reset to 0"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/add_server', methods=['POST'])
def add_server():
    data = request.json
    name = data.get("name", "Server-Custom")
    ip = data.get("ip")
    port = int(data.get("port", 6))
    mac = data.get("mac", f"00:00:00:00:00:0{port}")
    delay = float(data.get("delay", 0.02))

    new_node = {
        "name": name,
        "ip": ip,
        "mac": mac,
        "port": port,
        "delay": delay
    }

    config = {"servers": [
        {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "port": 3, "name": "Server-3 (Slow)", "delay": 0.40},
        {"ip": "10.0.0.4", "mac": "00:00:00:00:00:04", "port": 4, "name": "Server-4 (Medium)", "delay": 0.08},
        {"ip": "10.0.0.5", "mac": "00:00:00:00:00:05", "port": 5, "name": "Server-5 (Fast)", "delay": 0.01},
    ]}

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except Exception:
            pass

    if not any(s["ip"] == ip for s in config["servers"]):
        config["servers"].append(new_node)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return jsonify({"success": True, "message": f"Added {name} ({ip}) to SDN controller!"})
    
    return jsonify({"success": False, "message": "Server IP already exists in topology."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
