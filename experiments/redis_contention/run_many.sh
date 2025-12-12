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

PAIRS_CORES=(
    "1,32"
    # "2,33"
    # "3,34"
    # "4,35"
    # "5,36"
    # "6,37"
    # "7,38"
    # "8,39"
    # "9,40"
    # "10,41"
    # "11,42"
    # "12,43"
    # "13,44"
    # "14,45"
    # "15,46"
)

# declare -a client_arr=("1")
# declare -a thread_arr=("4")
# declare -a pipeline_arr=("1")
# declare -a client_arr=("16" "32")
declare -a client_arr=("16")
declare -a thread_arr=("4")
declare -a pipeline_arr=("100")

declare -a key_maximum_arr=("10000000")

BASE_PORT=6500

MAX_LOADED_PAIRS=$(( ${#PAIRS_CORES[@]} - 1 ))

for REDIS_KEY_MAXIMUM in "${key_maximum_arr[@]}"; do
    for CLIENTS in "${client_arr[@]}"; do
        for THREADS in "${thread_arr[@]}"; do
            for PIPELINE in "${pipeline_arr[@]}"; do
                for LOAD_PAIRS in $(seq 0 "$MAX_LOADED_PAIRS"); do
                    for i in "${!PAIRS_CORES[@]}"; do
                        if (( i != 0 && i > LOAD_PAIRS )); then
                            # This load pair is not active in this run
                            continue
                        fi

                        echo "---- RUN: clients=$CLIENTS threads=$THREADS pipeline=$PIPELINE ----"

                        CONFIGS="clients_${CLIENTS}_threads_${THREADS}_pipeline_${PIPELINE}_key_maximum_${REDIS_KEY_MAXIMUM}"
                        RESULTS_DIR="TEST_DB/$CONFIGS"
                        OUT_BASE="${PWD}/${RESULTS_DIR}/loaded_pairs_${LOAD_PAIRS}"
                        OUTPUT="$OUT_BASE/pair_$i"
                        READY_FLAG="$OUT_BASE/ready.txt"
                        RUN_FOLDER="$OUTPUT/$CONFIGS"

                        rm -f "$READY_FLAG" 2>/dev/null || true
                        mkdir -p "$OUTPUT"
                        mkdir -p "$OUT_BASE"
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
                            CLIENTS="$CLIENTS" THREADS="$THREADS" PIPELINE="$PIPELINE" \
                            VTUNE_DIR="$RESULTS_DIR" \
                            READY_FLAG="$READY_FLAG" \
                            REDIS_PORT="$port" PORT="$port" \
                            SERVER_LOG="$SERVER_LOG" \
                            REDIS_OUTPUT="$REDIS_OUTPUT" \
                            REDIS_HISTOGRAM_FILE="$REDIS_HISTOGRAM_FILE" \
                            REDIS_PREFIX="taskset -c $srv_core" \
                            MEMTIER_PREFIX="/usr/bin/time -v taskset -c $cli_core" \
                            REDIS_KEY_MAXIMUM="$REDIS_KEY_MAXIMUM" \
                            ./redis_pair.sh > "$RUN_FOLDER/redis_pair" 2>&1 &
                        else
                            FLUSH=1 \
                            REDIS_PORT="$port" PORT="$port" \
                            VTUNE_DIR="$RESULTS_DIR" \
                            READY_FLAG="$READY_FLAG" \
                            SERVER_LOG="$SERVER_LOG" \
                            REDIS_OUTPUT="$REDIS_OUTPUT" \
                            REDIS_HISTOGRAM_FILE="$REDIS_HISTOGRAM_FILE" \
                            REDIS_PREFIX="taskset -c $srv_core" \
                            MEMTIER_PREFIX="/usr/bin/time -v taskset -c $cli_core" \
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

# Aggregate results & graph
python3 aggregate.py --result_dir "./$RESULTS_DIR" --output "./$RESULTS_DIR.json"

python3 graph.py --input "./$RESULTS_DIR.json" --output "$RESULTS_DIR/plot_metrics.jpg"

echo "All pairs completed."
