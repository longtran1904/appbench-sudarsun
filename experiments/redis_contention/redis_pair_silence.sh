#!/usr/bin/env bash
set -euo pipefail
set -x

# --- paths (change via env or keep defaults) ---
CODEBASE="${CODEBASE:-$APPBENCH}"
REDIS_DIR="${REDIS_DIR:-$CODEBASE/redis-3.0.0/src}"
REDIS_SERVER="${REDIS_SERVER:-$REDIS_DIR/redis-server}"
REDIS_BENCH="${REDIS_BENCH:-$REDIS_DIR/redis-benchmark}"
REDIS_CLI="${REDIS_CLI:-$REDIS_DIR/redis-cli}"
REDIS_CONF="${REDIS_CONF:-$CODEBASE/redis-3.0.0/redis.conf}"
OUTPUT="${OUTPUT:-${OUTPUTDIR:-$PWD}/redis}"
FLUSH="${FLUSH:-1}"               # set FLUSH=1 to drop caches (needs sudo)

# --- REDIS run params (env overrides) ---
# KEY/DATASIZE patterns: R=random, S=sequential, G=Gaussian, Z=zipfian
HOST="${HOST:-127.0.0.1}"
# Performance params
# CLIENTS="${CLIENTS:-16}"
# THREADS="${THREADS:-4}"
# PIPELINE="${PIPELINE:-100}"
CLIENTS="${CLIENTS:-4}"
THREADS="${THREADS:-1}"
PIPELINE="${PIPELINE:-1}"
MULTI_GET_COUNT="${MULTI_GET_COUNT:-50}"

# Honor REDIS_PORT first, then PORT, fall back to 6500
REDIS_PORT="${REDIS_PORT:-${PORT:-6500}}"
REDIS_TESTTIME="${REDIS_TESTTIME:-60}"       # seconds
REDIS_DATASIZE_RANGE="${REDIS_DATASIZE_RANGE:-4-2048}" # bytes
REDIS_DATASIZE_PATTERN="${REDIS_DATASIZE_PATTERN:-R}"  
REDIS_KEY_MAXIMUM="${REDIS_KEY_MAXIMUM:-1000000}"
REDIS_KEY_PATTERN="${REDIS_KEY_PATTERN:-R:R}"
REDIS_RATIO="${REDIS_RATIO:-0:1}"           # SET:GET ratio
REDIS_OUTPUT="${REDIS_OUTPUT:-$OUTPUT/redis.out}"
REDIS_HISTOGRAM_FILE="${REDIS_HISTOGRAM_FILE:-$OUTPUT/latency.out}"
SERVER_LOG="${SERVER_LOG:-$OUTPUT/server.log}"

# Optional prefixes (e.g., taskset/numactl) for pinning
REDIS_PREFIX="${REDIS_PREFIX:-}"
MEMTIER_PREFIX="${MEMTIER_PREFIX:-}"

echo "==> starting redis-server on $HOST:$REDIS_PORT"

# start server in foreground, background the process; capture PID
echo "Printing server log to: $SERVER_LOG"
${REDIS_PREFIX:+$REDIS_PREFIX }"$REDIS_SERVER" ${REDIS_CONF:+$REDIS_CONF} \
  --bind "$HOST" --port "$REDIS_PORT" --daemonize no > "$SERVER_LOG" \
  --dir "./databases" --dbfilename "dump_${PAIR_INDEX}.rdb" 2>&1 &

SRV_PID=$!
echo "[SERVER PID]: $SRV_PID"

echo "Waiting for Redis to finish loading RDB (watching log: $SERVER_LOG)..."
while true; do
    # Check if the log already contains the magic string
    if grep -q "DB loaded from disk" "$SERVER_LOG"; then
        echo "Detected 'DB loaded from disk' in log. RDB load complete."
        break
    fi

    sleep 1
done

# wait for READY_FLAG file to have content
echo "waiting for READY_FLAG: ${READY_FLAG:-}"
while [ ! -s "${READY_FLAG:-}" ]; do
  sleep 0.1
done

${MEMTIER_PREFIX:+$MEMTIER_PREFIX }memtier_benchmark --port "$REDIS_PORT" --test-time="$REDIS_TESTTIME" \
  --clients "$CLIENTS" --threads "$THREADS" --pipeline "$PIPELINE" --multi-key-get "$MULTI_GET_COUNT" \
  --random-data --data-size-range="$REDIS_DATASIZE_RANGE" \
  --data-size-pattern="$REDIS_DATASIZE_PATTERN" --key-maximum="$REDIS_KEY_MAXIMUM" \
  --ratio="$REDIS_RATIO" --hide-histogram \
  --out-file="$REDIS_OUTPUT" --hdr-file-prefix="$REDIS_HISTOGRAM_FILE" 2>&1 &
MEMTIER_PID=$!
echo "[MEMTIER PID]: $MEMTIER_PID"

wait "$MEMTIER_PID" 2>/dev/null || true
kill "$SRV_PID" >/dev/null 2>&1 || true
wait "$SRV_PID" 2>/dev/null || true
echo "Done. Output: $REDIS_OUTPUT"

set -x