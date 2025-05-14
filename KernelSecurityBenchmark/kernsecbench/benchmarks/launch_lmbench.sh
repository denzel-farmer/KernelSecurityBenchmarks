#!/bin/bash
# set -euo pipefail

LMBENCH_DIR="/opt/lmbench"
STATUS_FILE="/tempbench.txt"
RESULTS_PATH="$LMBENCH_DIR/results/x86_64-linux-gnu"
RESULTS_FILE="$RESULTS_PATH/ubuntu-testing.0"

AUX_LOG_PATH="/dev/virtio-ports/host-port"

cd $LMBENCH_DIR
echo "[TAG: RUNNING LMBENCH]"

# List existing files in results and delete them
echo "=== Deleting old results ==="
ls -l "$RESULTS_PATH"
rm -rf "$RESULTS_PATH" "$STATUS_FILE"
mkdir -p "$RESULTS_PATH"
echo "=== Starting new benchmark ==="

echo "Tailing status file: $STATUS_FILE"
# follow progress live
tail -F "$STATUS_FILE" &
TAIL_PID=$!

# time the rerun
start=$(date +%s.%N)
make rerun
echo "temp" > $RESULTS_PATH/tempout.txt
end=$(date +%s.%N)

# stop tail
kill "$TAIL_PID" 2>/dev/null || true

echo
echo "=== Benchmark complete; dumping results at $RESULTS_FILE to aux log ==="
echo "[TAG: AUX LMBENCH RESULTS]" > "$AUX_LOG_PATH"
cat "$RESULTS_FILE" > "$AUX_LOG_PATH"
echo "[TAG: AUX LMBENCH RESULTS END]" >> "$AUX_LOG_PATH"
echo "[TAG: AUX LMBENCH RESULTS BASE64]" >> "$AUX_LOG_PATH"
base64 "$RESULTS_FILE" | tr -d '\n' | tr -d '\r' >> "$AUX_LOG_PATH"
echo "[TAG: AUX LMBENCH RESULTS BASE64 END]" >> "$AUX_LOG_PATH"
echo "============================================"

# # Also base64 encode the results and print as single line
# echo "=== Base64 encoded results ==="
# base64 "$RESULTS_FILE" | tr -d '\n' | tr -d '\r' > "$RESULTS_FILE.b64"
# echo "[TAG: LMBENCH RESULTS=\"$(cat $RESULTS_FILE.b64)\"]"

# report elapsed time
elapsed=$(echo "$end - $start" | bc -l)
echo "Elapsed time: ${elapsed} seconds"

echo "[TAG: LMBENCH COMPLETE]"