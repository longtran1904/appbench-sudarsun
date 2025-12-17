#!/usr/bin/env python3
"""
Aggregate Redis experiment results across all pair_* subdirectories within each loaded_pairs_* folder.
Combined throughput and bandwidth are summed per loaded_pairs bucket; latency figures are averaged.
"""

import os
import re
import json
import argparse
from collections import defaultdict

def extract_metrics(file_path):
    """
    Extract metrics from the 'Totals' line in redis.out file.
    
    Args:
        file_path: Path to the redis.out file
        
    Returns:
        tuple: (ops_per_sec, KB/s, avg_latency, p99_latency, p99_9_latency) or (None, None, None, None) if not found
    """
    try:
        with open(file_path, 'r') as f:
            for line in f:
                if 'Totals' in line:
                    # Extract metrics from Totals line
                    # Format: "Totals     762397.11     0.00    381198.55    53.59558    50.94300   131.07100   175.10300 ..."
                    # Index:  1           2              3         4             5            6           7           8
                    parts = line.split()
                    if len(parts) >= 8:
                        ops_per_sec = float(parts[1])
                        kb_per_sec = float(parts[8])
                        avg_latency = float(parts[4])
                        p99_latency = float(parts[6])
                        p99_9_latency = float(parts[7])
                        return ops_per_sec, kb_per_sec, avg_latency, p99_latency, p99_9_latency
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return None, None, None, None, None
def parse_folder_name(folder_name):
    """
    Parse folder name to extract clients, threads, and pipeline values.
    
    Format: clients_X_threads_Y_pipeline_Z_multi_key_M
    
    Args:
        folder_name: Name of the directory
        
    Returns:
        tuple: (clients, threads, pipeline, multi_get) as integers, or None if parsing fails
    """
    # match = re.match(r'clients_(\d+)_threads_(\d+)_pipeline_(\d+)', folder_name)
    match = re.match(r'loaded_pairs_(\d+)', folder_name)
    if match:
        return int(match.group(1))
    return None

def aggregate_results(base_path):
    """
    Aggregate all results from the redis_multi directory by summing metrics across all pair_* folders
    inside each loaded_pairs_* directory.
    
    Args:
        base_path: Path to the directory containing all configuration folders
        
    Returns:
        dict: result[loaded_pairs] = aggregated metrics
    """
    result = {}

    # Iterate through all folders in the base path
    for folder_name in os.listdir(base_path):
        folder_path = os.path.join(base_path, folder_name)

        # Skip if not a directory
        if not os.path.isdir(folder_path):
            continue

        # Parse folder name
        parsed = parse_folder_name(folder_name)
        if parsed is None:
            print(f"Skipping folder {folder_name}: could not parse configuration")
            continue

        loaded_pairs = parsed

        # Collect metrics from every pair_* folder
        pair_metrics = []
        for pair_folder in sorted(os.listdir(folder_path)):
            pair_path = os.path.join(folder_path, pair_folder)
            if not os.path.isdir(pair_path) or not pair_folder.startswith('pair_'):
                continue

            # print(f"loaded_pairs_folder: {folder_name}")
            if folder_name == "loaded_pairs_4":
                print(f"loaded_pairs_folder: {folder_name}")
                print(f"Aggregating metrics from {pair_folder}...")
            redis_out_path = os.path.join(pair_path, 'redis.out')
            if not os.path.exists(redis_out_path):
                print(f"Warning: redis.out not found in {pair_path}")
                continue

            ops_per_sec, kb_per_sec, avg_latency, p99_latency, p99_9_latency = extract_metrics(redis_out_path)
            if ops_per_sec is None:
                print(f"Warning: Could not extract metrics from {redis_out_path}")
                continue

            pair_metrics.append((ops_per_sec, kb_per_sec, avg_latency, p99_latency, p99_9_latency))
        
        if folder_name == "loaded_pairs_4":
            print(f"loaded_pairs_folder: {folder_name}")
            print(f"collected_metrics: {pair_metrics}")
            

        if not pair_metrics:
            print(f"Warning: No valid pair_* metrics found in {folder_path}")
            continue

        total_ops = sum(m[0] for m in pair_metrics)
        total_kb = sum(m[1] for m in pair_metrics)

        # Average latency figures across pairs (best-effort summary)
        avg_latency_vals = [m[2] for m in pair_metrics if m[2] is not None]
        p99_latency_vals = [m[3] for m in pair_metrics if m[3] is not None]
        p99_9_latency_vals = [m[4] for m in pair_metrics if m[4] is not None]

        avg_latency = sum(avg_latency_vals) / len(avg_latency_vals) if avg_latency_vals else None
        p99_latency = sum(p99_latency_vals) / len(p99_latency_vals) if p99_latency_vals else None
        p99_9_latency = sum(p99_9_latency_vals) / len(p99_9_latency_vals) if p99_9_latency_vals else None

        result[loaded_pairs] = {
            "throughput_ops_sec": total_ops,
            "KB/s": total_kb,
            "avg_latency_ms": avg_latency,
            "p99_latency_ms": p99_latency,
            "p99_9_latency_ms": p99_9_latency,
            "pair_count": len(pair_metrics)
        }

        def fmt_latency(value):
            return f"{value:.4f}" if value is not None else "n/a"

        print(
            f"Processed: loaded_pairs={loaded_pairs}, pairs={len(pair_metrics)}, "
            f"Combined Ops/sec={total_ops:.2f}, Combined KB/s={total_kb:.2f}, "
            f"Avg Latency={fmt_latency(avg_latency)}ms, "
            f"P99={fmt_latency(p99_latency)}ms, "
            f"P99.9={fmt_latency(p99_9_latency)}ms"
        )

    return result

