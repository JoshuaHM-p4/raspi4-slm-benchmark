#!/usr/bin/env bash
# One measured session for one model, per docs/PROTOCOL_FREEZE.md.
# Usage: scripts/session.sh speed|quality <label> <models/file.gguf>
#   speed:   cool to <= 45.0 C, start monitor.py, run benchmark.py, stop monitor
#   quality: verify the frozen prompt checksum, cool, run collect_answers.py on data/prompts.jsonl
# Outputs: results/raw/<speed|quality>/<label>/ (refuses to reuse it).
set -euo pipefail
(($# == 3)) || { sed -n '2,7p' "$0"; exit 2; }
kind=$1 label=$2 model=$3
out=results/raw/$kind/$label
[[ -e $out ]] && { echo "exists: $out" >&2; exit 1; }
pgrep -x llama-server >/dev/null && { echo "a llama-server is running; stop it first" >&2; exit 1; }
[[ $kind == quality ]] && sha256sum --quiet -c data/prompts.jsonl.sha256

milli() { cat /sys/class/thermal/thermal_zone0/temp; }
waited=0
while (( $(milli) > 45000 && waited < 600 )); do sleep 10; waited=$((waited + 10)); done
mkdir -p "$(dirname "$out")"
start="start_temp_c=$(awk '{printf "%.1f", $1/1000}' /sys/class/thermal/thermal_zone0/temp) waited_s=$waited $(vcgencmd get_throttled)"

case $kind in
  speed)
    mkdir "$out"
    echo "$start" > "$out/session.txt"
    python3 scripts/monitor.py --output "$out/telemetry.csv" & mon=$!
    rc=0
    python3 scripts/benchmark.py --model "$model" --label "$label" --out "$out/bench" || rc=$?
    kill $mon; wait $mon || true  # SIGTERM: background jobs ignore SIGINT; monitor flushes every row
    echo "end_temp=$(vcgencmd measure_temp) $(vcgencmd get_throttled) benchmark_exit=$rc" >> "$out/session.txt"
    cat "$out/session.txt" ;;
  quality)
    rc=0
    python3 scripts/collect_answers.py --model "$model" --label "$label" --prompts data/prompts.jsonl \
      --out "$out" || rc=$?
    echo "$start" > "$out/session.txt"
    echo "end_temp=$(vcgencmd measure_temp) $(vcgencmd get_throttled) collect_exit=$rc" >> "$out/session.txt"
    cat "$out/session.txt" ;;
  *) echo "unknown kind: $kind" >&2; exit 2 ;;
esac
exit $rc
