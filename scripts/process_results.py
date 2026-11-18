#!/usr/bin/env python3
"""Regenerate results/processed/*.csv from results/raw and the scores CSVs, and write results/SHA256SUMS.

Deterministic and read-only toward raw evidence: every number in the processed tables is computed
from a committed raw file. Sets or runs that do not exist yet (e.g. unscored vendor answers) are
skipped, not filled. Run from the repository root on the workstation.
"""
import csv
import hashlib
import json
import re
from pathlib import Path

RAW, OUT = Path("results/raw"), Path("results/processed")
MODELS = ["qwen35-08b-q4km", "lfm25-12b-q4km", "gemma4-e2b-q4_0"]
NAMES = {"qwen35-08b-q4km": "Qwen3.5-0.8B Q4_K_M", "lfm25-12b-q4km": "LFM2.5-1.2B-Instruct Q4_K_M",
         "gemma4-e2b-q4_0": "Gemma 4 E2B-it Q4_0"}
CATEGORIES = ["instruction", "extraction", "reasoning", "summarization", "coding"]
SETS = {"greedy": ("quality", "pilot", Path("data/quality_scores.csv")),
        "vendor": ("quality-vendor", "pilot-vendor", Path("data/quality_scores_vendor.csv"))}


def load(path):
    return json.loads(Path(path).read_text())


