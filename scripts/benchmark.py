#!/usr/bin/env python3
"""Run a warm-up and timed llama-bench; preserve all outputs, including failures."""
import argparse
import datetime as dt
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def execute(command, directory, prefix, timeout):
    started = time.monotonic()
    result = {"command": command, "started_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    with (directory / f"{prefix}.jsonl").open("w") as stdout, (directory / f"{prefix}.stderr.log").open("w") as stderr:
        try:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        except OSError as error:
            result.update(status="launch_error", error=str(error))
        else:
            try:
                code = process.wait(timeout=timeout)
                result.update(status="ok" if code == 0 else "failed", exit_code=code)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                result.update(status="timeout" if isinstance(error, subprocess.TimeoutExpired) else "interrupted",
                              exit_code=process.returncode)
    result["elapsed_wall_seconds"] = time.monotonic() - started
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--binary", type=Path, default=Path("vendor/llama.cpp/build/bin/llama-bench"))
    parser.add_argument("--time-binary", type=Path, default=Path("/usr/bin/time"))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args()
    if args.threads <= 0 or args.timeout <= 0:
        parser.error("threads and timeout must be positive")
    if not args.model.is_file() or not args.binary.is_file():
        parser.error("model and benchmark binary must exist")
    if not args.time_binary.is_file():
        parser.error("GNU time is required; install it or specify --time-binary")
    args.out.mkdir(parents=True, exist_ok=False)
    common = [str(args.binary.resolve()), "-m", str(args.model.resolve()),
              "-t", str(args.threads), "-ngl", "0", "-b", "128", "-ub", "128", "-o", "jsonl"]
    metadata = {"model_label": args.label, "model_path": str(args.model.resolve()),
                "model_file_bytes": args.model.stat().st_size, "model_sha256": sha256(args.model),
                "timeout_seconds_per_invocation": args.timeout,
                "note": "Synthetic pp/tg; warm-up excluded; no application TTFT measurement."}
    metadata_path = args.out / "metadata.json"

    def save():
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")

    save()
    metadata["warmup"] = execute(common + ["-p", "128", "-n", "16", "-r", "1"], args.out, "warmup", args.timeout)
    save()
    if metadata["warmup"]["status"] != "ok":
        print(f"Warm-up failed; inspect {args.out}", file=sys.stderr)
        return 1
    measured = common + ["-p", "128,512", "-n", "64", "-r", "3"]
    timed = [str(args.time_binary.resolve()), "-f", "peak_rss_kib=%M\nelapsed_seconds=%e\nexit_code=%x",
             "-o", str((args.out / "measured.resources.txt").resolve()), *measured]
    metadata["measured"] = execute(timed, args.out, "measured", args.timeout)
    save()
    print(f"{metadata['measured']['status']}: {args.out}")
    return 0 if metadata["measured"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
