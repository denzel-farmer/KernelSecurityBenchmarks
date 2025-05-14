#!/bin/bash
set -euo pipefail


AUX_LOG_PATH="/dev/virtio-ports/host-port"

echo "[TAG: RUNNING INKSCAPE-BENCH]"

echo "Starting inkscape-bench..."
phoronix-test-suite batch-run system/inkscape >> $AUX_LOG_PATH 2>&1

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
echo "[TAG: AUX INKSCAPE-BENCH RESULTS]" >> "$AUX_LOG_PATH"
phoronix-test-suite result-file-to-text "$latest_result" >> "$AUX_LOG_PATH"
echo "[TAG: AUX INKSCAPE-BENCH RESULTS END]" >> "$AUX_LOG_PATH"

echo "[TAG: INKSCAPE-BENCH COMPLETE]"
