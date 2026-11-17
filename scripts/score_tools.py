#!/usr/bin/env python3
"""Blinded scoring workflow for the quality answers (runs on the workstation, never on the Pi).

  sheets   Build results/scoring/: blind_sheet.md (answers grouped by prompt, shuffled, coded),
           blind_scores.csv (fill correctness_0_2 / adherence_0_2 / notes), key.csv (code -> model;
           do not open while scoring). Coding answers are executed against the criteria's test
           cases in a throwaway container (podman, --network none) and the outcome is shown.
  unblind  Validate blind_scores.csv and write data/quality_scores.csv rows.
  summary  Per-model, per-category totals from data/quality_scores.csv (all-attempts view).
"""
import argparse
import csv
import json
import random
import re
import secrets
import subprocess
import sys
from pathlib import Path

RAW = Path("results/raw/quality")
OUT = Path("results/scoring")
PROMPTS = Path("data/prompts.jsonl")
SCORES = Path("data/quality_scores.csv")
IMAGE = "docker.io/library/python:3.13-slim"
CATEGORIES = ["instruction", "extraction", "reasoning", "summarization", "coding"]

# Trusted runner; the untrusted answer and the test expressions arrive as JSON on stdin.
RUNNER = """
import json, sys
p = json.load(sys.stdin)
ns, out = {}, {"exec_error": None, "tests": []}
try:
    exec(p["code"], ns)
except BaseException as e:
    out["exec_error"] = repr(e)
for t in p["tests"]:
    try:
        out["tests"].append({"test": t, "passed": bool(eval(t, ns))})
    except BaseException as e:
        out["tests"].append({"test": t, "passed": False, "error": repr(e)})
print(json.dumps(out))
"""


def load_prompts():
    return {row["id"]: row for row in map(json.loads, PROMPTS.read_text().splitlines()) if row}


def strip_fences(text):
    match = re.search(r"```[a-zA-Z0-9]*\n(.*?)```", text, re.S)
    return (match.group(1), True) if match else (text, False)


def code_tests(criteria):
    return [t.strip() for t in criteria.split(";") if "(" in t and ("==" in t or " is " in t)]


def run_code(answer, criteria):
    code, fenced = strip_fences(answer)
    payload = json.dumps({"code": code, "tests": code_tests(criteria)})
    command = ["podman", "run", "--rm", "-i", "--network", "none", "--read-only", "--memory", "256m",
               "--pids-limit", "64", "--cap-drop", "ALL", IMAGE, "python", "-c", RUNNER]
    try:
        run = subprocess.run(command, input=payload, capture_output=True, text=True, timeout=60)
        result = json.loads(run.stdout) if run.returncode == 0 else {"runner_error": run.stderr.strip()[-300:]}
    except (subprocess.TimeoutExpired, ValueError) as error:
        result = {"runner_error": repr(error)}
    result["fences_stripped"] = fenced
    return result


