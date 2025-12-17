#!/usr/bin/env python3
"""
Plot throughput (Ops/sec) versus loaded_pairs from combined bandwidth contention results.
"""

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt


def load_data(path: Path):
    """Load and parse results.json to extract loaded_pairs and throughput."""
    with path.open("r") as f:
        data = json.load(f)

    configurations = data.get("configurations", {})
    points = []

    for loaded_pairs_key, metrics in configurations.items():
        match = re.search(r"loaded_pairs_(\d+)", loaded_pairs_key)
        if not match:
            continue

        loaded_pairs = int(match.group(1))
        throughput = metrics.get("throughput_ops_sec")
        if throughput is None:
            continue

        points.append((loaded_pairs, float(throughput)))

    # Sort by loaded_pairs
    points.sort(key=lambda x: x[0])
    return points


def plot(points, output_path: Path):
    """Create and save the plot."""
    if not points:
        print("No data to plot.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    x_vals = [p[0] for p in points]
    y_vals = [p[1] for p in points]
    
    ax.plot(x_vals, y_vals, marker="o", linestyle="-", linewidth=2, markersize=6, color='green')

    ax.set_xlabel("Loaded Pairs", fontsize=12)
    ax.set_ylabel("Throughput (Ops/sec)", fontsize=12)
    ax.set_title("Combined Throughput: Ops/sec vs Loaded Pairs", fontsize=14, fontweight='bold')
    ax.grid(True, linestyle="--", alpha=0.5)
    
    # Format y-axis to show values in plain format
    ax.ticklabel_format(style='plain', axis='y')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Saved plot to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Plot throughput (Ops/sec) vs loaded_pairs from combined bandwidth contention results"
    )
    parser.add_argument(
        "-i",
        "--input",
        default="combined_bandwidth_contention/results.json",
        help="Path to results.json (default: combined_bandwidth_contention/results.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="combined_bandwidth_contention/throughput_ops_sec.png",
        help="Output image path (default: combined_bandwidth_contention/throughput_ops_sec.png)",
    )

    args = parser.parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return

    print(f"Loading data from {input_path}...")
    points = load_data(input_path)
    print(f"Found {len(points)} data points")

    plot(points, output_path)


if __name__ == "__main__":
    main()
