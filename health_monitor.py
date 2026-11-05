#!/usr/bin/env python3
import json
import os
import socket
import time

SERVERS = {
    "10.0.0.3": 8000,
    "10.0.0.4": 8000,
    "10.0.0.5": 8000,
}

STATUS_FILE = "/tmp/server_status.json"
CHECK_INTERVAL = 3

def check_server(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=1):
            return True
    except OSError:
        return False

if __name__ == "__main__":
    print("Server health monitor started.", flush=True)

    try:
        while True:
            statuses = {}

            for ip, port in SERVERS.items():
                up = check_server(ip, port)
                statuses[ip] = up
                print(f"Server {ip}:{port} - {'UP' if up else 'DOWN'}", flush=True)

            temporary_file = STATUS_FILE + ".tmp"
            with open(temporary_file, "w") as file:
                json.dump(statuses, file)
            os.replace(temporary_file, STATUS_FILE)

            print(f"Health status saved to {STATUS_FILE}", flush=True)
            print("-" * 35, flush=True)
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\nHealth monitor stopped.", flush=True)
