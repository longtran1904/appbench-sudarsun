#!/usr/bin/env bash
set -euo pipefail

# Copy dump.rdb to dump_<i>.rdb for i = 0..79
for i in $(seq 0 79); do
    cp dump.rdb "dump_${i}.rdb"
done