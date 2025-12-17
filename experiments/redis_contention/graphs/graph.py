#!/usr/bin/env python3
"""
Plot subplots for each metric in aggregated_results.json.
Y-axis: metric value.
X-axis: number of pairs extracted from loaded_pairs_{x}.
"""

import argparse
import json
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt


def load_results(path: Path):
    with path.open("r") as f:
        data = json.load(f)
    configs = data.get("configurations", {})
    metrics = data.get("metadata", {}).get("metrics", [])
    parsed = []
    for name, values in configs.items():
        m = re.match(r"loaded_pairs_(\d+)", name)
        if not m:
            continue
        pairs = int(m.group(1))
        parsed.append({"pairs": pairs, "metrics": values, "name": name})
    parsed.sort(key=lambda x: x["pairs"])
    return parsed, metrics


def plot_metrics(data, metrics, output_path: Path):
    if not data:
        print("No data to plot.")
        return
    if not metrics:
        metrics = list(data[0]["metrics"].keys())

    n = len(metrics)
    cols = 2
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4 * rows))
    axes = axes.flatten() if n > 1 else [axes]

    x_vals = [item["pairs"] for item in data]

    for idx, metric_key in enumerate(metrics):
        # Map metric key to a nice label
        match metric_key:
            case "throughput_ops_sec":
                metric_label = "Throughput (Ops/sec)"
            case "MB/s":
                metric_label = "Throughput (MB/sec)"
            case "avg_latency_ms":
                metric_label = "Average Latency (ms)"
            case "p99_latency_ms":
                metric_label = "p99 Latency (ms)"
            case "p99_9_latency_ms":
                metric_label = "p99.9 Latency (ms)"
            case _:
                metric_label = metric_key

        ax = axes[idx]
        # Use the original key to pull values from the JSON
        y_vals = [item["metrics"].get(metric_key) for item in data]
        ax.plot(x_vals, y_vals, marker="o", linestyle="-", color="tab:blue")
        ax.set_xticks(x_vals)
        ax.set_xticklabels([str(x) for x in x_vals])
        ax.set_title(metric_label)
        ax.set_xlabel("Number of Pairs Run Concurrently with Victim")
        ax.grid(True, linestyle="--", alpha=0.5)

    # Hide any unused axes
    for j in range(n, len(axes)):
        axes[j].set_visible(False)

    fig.tight_layout()
    plt.savefig(output_path, bbox_inches="tight")
    print(f"Saved plot to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Plot metrics from aggregated_results.json"
    )
    parser.add_argument(
        "-i",
        "--input",
        default="aggregated_results.json",
        help="Path to aggregated_results.json (default: aggregated_results.json in CWD)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="graph_results/plot_metrics.png",
        help="Output image path (default: plot_metrics.png)",
    )

    args = parser.parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return

    data, metrics = load_results(input_path)
    plot_metrics(data, metrics, output_path)


if __name__ == "__main__":
    main()
