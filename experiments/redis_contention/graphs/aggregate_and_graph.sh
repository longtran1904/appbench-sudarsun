RESULTS_BASE="$1"
CONFIGS="$2"
RESULTS_DIR="$3"

python3 graphs/aggregate_combined_results.py --result_dir "$RESULTS_BASE/$CONFIGS" --output "$RESULTS_DIR/combined_results.json"

# python3 graphs/aggregate_analysis_results.py --result_dir "$RESULTS_BASE/$CONFIGS" --output "$RESULTS_DIR/results.json"
python3 graphs/plot_loaded_pairs_mbs.py --input "$RESULTS_DIR/combined_results.json" --output "$RESULTS_DIR/plot_loaded_pairs_mbs.png"
python3 graphs/plot_loaded_pairs_throughput.py --input "$RESULTS_DIR/combined_results.json" --output "$RESULTS_DIR/plot_loaded_pairs_throughput.png"