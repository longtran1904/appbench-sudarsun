#!/usr/bin/env python3
"""
Plot KB/s versus multi_get size from multi-key benchmark results.
"""

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt


def load_series(path: Path):
    with path.open("r") as f:
        data = json.load(f)

    configurations = data.get("configurations", {})
    series = []

    for clients_key, threads_map in configurations.items():
        clients_match = re.search(r"clients_(\d+)", clients_key)
        clients = int(clients_match.group(1)) if clients_match else clients_key

        for threads_key, pipelines_map in threads_map.items():
            threads_match = re.search(r"threads_(\d+)", threads_key)
            threads = int(threads_match.group(1)) if threads_match else threads_key

            for pipeline_key, multiget_map in pipelines_map.items():
                pipeline_match = re.search(r"pipeline_(\d+)", pipeline_key)
                pipeline = int(pipeline_match.group(1)) if pipeline_match else pipeline_key

                points = []
                for multiget_key, metrics in multiget_map.items():
                    multiget_match = re.search(r"multi_get_(\d+)", multiget_key)
                    if not multiget_match:
                        continue

                    multiget = int(multiget_match.group(1))
                    kb_per_s = metrics.get("KB/s")
                    if kb_per_s is None:
                        continue

                    points.append((multiget, float(kb_per_s)))

                if not points:
                    continue

                points.sort(key=lambda x: x[0])
                label = f"clients={clients}, threads={threads}, pipeline={pipeline}"
                series.append((label, points))

    return series


def plot(series, output_path: Path):
    if not series:
        print("No data to plot.")
        return

    fig, ax = plt.subplots(figsize=(7, 4))

    for label, points in series:
        x_vals = [p[0] for p in points]
        y_vals = [p[1] for p in points]
        ax.plot(x_vals, y_vals, marker="o", linestyle="-", label=label)

    all_x = sorted({x for _, pts in series for x, _ in pts})
    ax.set_xticks(all_x)
    ax.set_xlabel("multi_get size")
    ax.set_ylabel("KB/s")
    ax.set_title("Redis multi-get throughput")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    print(f"Saved plot to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Plot KB/s vs multi_get size")
    parser.add_argument(
        "-i",
        "--input",
        default="multi-key-benchmark/results.json",
        help="Path to results.json (default: multi-key-benchmark/results.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="plots/multi_get_kbs.png",
        help="Output image path (default: plots/multi_get_kbs.png)",
    )

    args = parser.parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return

    series = load_series(input_path)
    plot(series, output_path)


if __name__ == "__main__":
    main()
