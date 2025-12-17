#!/usr/bin/env bash
set -euo pipefail

# How many client-server pairs
# You can tweak this or drive from CLI args.
# PAIRS_CORES=(
#   "1,2-3"   # pair 0: server core 0, client core 1-2
#   "4,5-6"   # pair 1: server core 3, client core 4-5
#   "7,8-9"   # pair 2: server core 6, client core 7-8
#   "10,11-12"   # pair 3: server core 9, client core 10-11
#   "13,14-15"   # pair 4: server core 12, client core 13-14
#   "33,34-35"   # pair 5: server core 32, client core 33-34
#   "36,37-38"   # pair 6: server core 35, client core 36-37
#   "39,40-41"   # pair 7: server core 38, client core 39-40
#   "42,43-44"   # pair 8: server core 41, client core 42-43
#   "45,46-47"   # pair 9: server core 44, client core 45-46
# )

PAIRS_CORES=()
for ((core=0; core<=160; core+=4)); do
    PAIRS_CORES+=("${core},$((core + 2))")
done
echo "Configured ${#PAIRS_CORES[@]} client-server pairs."

declare -a client_arr=("4")
declare -a thread_arr=("1")
declare -a pipeline_arr=("1")
# declare -a client_arr=("1" "2" "4" "8" "16")
# declare -a thread_arr=("1" "2" "4" "8")
# declare -a pipeline_arr=("1" "8" "16" "32" "64" "128" "256")
declare -a multi_get_arr=("50")

declare -a key_maximum_arr=("1000000")

BASE_PORT=6500

MAX_LOADED_PAIRS=$(( ${#PAIRS_CORES[@]} - 1 ))
# MAX_LOADED_PAIRS=$(( ${#PAIRS_CORES[@]} - 70 ))

for REDIS_KEY_MAXIMUM in "${key_maximum_arr[@]}"; do
    for CLIENTS in "${client_arr[@]}"; do
        for THREADS in "${thread_arr[@]}"; do
            for PIPELINE in "${pipeline_arr[@]}"; do
                for MULTI_GET_COUNT in "${multi_get_arr[@]}"; do
                    # Increase 4 pairs every iteration
                    for LOAD_PAIRS in $(seq 0 4 "$MAX_LOADED_PAIRS"); do
                        for i in "${!PAIRS_CORES[@]}"; do
                            if (( i != 0 && i > (LOAD_PAIRS - 1) )); then
                                # This load pair is not active in this run
                                continue
                            fi

                            echo "---- RUN: clients=$CLIENTS threads=$THREADS pipeline=$PIPELINE multi_key=$MULTI_GET_COUNT ----"

                            CONFIGS="clients_${CLIENTS}_threads_${THREADS}_pipeline_${PIPELINE}_multi_key_${MULTI_GET_COUNT}"
                            # RESULTS_DIR="contention/$CONFIGS"
                            # RESULTS_BASE="redis_numactl_same_node_vtune"
                            RESULTS_BASE="redis_numactl_same_node_3"
                            RESULTS_DIR="${RESULTS_BASE}/${CONFIGS}/loaded_pairs_${LOAD_PAIRS}"
                            VTUNE_RES="${RESULTS_BASE}/loaded_pairs_${LOAD_PAIRS}"
                            READY_FLAG="${PWD}/${RESULTS_DIR}/ready.txt"
                            RUN_FOLDER="${PWD}/${RESULTS_DIR}/pair_$i"

                            rm -f "$READY_FLAG" 2>/dev/null || true
                            mkdir -p "${PWD}/${RESULTS_DIR}"
                            mkdir -p "$RUN_FOLDER"
                            SERVER_LOG="$RUN_FOLDER/server.log"
                            REDIS_OUTPUT="$RUN_FOLDER/redis.out"
                            REDIS_HISTOGRAM_FILE="$RUN_FOLDER/latency.out"

                            cores="${PAIRS_CORES[$i]}"
                            srv_core="${cores%%,*}"
                            cli_core="${cores##*,}"
                            port=$((BASE_PORT + i))

                            echo "Launching pair $i on port $port (server core $srv_core, client core $cli_core)"

                            # For multi-pair runs, usually you don't want to drop caches each time

                            if [[ "$i" == 0 ]]; then
                            # First pair flushes caches
                                FLUSH=1 \
                                LOADED_PAIRS="$LOAD_PAIRS" \
                                PAIR_INDEX="$i" \
                                CLIENTS="$CLIENTS" THREADS="$THREADS" PIPELINE="$PIPELINE" MULTI_GET_COUNT="$MULTI_GET_COUNT" \
                                VTUNE_DIR="$VTUNE_RES" \
                                VTUNE_LOG="$RUN_FOLDER/vtune.log" \
                                READY_FLAG="$READY_FLAG" \
                                REDIS_PORT="$port" PORT="$port" \
                                SERVER_LOG="$SERVER_LOG" \
                                REDIS_OUTPUT="$REDIS_OUTPUT" \
                                REDIS_HISTOGRAM_FILE="$REDIS_HISTOGRAM_FILE" \
                                REDIS_PREFIX="numactl -C $srv_core --membind=0" \
                                MEMTIER_PREFIX="/usr/bin/time -v numactl -C $cli_core --membind=1" \
                                REDIS_KEY_MAXIMUM="$REDIS_KEY_MAXIMUM" \
                                ./redis_pair_main.sh > "$RUN_FOLDER/redis_pair" 2>&1 &
                            else
                                FLUSH=1 \
                                PAIR_INDEX="$i" \
                                REDIS_PORT="$port" PORT="$port" \
                                READY_FLAG="$READY_FLAG" \
                                SERVER_LOG="$SERVER_LOG" \
                                REDIS_OUTPUT="$REDIS_OUTPUT" \
                                REDIS_HISTOGRAM_FILE="$REDIS_HISTOGRAM_FILE" \
                                REDIS_PREFIX="numactl -C $srv_core --membind=0" \
                                MEMTIER_PREFIX="/usr/bin/time -v numactl -C $cli_core --membind=1" \
                                ./redis_pair_silence.sh > "$RUN_FOLDER/redis_pair" 2>&1 &
                            fi
                        done
                        wait
                        sleep 5  # wait a bit before starting next run
                    done
                done
            done
        done
    done
done 


# Aggregate results & graph
./graphs/aggregate_and_graph.sh "$RESULTS_BASE" "$CONFIGS" "$RESULTS_DIR"

# python3 graphs/aggregate_analysis_results.py --result_dir "$RESULTS_BASE/$CONFIGS" --output "$RESULTS_BASE/results.json"
# python3 graphs/plot_loaded_pairs_mbs.py --input "$RESULTS_BASE/results.json" --output "$RESULTS_BASE/plot_loaded_pairs_mbs.png"
# python3 graphs/plot_loaded_pairs_throughput.py --input "$RESULTS_BASE/results.json" --output "$RESULTS_BASE/plot_loaded_pairs_throughput.png"

echo "All pairs completed."
