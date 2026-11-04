#!/usr/bin/env python3
import socket
import sys
import time
import csv
import concurrent.futures

VIP = "10.0.0.100"
PORT = 8000

def send_request(req_id):
    server_id = "UNKNOWN"
    status = "SUCCESS"
    rtt = 0.0

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((VIP, PORT))
        
        start_t = time.time()
        sock.sendall(f"StressTask-{req_id}".encode('utf-8'))
        response = sock.recv(1024).decode('utf-8')
        rtt = (time.time() - start_t) * 1000.0

        if "REPLY FROM" in response:
            server_id = response.split("REPLY FROM ")[1].split("]")[0]
        sock.close()
    except Exception as e:
        status = "FAILED"
        rtt = 0.0

    return (req_id, server_id, round(rtt, 2), status)

def run_benchmark(num_requests, concurrency, output_csv):
    print(f"Starting benchmark: {num_requests} requests (concurrency: {concurrency}) -> VIP {VIP}:{PORT}...")
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_request, i) for i in range(1, num_requests + 1)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            results.append(res)
            print(f"Req #{res[0]}: {res[1]} | RTT: {res[2]} ms | {res[3]}")

    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Request_ID", "Server", "RTT_ms", "Status"])
        writer.writerows(sorted(results, key=lambda x: x[0]))

    rtts = [r[2] for r in results if r[3] == "SUCCESS"]
    avg_rtt = sum(rtts) / len(rtts) if rtts else 0
    print(f"\nCompleted! Results saved to {output_csv}")
    print(f"Average RTT: {avg_rtt:.2f} ms (Total Success: {len(rtts)}/{num_requests})")

if __name__ == '__main__':
    total_reqs = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    concurrency = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    out_file = sys.argv[3] if len(sys.argv) > 3 else "benchmark_results.csv"
    run_benchmark(total_reqs, concurrency, out_file)
