#!/usr/bin/env python3
"""Best-effort Linux/Pi snapshot; no third-party Python dependencies."""
import argparse
import datetime as dt
import json
import platform
import shutil
import subprocess
from pathlib import Path


def command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return {"command": args, "exit_code": result.returncode,
                "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"command": args, "unavailable": str(error)}


def snapshot():
    paths = ["/etc/os-release", "/proc/meminfo", "/proc/swaps", "/proc/cpuinfo",
             "/sys/firmware/devicetree/base/model",
             "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"]
    files = {}
    for name in paths:
        try:
            files[name] = Path(name).read_text().replace("\x00", "").strip()
        except OSError as error:
            files[name] = {"unavailable": str(error)}
    disk = shutil.disk_usage(".")
    return {"timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "platform": platform.platform(), "machine": platform.machine(),
            "files": files, "disk_bytes": dict(zip(["total", "used", "free"], disk)),
            "commands": [command(args) for args in [
                ["vcgencmd", "measure_temp"], ["vcgencmd", "get_throttled"],
                ["vcgencmd", "measure_clock", "arm"], ["vcgencmd", "version"],
                ["lscpu"], ["lsblk", "-o", "NAME,SIZE,TYPE,MODEL,TRAN,MOUNTPOINTS"],
                ["git", "-C", "vendor/llama.cpp", "rev-parse", "HEAD"],
                ["cmake", "--version"], ["c++", "--version"]]]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/raw/environment.json"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(snapshot(), handle, indent=2)
        handle.write("\n")
    print(args.output)
