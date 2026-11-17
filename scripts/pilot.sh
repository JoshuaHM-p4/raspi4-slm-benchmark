#!/usr/bin/env bash
# Phase 4 pilot for one model: a short llama-bench microbenchmark, then the two non-scored pilot prompts.
# Usage: scripts/pilot.sh <label> <models/file.gguf>
set -euo pipefail
(($# == 2)) || { sed -n '2,3p' "$0"; exit 2; }
label=$1 model=$2
out=results/raw/pilot/$label
[[ -e $out ]] && { echo "exists: $out" >&2; exit 1; }
mkdir -p "$out"
bench=(vendor/llama.cpp/build/bin/llama-bench -m "$model" -t 4 -ngl 0 -b 128 -ub 128 -p 128 -n 32 -r 1 -o jsonl)
printf '%q ' "${bench[@]}" > "$out/microbench.command.txt"
{ vcgencmd measure_temp; vcgencmd get_throttled; } > "$out/microbench.before.txt"
/usr/bin/time -f 'peak_rss_kib=%M\nelapsed_seconds=%e\nexit_code=%x' -o "$out/microbench.resources.txt" \
  "${bench[@]}" > "$out/microbench.jsonl" 2> "$out/microbench.stderr.log" || echo "microbench failed; see $out" >&2
{ vcgencmd measure_temp; vcgencmd get_throttled; } > "$out/microbench.after.txt"
python3 scripts/collect_answers.py --model "$model" --label "$label" --prompts data/pilot_prompts.jsonl \
  --out "$out/answers"
