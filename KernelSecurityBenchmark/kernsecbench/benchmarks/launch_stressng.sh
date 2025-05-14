#!/bin/bash
set -euo pipefail


AUX_LOG_PATH="/dev/virtio-ports/host-port"

echo "[TAG: RUNNING STRESSNG-BENCH]"

echo "Starting stressng-bench..."
echo "2,3,4,8,9,10,11,12,13,14,15,16,17,19,20,21,22,23,27,28,31,37,39" | phoronix-test-suite batch-run stress-ng >> $AUX_LOG_PATH 2>&1

latest_result=$(
  phoronix-test-suite list-saved-results | \
  awk '/^[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{4}/ {print $1; exit}'
)

if [[ -z "${latest_result:-}" ]]; then
  echo "No date‑style saved results found." >&2
  exit 1
fi

echo "Latest saved result: $latest_result"
# Dump the result to the terminal in plain text.
phoronix-test-suite result-file-to-text "$latest_result"
echo "[TAG: AUX STRESSNG-BENCH RESULTS]" >> "$AUX_LOG_PATH"
phoronix-test-suite result-file-to-text "$latest_result" >> "$AUX_LOG_PATH"
echo "[TAG: AUX STRESSNG-BENCH RESULTS END]" >> "$AUX_LOG_PATH"

echo "[TAG: STRESSNG-BENCH COMPLETE]"
