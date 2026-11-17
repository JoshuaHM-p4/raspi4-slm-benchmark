#!/usr/bin/env python3
"""Sample board telemetry until Ctrl+C; blank cells mean unavailable."""
import argparse
import csv
import datetime as dt
import subprocess
import time
from pathlib import Path


def vcgencmd(*args):
    try:
        run = subprocess.run(["vcgencmd", *args], capture_output=True, text=True, timeout=2)
        return run.stdout.strip() if run.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def sample():
    row = {"timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
           "temperature_c": "", "mem_available_kib": "", "swap_free_kib": "",
           "throttle_flags_raw": vcgencmd("get_throttled"),
           "arm_clock_raw": vcgencmd("measure_clock", "arm")}
    try:
        row["temperature_c"] = float(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    except (OSError, ValueError):
        pass
    try:
        info = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        row["mem_available_kib"] = info.get("MemAvailable", "").strip().split()[0]
        row["swap_free_kib"] = info.get("SwapFree", "").strip().split()[0]
    except (OSError, ValueError, IndexError):
        pass
    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(sample()))
        writer.writeheader()
        try:
            while True:
                writer.writerow(sample())
                handle.flush()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            pass
    print(args.output)
