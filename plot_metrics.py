#!/usr/bin/env python3
import csv
import sys
import matplotlib
matplotlib.use('Agg')  # Headless mode for VM/terminal
import matplotlib.pyplot as plt

def load_data(csv_file):
    rtts = []
    server_counts = {}
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Status'] == 'SUCCESS':
                rtts.append(float(row['RTT_ms']))
                srv = row['Server']
                server_counts[srv] = server_counts.get(srv, 0) + 1
    return rtts, server_counts

def plot_comparison(rr_csv, adapt_csv, output_img="d2_performance_comparison.png"):
    rr_rtts, rr_counts = load_data(rr_csv)
    ad_rtts, ad_counts = load_data(adapt_csv)

    avg_rr = sum(rr_rtts) / len(rr_rtts) if rr_rtts else 0
    avg_ad = sum(ad_rtts) / len(ad_rtts) if ad_rtts else 0

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))

    # Graph 1: Average Latency
    bars = ax1.bar(['Round-Robin (D1)', 'Least-Connections (D2)'], [avg_rr, avg_ad], color=['#EF4444', '#10B981'], width=0.5)
    ax1.set_ylabel('Average RTT (ms)')
    ax1.set_title('Average Request Latency under Asymmetric Stress')
    for bar in bars:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 5, f"{yval:.1f} ms", ha='center', va='bottom', fontweight='bold')

    # Graph 2: Request Distribution
    servers = sorted(list(set(list(rr_counts.keys()) + list(ad_counts.keys()))))
    rr_vals = [rr_counts.get(s, 0) for s in servers]
    ad_vals = [ad_counts.get(s, 0) for s in servers]

    import numpy as np
    x = np.arange(len(servers))
    width = 0.35

    ax2.bar(x - width/2, rr_vals, width, label='Round-Robin', color='#EF4444')
    ax2.bar(x + width/2, ad_vals, width, label='Least-Connections', color='#10B981')
    ax2.set_xlabel('Backend Server')
    ax2.set_ylabel('Total Requests Handled')
    ax2.set_title('Request Distribution (Server-3 is Stressed)')
    ax2.set_xticks(x)
    ax2.set_xticklabels(servers)
    ax2.legend()

    plt.tight_layout()
    plt.savefig(output_img, dpi=300)
    print(f"Comparison graph saved to: {output_img}")

if __name__ == '__main__':
    rr_file = sys.argv[1] if len(sys.argv) > 1 else "rr_results.csv"
    ad_file = sys.argv[2] if len(sys.argv) > 2 else "adaptive_results.csv"
    plot_comparison(rr_file, ad_file)