def write(name, rows):
    if not rows:
        return
    with (OUT / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{OUT / name}: {len(rows)} rows")


def telemetry_max_temp(path):
    temps = [float(r["temperature_c"]) for r in csv.DictReader(path.open()) if r.get("temperature_c")]
    flags = sorted({r["throttle_flags_raw"] for r in csv.DictReader(path.open())})
    return max(temps), ";".join(flags), len(temps)


def feasibility():
    rows = []
    for run in sorted((RAW / "feasibility").iterdir()):
        r = load(run / "result.json")
        t = r["telemetry_summary"]
        rows.append({"model_label": r["model_label"], "run": run.name, "status": r["status"],
                     "restrictions": "; ".join(r["restrictions"]), "load_seconds": r["load_seconds"],
                     "parallel_slots": r["settings"].get("parallel_slots", "4 (server default)"),
                     "server_vmhwm_kib": t["max_server_hwm_kib"], "server_vmswap_peak_kib": t["max_server_swap_kib"],
                     "pswpout_pages": t["pswpout_delta"], "pswpin_pages": t["pswpin_delta"],
                     "throttled_before": r["before"]["throttled"], "throttled_after": r["after"]["throttled"]})
    write("feasibility.csv", rows)


def speed():
    rows = []
    for model in MODELS:
        base = RAW / "speed" / model
        if not base.exists():
            continue
        resources = dict(line.split("=", 1) for line in (base / "bench/measured.resources.txt").read_text().split())
        max_temp, flags, samples = telemetry_max_temp(base / "telemetry.csv")
        for test in map(json.loads, (base / "bench/measured.jsonl").read_text().splitlines()):
            name = f"pp{test['n_prompt']}" if test["n_prompt"] else f"tg{test['n_gen']}"
            rows.append({"model_label": model, "model_type": test["model_type"],
                         "model_n_params": test["model_n_params"], "model_size_bytes": test["model_size"],
                         "test": name, "repetitions": len(test["samples_ts"]),
                         "mean_tokens_per_s": round(test["avg_ts"], 3), "sd_tokens_per_s": round(test["stddev_ts"], 3),
                         "samples_tokens_per_s": " ".join(f"{s:.3f}" for s in test["samples_ts"]),
                         "benchmark_peak_rss_kib": resources["peak_rss_kib"],
                         "benchmark_elapsed_s": resources["elapsed_seconds"], "sampled_max_temp_c": round(max_temp, 1),
                         "throttle_flags_seen": flags, "telemetry_samples": samples,
                         "build_commit": test["build_commit"], "threads": test["n_threads"],
                         "batch": test["n_batch"], "ubatch": test["n_ubatch"]})
    write("speed.csv", rows)


def answers():
    rows, memory = [], []
    for set_name, (quality_dir, _, _) in SETS.items():
        for model in MODELS:
            path = RAW / quality_dir / model / "result.json"
            if not path.exists():
                continue
            r = load(path)
            for a in r["answers"]:
                rows.append({"set": set_name, "model_label": model, "prompt_id": a["prompt_id"],
                             "category": a["category"], "status": a["status"], "prompt_tokens": a["prompt_tokens"],
                             "completion_tokens": a["completion_tokens"], "wall_seconds": a["wall_seconds"]})
            memory.append({"set": set_name, "model_label": model, "kind": "chat server (default --cache-ram)",
                           "vmhwm_kib": r["telemetry_summary"]["max_server_hwm_kib"],
                           "source": str(path.parent)})
    for model in MODELS:
        speed_res = RAW / "speed" / model / "bench/measured.resources.txt"
        if speed_res.exists():
            peak = dict(line.split("=", 1) for line in speed_res.read_text().split())["peak_rss_kib"]
            memory.append({"set": "speed", "model_label": model, "kind": "llama-bench peak RSS (GNU time)",
                           "vmhwm_kib": peak, "source": str(speed_res.parent)})
    for diag in sorted((RAW / "diagnostic").glob("*")):
        r = load(diag / "result.json")
        memory.append({"set": "diagnostic", "model_label": r["model_label"].split("-diag")[0],
                       "kind": "chat server --cache-ram 0", "vmhwm_kib": r["telemetry_summary"]["max_server_hwm_kib"],
                       "source": str(diag)})
    write("answer_times.csv", rows)
    write("memory.csv", memory)


def looping():
    rows = []
    for set_name, (_, pilot_dir, _) in SETS.items():
        for model in MODELS:
            base = RAW / pilot_dir / model
            path = base / "answers/answers/P02.txt" if (base / "answers").exists() else base / "answers/P02.txt"
            if not path.exists():
                continue
            items = [re.sub(r"^\s*\d+[.)]\s*", "", line).strip().lower()
                     for line in path.read_text().splitlines() if re.match(r"^\s*\d+[.)]", line)]
            rows.append({"set": set_name, "model_label": model, "prompt_id": "P02", "list_items": len(items),
                         "distinct_items": len(set(items)), "source": str(path)})
    write("pilot_p02_repetition.csv", rows)


def quality():
    rows = []
    for set_name, (_, _, scores) in SETS.items():
        scored = [r for r in csv.DictReader(scores.open())] if scores.exists() else []
        for model in MODELS:
            for category in CATEGORIES + ["total"]:
                group = [r for r in scored if r["model_label"] == model and category in (r["category"], "total")]
                if not group:
                    continue
                rows.append({"set": set_name, "model_label": model, "category": category,
                             "attempted": len(group), "completed": sum(r["status"] == "complete" for r in group),
                             "truncated": sum(r["status"] == "truncated" for r in group),
                             "correctness": sum(int(r["correctness_0_2"] or 0) for r in group),
                             "adherence": sum(int(r["adherence_0_2"] or 0) for r in group),
                             "max_points": 2 * len(group)})
    write("quality_by_category.csv", rows)


def manifest():
    files = sorted(p for root in (Path("results/raw"), Path("results/scoring"), Path("results/scoring-vendor"))
                   if root.exists() for p in root.rglob("*") if p.is_file() and not p.name.startswith(".~lock"))
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p}" for p in files]
    Path("results/SHA256SUMS").write_text("\n".join(lines) + "\n")
    print(f"results/SHA256SUMS: {len(lines)} files (verify: sha256sum -c results/SHA256SUMS)")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    feasibility()
    speed()
    answers()
    looping()
    quality()
    manifest()