def save_results(result, input_dir, output_path):
    """
    Save results to a JSON file in grouped summary format.
    
    Args:
        result: The nested dictionary with results
        output_path: Path to save the JSON file
    """
    # Build grouped summary structure
    configurations = {}
    for loaded_pairs in sorted(result.keys()):
        loaded_pairs_key = f"loaded_pairs_{loaded_pairs}"
        configurations[loaded_pairs_key] = result[loaded_pairs]
    
    # Count total configurations
    total_configs = sum(
        1 for _ in result.keys()
    )
    
    # Create output with metadata and grouped structure
    output_data = {
        "metadata": {
            "experiment": "redis_contention",
            "total_configurations": total_configs,
            "data_source": input_dir,
            "metrics": ["throughput_ops_sec", "KB/s", "avg_latency_ms", "p99_latency_ms", "p99_9_latency_ms", "pair_count"]
        },
        "configurations": configurations
    }
    
    try:
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"Results saved to: {output_path}")
    except Exception as e:
        print(f"Error saving results: {e}")

def main():
    """Main function to run the aggregation."""
    parser = argparse.ArgumentParser(
        description='Aggregate Redis experiment results from multiple directories.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    python3 aggregate_results.py /path/to/combined_bandwidth_contention/clients_4_threads_1_pipeline_1_multi_key_50
    python3 aggregate_results.py /path/to/redis_multi_pairs --output results.json
        '''
    )
    parser.add_argument(
        '-r', '--result_dir',
                default = './combined_bandwidth_contention/clients_4_threads_1_pipeline_1_multi_key_50',
                help='Path to the directory containing loaded_pairs_* folders'
    )
    parser.add_argument(
        '-o', '--output',
        default= 'aggregated_results.json',
        help='Output JSON file path (default: aggregated_results.json in the result directory)'
    )
    
    args = parser.parse_args()
    
    base_path = args.result_dir
    if args.output:
        output_file = args.output
    else:
        output_file = os.path.join(base_path, 'aggregated_results.json')
    
    if not os.path.exists(base_path):
        print(f"Error: Path does not exist: {base_path}")
        return
    
    print(f"Aggregating results from {base_path}...\n")
    
    result = aggregate_results(base_path)
    
    print(f"\n{'='*50}")
    print("Aggregation Complete!")
    print(f"{'='*50}")
    print(f"Total configurations found: {len(result)}")
    print(f"\nResult structure: result[loaded_pairs] = Metrics")
    
    # Save results to JSON file
    print("\n" + "="*50)
    save_results(result, base_path, output_file)
    
    # Print a sample of the results
    print(f"\nSample of results:")
    for loaded_pairs in sorted(result.keys())[:2]:  # Show first 2 client counts
        print(f"\nLoaded Pairs: {loaded_pairs}")
        metrics = result[loaded_pairs]
        throughput = metrics["throughput_ops_sec"]
        avg_lat = metrics["avg_latency_ms"]
        p99_lat = metrics["p99_latency_ms"]
        p99_9_lat = metrics["p99_9_latency_ms"]
        pair_count = metrics.get("pair_count", 1)
        print(
            f"    Loaded_pairs: {loaded_pairs:3d} (pairs={pair_count:2d}) -> "
            f"Throughput: {throughput:12.2f} Ops/sec, Avg: {avg_lat:8.4f}ms, "
            f"P99: {p99_lat:8.4f}ms, P99.9: {p99_9_lat:8.4f}ms"
        )
    
    return result

if __name__ == '__main__':
    result = main()