def sheets(_args):
    OUT.mkdir(parents=True, exist_ok=False)
    prompts = load_prompts()
    items = []
    for answer_file in sorted(RAW.glob("*/answers/*.json")):
        label = answer_file.parent.parent.name
        record = json.loads(answer_file.read_text())
        items.append({"label": label, "prompt_id": record["prompt_id"], "status": record["status"],
                      "content": record["content"],
                      "completion_tokens": (record.get("usage") or {}).get("completion_tokens"),
                      "output_path": str(answer_file.with_suffix(".txt"))})
    if not items:
        sys.exit(f"no answers under {RAW}")
    codes = set()
    for item in items:
        while (code := secrets.token_hex(2).upper()) in codes:
            pass
        codes.add(code)
        item["code"] = code
        if prompts[item["prompt_id"]]["category"] == "coding" and item["content"]:
            item["code_test"] = run_code(item["content"], prompts[item["prompt_id"]]["criteria"])
    shuffle = random.Random(secrets.randbits(64))
    lines = ["# Blind score sheet", "",
             "Score each answer 0-2 for correctness and 0-2 for adherence (docs/EVALUATION.md) in "
             "`blind_scores.csv`. Do not open `key.csv` until every row is scored.", ""]
    rows = []
    for prompt_id, prompt in prompts.items():
        group = [item for item in items if item["prompt_id"] == prompt_id]
        shuffle.shuffle(group)
        lines += [f"## {prompt_id} ({prompt['category']})", "", f"**Prompt:** {prompt['prompt']}", "",
                  f"**Reference:** `{prompt['reference']}`", "", f"**Criteria:** {prompt['criteria']}", ""]
        for item in group:
            lines += [f"### {item['code']}: status {item['status']}, {item['completion_tokens']} tokens", "",
                      "~~~~text", item["content"], "~~~~", ""]
            if "code_test" in item:
                lines += [f"Code test (isolated container): `{json.dumps(item['code_test'])}`", ""]
            rows.append({"code": item["code"], "prompt_id": prompt_id, "category": prompt["category"],
                         "status": item["status"], "correctness_0_2": "", "adherence_0_2": "", "notes": ""})
    with (OUT / "blind_sheet.md").open("x") as handle:
        handle.write("\n".join(lines) + "\n")
    with (OUT / "blind_scores.csv").open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (OUT / "key.csv").open("x", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["code", "model_label", "prompt_id", "output_path", "code_test"])
        for item in items:
            writer.writerow([item["code"], item["label"], item["prompt_id"], item["output_path"],
                             json.dumps(item.get("code_test", ""))])
    print(f"{len(rows)} answers -> {OUT}/blind_sheet.md, blind_scores.csv (key.csv kept separate)")


def unblind(_args):
    key = {row["code"]: row for row in csv.DictReader((OUT / "key.csv").open())}
    blind = list(csv.DictReader((OUT / "blind_scores.csv").open()))
    problems = []
    for row in blind:
        scored = row["status"] in ("complete", "truncated")
        for field in ("correctness_0_2", "adherence_0_2"):
            value = row[field].strip()
            if scored and value not in ("0", "1", "2"):
                problems.append(f"{row['code']} {row['prompt_id']}: {field}={value!r}")
            if not scored and value:
                problems.append(f"{row['code']} {row['prompt_id']}: {row['status']} answers stay unscored")
    if problems:
        sys.exit("fix blind_scores.csv:\n  " + "\n  ".join(problems))
    existing = SCORES.read_text().strip().splitlines()
    if len(existing) > 1:
        sys.exit(f"{SCORES} already has rows; refusing to overwrite")
    fields = existing[0].split(",")
    with SCORES.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        for row in sorted(blind, key=lambda r: (key[r["code"]]["model_label"], r["prompt_id"])):
            label = key[row["code"]]["model_label"]
            writer.writerow({"model_label": label, "run_id": f"quality/{label}", "prompt_id": row["prompt_id"],
                             "category": row["category"], "correctness_0_2": row["correctness_0_2"],
                             "adherence_0_2": row["adherence_0_2"], "status": row["status"],
                             "output_path": key[row["code"]]["output_path"], "notes": row["notes"]})
    print(f"wrote {len(blind)} rows to {SCORES}")


def summary(_args):
    rows = list(csv.DictReader(SCORES.open()))
    print("| Configuration | Category | Completed / attempted (truncated) | Correctness / 8 | Adherence / 8 |")
    print("| --- | --- | --- | --- | --- |")
    for label in sorted({row["model_label"] for row in rows}):
        for category in CATEGORIES:
            group = [row for row in rows if row["model_label"] == label and row["category"] == category]
            done = sum(row["status"] == "complete" for row in group)
            cut = sum(row["status"] == "truncated" for row in group)
            points = lambda f: sum(int(row[f] or 0) for row in group)  # failures count 0 (all-attempts)
            print(f"| {label} | {category} | {done} / {len(group)} ({cut}) | {points('correctness_0_2')} | "
                  f"{points('adherence_0_2')} |")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["sheets", "unblind", "summary"])
    args = parser.parse_args()
    {"sheets": sheets, "unblind": unblind, "summary": summary}[args.command](args)
