#!/usr/bin/env python3
"""
Aggregate Redis experiment results from multiple directories.
Extracts throughput (Ops/sec) from redis.out files and organizes them
by clients, threads, and pipeline configuration.
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
        tuple: (ops_per_sec, avg_latency, p99_latency, p99_9_latency) or (None, None, None, None) if not found
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
                        avg_latency = float(parts[4])
                        p99_latency = float(parts[6])
                        p99_9_latency = float(parts[7])
                        return ops_per_sec, avg_latency, p99_latency, p99_9_latency
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return None, None, None, None

def parse_folder_name(folder_name):
    """
    Parse folder name to extract clients, threads, and pipeline values.
    
    Format: clients_X_threads_Y_pipeline_Z
    
    Args:
        folder_name: Name of the directory
        
    Returns:
        tuple: (clients, threads, pipeline, key_maximum) as integers, or None if parsing fails
    """
    match = re.match(r'clients_(\d+)_threads_(\d+)_pipeline_(\d+)_key_maximum_(\d+)', folder_name)
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4)))
    return None

def aggregate_results(base_path):
    """
    Aggregate all results from the redis_multi/pair_0 directory.
    
    Args:
        base_path: Path to the directory containing all configuration folders
        
    Returns:
        dict: Nested dictionary with structure result[clients][threads][pipeline] = {throughput, latency}
    """
    result = defaultdict(lambda: defaultdict(dict))
    
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
        
        clients, threads, pipeline, key_maximum = parsed
        
        # Look for redis.out file
        redis_out_path = os.path.join(folder_path, 'loaded_pairs_0', 'pair_0', 'redis.out')
        if not os.path.exists(redis_out_path):
            print(f"Warning: redis.out not found in {folder_path}")
            continue
        
        # Extract metrics
        ops_per_sec, avg_latency, p99_latency, p99_9_latency = extract_metrics(redis_out_path)
        if ops_per_sec is None:
            print(f"Warning: Could not extract metrics from {redis_out_path}")
            continue
        
        # Store in nested dictionary
        result[clients][threads][pipeline] = {
            "throughput_ops_sec": ops_per_sec,
            "avg_latency_ms": avg_latency,
            "p99_latency_ms": p99_latency,
            "p99_9_latency_ms": p99_9_latency
        }
        print(f"Processed: clients={clients}, threads={threads}, pipeline={pipeline}, Ops/sec={ops_per_sec:.2f}, Avg Latency={avg_latency:.4f}ms, P99={p99_latency:.4f}ms, P99.9={p99_9_latency:.4f}ms")
    
    # Convert defaultdicts to regular dicts
    return {k: {k2: dict(v2) for k2, v2 in v.items()} for k, v in result.items()}

def save_results(result, output_path):
    """
    Save results to a JSON file in grouped summary format.
    
    Args:
        result: The nested dictionary with results
        output_path: Path to save the JSON file
    """
    # Build grouped summary structure
    configurations = {}
    for clients in sorted(result.keys()):
        clients_key = f"clients_{clients}"
        configurations[clients_key] = {}
        for threads in sorted(result[clients].keys()):
            threads_key = f"threads_{threads}"
            configurations[clients_key][threads_key] = {}
            for pipeline in sorted(result[clients][threads].keys()):
                pipeline_key = f"pipeline_{pipeline}"
                configurations[clients_key][threads_key][pipeline_key] = result[clients][threads][pipeline]
    
    # Count total configurations
    total_configs = sum(
        len(result[clients][threads])
        for clients in result
        for threads in result[clients]
    )
    
    # Create output with metadata and grouped structure
    output_data = {
        "metadata": {
            "experiment": "redis_contention",
            "total_configurations": total_configs,
            "data_source": "redis_multi/pair_0",
            "metrics": ["throughput_ops_sec", "avg_latency_ms", "p99_latency_ms", "p99_9_latency_ms"]
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
  python3 aggregate_results.py /path/to/redis_multi/pair_0
  python3 aggregate_results.py /path/to/redis_multi/pair_0 --output results.json
        '''
    )
    parser.add_argument(
        '-r', '--result_dir',
        default = './redis_multi/pair_0',
        help='Path to the directory containing all configuration folders'
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
    print(f"Total configurations found: {sum(len(threads) for clients_dict in result.values() for threads in clients_dict.values())}")
    print(f"\nResult structure: result[clients][threads][pipeline] = Metrics")
    
    # Save results to JSON file
    print("\n" + "="*50)
    save_results(result, output_file)
    
    # Print a sample of the results
    print(f"\nSample of results:")
    for clients in sorted(result.keys())[:2]:  # Show first 2 client counts
        print(f"\nClients: {clients}")
        for threads in sorted(result[clients].keys())[:2]:  # Show first 2 thread counts
            print(f"  Threads: {threads}")
            for pipeline in sorted(result[clients][threads].keys())[:3]:  # Show first 3 pipelines
                metrics = result[clients][threads][pipeline]
                throughput = metrics["throughput_ops_sec"]
                avg_lat = metrics["avg_latency_ms"]
                p99_lat = metrics["p99_latency_ms"]
                p99_9_lat = metrics["p99_9_latency_ms"]
                print(f"    Pipeline: {pipeline:3d} -> Throughput: {throughput:12.2f} Ops/sec, Avg: {avg_lat:8.4f}ms, P99: {p99_lat:8.4f}ms, P99.9: {p99_9_lat:8.4f}ms")
    
    return result

if __name__ == '__main__':
    result = main()
