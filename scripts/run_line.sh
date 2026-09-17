#!/usr/bin/env bash
# Convenience script: starts the ingest service and all three station
# simulators as background processes. Assumes Mosquitto is already running
# (docker-compose up -d) and dependencies are installed (pip install -r
# requirements.txt).
#
# Usage: ./scripts/run_line.sh [unit_count]
#   unit_count: optional, stops the assembly station after producing this
#               many units. Omit to run indefinitely (Ctrl+C to stop).
set -euo pipefail
cd "$(dirname "$0")/.."

UNIT_COUNT="${1:-}"
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

echo "Starting ingest service..."
python -m ingest.ingest_service > "$LOG_DIR/ingest.log" 2>&1 &
INGEST_PID=$!

echo "Starting pack station..."
python -m stations.pack > "$LOG_DIR/pack.log" 2>&1 &
PACK_PID=$!

echo "Starting test station..."
python -m stations.test > "$LOG_DIR/test.log" 2>&1 &
TEST_PID=$!

sleep 1

echo "Starting assembly station..."
if [ -n "$UNIT_COUNT" ]; then
  python -m stations.assembly "$UNIT_COUNT" > "$LOG_DIR/assembly.log" 2>&1 &
else
  python -m stations.assembly > "$LOG_DIR/assembly.log" 2>&1 &
fi
ASSEMBLY_PID=$!

echo "Line running. PIDs: ingest=$INGEST_PID pack=$PACK_PID test=$TEST_PID assembly=$ASSEMBLY_PID"
echo "Logs in ./$LOG_DIR/. Press Ctrl+C to stop everything."

trap 'echo "Stopping..."; kill $INGEST_PID $PACK_PID $TEST_PID $ASSEMBLY_PID 2>/dev/null || true' EXIT

wait
