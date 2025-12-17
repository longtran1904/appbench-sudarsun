#!/usr/bin/env python3
import json
import math
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def load_and_flatten(json_path: Path) -> pd.DataFrame:
    """Load throughput.json and flatten to a DataFrame."""
    with open(json_path, "r") as f:
        data = json.load(f)

    rows = []

    configs = data["configurations"]
    for c_key, c_val in configs.items():
        # c_key: "clients_1" -> 1
        clients = int(c_key.split("_")[1])

        for t_key, t_val in c_val.items():
            # t_key: "threads_4" -> 4
            threads = int(t_key.split("_")[1])

            for p_key, p_val in t_val.items():
                # p_key: "pipeline_1" -> 1
                pipeline = int(p_key.split("_")[1])

                for m_key, metrics in p_val.items():
                    print("m_key:", m_key)
                    multi_get = int(m_key.split("_")[2])
                    row = {
                        "clients": clients,
                        "threads": threads,
                        "pipeline": pipeline,
                        "multi_get": multi_get,
                        "throughput": metrics["throughput_ops_sec"],
                        "KB/s": metrics["KB/s"],
                        "avg_latency": metrics["avg_latency_ms"],
                        "p99": metrics["p99_latency_ms"],
                        "p999": metrics["p99_9_latency_ms"],
                    }
                    rows.append(row)

    df = pd.DataFrame(rows)

    # Clean up NaNs / invalid rows
    # df = df.replace([np.inf, -np.inf], np.nan)
    # df = df.dropna(subset=["throughput", "avg_latency"])
    sorted_df = df.sort_values("KB/s", ascending=False)
    print(sorted_df)

    return df


def is_pareto_front(df: pd.DataFrame) -> pd.Series:
    """
    Mark rows that are on the Pareto frontier:
    - maximize throughput
    - minimize avg_latency
    A config A dominates B if:
      throughput_A >= throughput_B and
      avg_latency_A <= avg_latency_B
    and at least one inequality is strict.
    """
    n = len(df)
    pareto = [True] * n

    # Work on numpy arrays for speed
    thr = df["throughput"].to_numpy()
    lat = df["avg_latency"].to_numpy()

    for i in range(n):
        if not pareto[i]:
            continue
        for j in range(n):
            if i == j:
                continue
            # Skip NaNs just in case
            if math.isnan(thr[j]) or math.isnan(lat[j]):
                continue

            # j dominates i?
            if (
                thr[j] >= thr[i]
                and lat[j] <= lat[i]
                and (thr[j] > thr[i] or lat[j] < lat[i])
            ):
                pareto[i] = False
                break

    return pd.Series(pareto, index=df.index, name="pareto")

def get_pareto_configs(df: pd.DataFrame) -> pd.DataFrame:
    mask = is_pareto_front(df)
    return df[mask].copy()

def maybe_plot(df: pd.DataFrame, outdir: Path):
    """
    Make a few basic plots if matplotlib is available.
    If not installed, just skip plotting.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[INFO] matplotlib not installed; skipping plots.")
        return

    outdir.mkdir(parents=True, exist_ok=True)

    # Main tradeoff plot: throughput vs avg latency
    plt.figure()
    plt.scatter(df["avg_latency"], df["throughput"])
    plt.xlabel("Average Latency (ms)")
    plt.ylabel("Throughput (ops/sec)")
    plt.title("Throughput vs Latency")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(outdir / "throughput_vs_latency.png", dpi=200)

    # Pareto-only highlight
    pareto_df = df[df["pareto"]]

    plt.figure()
    plt.scatter(df["avg_latency"], df["throughput"], alpha=0.3)
    plt.scatter(pareto_df["avg_latency"], pareto_df["throughput"])
    plt.xlabel("Average Latency (ms)")
    plt.ylabel("Throughput (ops/sec)")
    plt.title("Pareto-Optimal Configurations")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(outdir / "pareto_frontier.png", dpi=200)

    # Example: throughput vs clients, one line per pipeline
    plt.figure()
    for p in sorted(df["pipeline"].unique()):
        subset = df[df["pipeline"] == p].sort_values("clients")
        plt.plot(subset["clients"], subset["throughput"], marker="o", label=f"pipe={p}")
    plt.xlabel("Clients")
    plt.ylabel("Throughput (ops/sec)")
    plt.title("Throughput vs Clients (by pipeline)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / "throughput_vs_clients_by_pipeline.png", dpi=200)

    print(f"[INFO] Plots written to: {outdir}")


def main():
    parser = argparse.ArgumentParser(
        description="Process Redis throughput/latency JSON and find best configs."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("throughput.json"),
        help="Path to throughput.json (default: throughput.json)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("throughput_flat.csv"),
        help="Output CSV path (default: throughput_flat.csv)",
    )
    parser.add_argument(
        "--plots-dir",
        type=Path,
        default=Path("plots"),
        help="Directory to store plots (default: plots/)",
    )
    args = parser.parse_args()

    df = load_and_flatten(args.input)
    print("[INFO] Loaded and flattened data:")
    # print(df)

    # Compute Pareto frontier (throughput vs avg_latency)
    pareto_df = get_pareto_configs(df)

    pareto_df = pareto_df.sort_values(
        by=["throughput", "avg_latency"],
        ascending=[False, True]
    )

    print(pareto_df)
    df["pareto"] = is_pareto_front(df)

    # Save full data
    df.to_csv(args.csv, index=False)
    print(f"[INFO] Wrote flattened data to: {args.csv}")

    # Show top Pareto configs
    pareto_df = df[df["pareto"]].copy()
    pareto_df = pareto_df.sort_values(
        by=["throughput", "avg_latency"], ascending=[False, True]
    )
    print("\n[INFO] Pareto-optimal configurations (best throughput/latency tradeoff):")
    print(pareto_df.to_string(index=False))

    # Try to make plots
    maybe_plot(df, args.plots_dir)


if __name__ == "__main__":
    main()
