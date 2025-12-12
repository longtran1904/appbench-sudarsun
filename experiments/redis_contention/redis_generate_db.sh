#!/usr/bin/env bash
set -euo pipefail
set -x

# --- paths (change via env or keep defaults) ---
CODEBASE="${CODEBASE:-$APPBENCH}"
REDIS_DIR="${REDIS_DIR:-$CODEBASE/redis-3.0.0/src}"
REDIS_SERVER="${REDIS_SERVER:-$REDIS_DIR/redis-server}"
REDIS_BENCH="${REDIS_BENCH:-$REDIS_DIR/redis-benchmark}"
REDIS_CLI="${REDIS_CLI:-$REDIS_DIR/redis-cli}"
REDIS_CONF="${REDIS_CONF:-$CODEBASE/redis-3.0.0/redis_save_db.conf}"
OUTPUT="${OUTPUT:-${OUTPUTDIR:-$PWD}/redis}"
FLUSH="${FLUSH:-1}"               # set FLUSH=1 to drop caches (needs sudo)

# --- REDIS run params (env overrides) ---
# KEY/DATASIZE patterns: R=random, S=sequential, G=Gaussian, Z=zipfian
HOST="${HOST:-127.0.0.1}"
# Performance params
CLIENTS="${CLIENTS:-1024}"
THREADS="${THREADS:-4}"
PIPELINE="${PIPELINE:-10}"

# Number of Loaded Client-Server Pairs
LOADED_PAIRS="${LOADED_PAIRS:-0}"

# Redis configs
REDIS_PORT="${REDIS_PORT:-${PORT:-6500}}"
REDIS_TESTTIME="${REDIS_TESTTIME:-60}"       # seconds
REDIS_DATASIZE_RANGE="${REDIS_DATASIZE_RANGE:-4-2048}" # bytes
REDIS_DATASIZE_PATTERN="${REDIS_DATASIZE_PATTERN:-R}"  
REDIS_KEY_MAXIMUM="${REDIS_KEY_MAXIMUM:-1000000}"
REDIS_KEY_PATTERN="${REDIS_KEY_PATTERN:-S:R}"
REDIS_RATIO="${REDIS_RATIO:-1:0}"           # SET:GET ratio
REDIS_OUTPUT="${REDIS_OUTPUT:-$OUTPUT/redis.out}"
REDIS_HISTOGRAM_FILE="${REDIS_HISTOGRAM_FILE:-$OUTPUT/latency.out}"
SERVER_LOG="${SERVER_LOG:-$OUTPUT/server.log}"

# Optional prefixes (e.g., taskset/numactl) for pinning
REDIS_PREFIX="${REDIS_PREFIX:-}"
MEMTIER_PREFIX="${MEMTIER_PREFIX:-}"

flush() {
  [ "$FLUSH" = "1" ] && sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' || true
}

echo "==> starting redis-server on $HOST:$REDIS_PORT"

flush # Flush page cache

# start server in foreground, background the process; capture PID
echo "Printing server log to: $SERVER_LOG"
echo "==> redis-server: ${REDIS_PREFIX:+$REDIS_PREFIX }$REDIS_SERVER ${REDIS_CONF:+$REDIS_CONF} --bind $HOST --port $REDIS_PORT --daemonize no >$SERVER_LOG 2>&1 &"

rm -f "$READY_FLAG" 2>/dev/null || true

${REDIS_PREFIX:+$REDIS_PREFIX }"$REDIS_SERVER" ${REDIS_CONF:+$REDIS_CONF} \
    --bind "$HOST" --port "$REDIS_PORT" --daemonize no > "$SERVER_LOG" 2>&1 &

SRV_PID=$!
echo "[SERVER PID]: $SRV_PID"

# wait until it answers PING (max ~20s)
for i in {1..100}; do
    if "$REDIS_CLI" -h "$HOST" -p "$REDIS_PORT" PING >/dev/null 2>&1; then
        READY=1
        echo "[INFO] Redis is ready on $HOST:$REDIS_PORT (after $((i * 200)) ms)"
        echo "READY" > "${READY_FLAG}"
        break
    fi
    sleep 0.2
done

if [ "$READY" -ne 1 ]; then
    echo "[ERROR] Redis on $HOST:$REDIS_PORT did NOT respond to PING after $((MAX_WAIT * 200)) ms" >&2
    echo "[ERROR] Check server log: $SERVER_LOG" >&2
    # Optional: show last few lines to make debugging easier
    if [ -f "$SERVER_LOG" ]; then
        echo "---- tail $SERVER_LOG ----" >&2
        tail -n 20 "$SERVER_LOG" >&2 || true
        echo "--------------------------" >&2
    fi
    exit 1
fi

echo "==> starting memtier_benchmark ${MEMTIER_PREFIX:+$MEMTIER_PREFIX }memtier_benchmark --port "$REDIS_PORT" --test-time="$REDIS_TESTTIME" \
    --clients "$CLIENTS" --threads "$THREADS" --pipeline "$PIPELINE" \
    --random-data --data-size-range="$REDIS_DATASIZE_RANGE" \
    --data-size-pattern="$REDIS_DATASIZE_PATTERN" --key-maximum="$REDIS_KEY_MAXIMUM" \
    --ratio="$REDIS_RATIO" --hide-histogram \
    --out-file="$REDIS_OUTPUT" --hdr-file-prefix="$REDIS_HISTOGRAM_FILE" 2>&1 &"

${MEMTIER_PREFIX:+$MEMTIER_PREFIX }memtier_benchmark --port "$REDIS_PORT" --requests='allkeys' \
  --clients "$CLIENTS" --threads "$THREADS" --pipeline "$PIPELINE" \
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