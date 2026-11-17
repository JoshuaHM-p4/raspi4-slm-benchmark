#!/usr/bin/env python3
"""Feasibility gate for one model: load in llama-server, one short chat, telemetry; keep every outcome.

Writes <out>/ result.json, request.json, response.json, rendered_prompt.json, props.json,
server.log, telemetry.csv. Refuses to reuse an existing <out>. Status is provisional:
coherence of the answer is a human judgment recorded afterwards in configs/models.csv.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# Not one of the 20 scored prompts in data/prompts.jsonl.
GATE_PROMPT = "In one short sentence, what is a single-board computer?"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def vcgencmd(*args):
    try:
        run = subprocess.run(["vcgencmd", *args], capture_output=True, text=True, timeout=2)
        return run.stdout.strip() if run.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def kv_file(path, sep=":"):
    out = {}
    try:
        for line in Path(path).read_text().splitlines():
            key, _, value = line.partition(sep)
            out[key.strip()] = value.strip()
    except OSError:
        pass
    return out


def kib(value):
    return int(value.split()[0]) if value else None


def board():
    mem = kv_file("/proc/meminfo")
    vm = kv_file("/proc/vmstat", " ")
    return {"time_utc": now(), "temp": vcgencmd("measure_temp"), "throttled": vcgencmd("get_throttled"),
            "arm_clock": vcgencmd("measure_clock", "arm"),
            "mem_available_kib": kib(mem.get("MemAvailable")), "swap_free_kib": kib(mem.get("SwapFree")),
            "swap_total_kib": kib(mem.get("SwapTotal")),
            "pswpin": int(vm.get("pswpin", 0)), "pswpout": int(vm.get("pswpout", 0))}


def proc_mem(pid):
    status = kv_file(f"/proc/{pid}/status")
    return kib(status.get("VmRSS")), kib(status.get("VmHWM")), kib(status.get("VmSwap"))


class Sampler(threading.Thread):
    """1 Hz telemetry; may miss sub-second peaks (VmHWM covers the server's own peak RSS)."""

    fields = ["time_utc", "temp", "throttled", "arm_clock", "mem_available_kib", "swap_free_kib",
              "pswpin", "pswpout", "server_rss_kib", "server_hwm_kib", "server_swap_kib"]

    def __init__(self, path, pid):
        super().__init__(daemon=True)
        self.path, self.pid, self.stop = path, pid, threading.Event()
        self.min_available = self.max_hwm = self.min_swap_free = None
        self.max_server_swap = 0

    def run(self):
        with self.path.open("x", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fields, extrasaction="ignore")
            writer.writeheader()
            while not self.stop.is_set():
                row = board()
                row["server_rss_kib"], row["server_hwm_kib"], row["server_swap_kib"] = proc_mem(self.pid)
                writer.writerow(row)
                handle.flush()
                self.min_available = min(filter(None, [self.min_available, row["mem_available_kib"]]), default=None)
                self.min_swap_free = min(filter(None, [self.min_swap_free, row["swap_free_kib"]]), default=None)
                self.max_hwm = max(filter(None, [self.max_hwm, row["server_hwm_kib"]]), default=None)
                self.max_server_swap = max(self.max_server_swap, row["server_swap_kib"] or 0)
                self.stop.wait(1.0)


def http(url, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        body = error.read()
        try:
            return error.code, json.loads(body)
        except ValueError:
            return error.code, body.decode(errors="replace")


def port_free(port):
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def classify_load_failure(returncode, log_text, timed_out):
    text = log_text.lower()
    if timed_out:
        return "timeout"
    if "unknown model architecture" in text or "unsupported model" in text:
        return "unsupported"
    if returncode == -signal.SIGKILL or "failed to allocate" in text or "cannot allocate memory" in text \
            or "out of memory" in text:
        return "oom"
    return "other_failure"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--server", type=Path, default=Path("vendor/llama.cpp/build/bin/llama-server"))
    parser.add_argument("--ctx", type=int, default=2048)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--load-timeout", type=float, default=900)
    parser.add_argument("--chat-timeout", type=float, default=600)
    args = parser.parse_args()
    if not args.model.is_file() or not args.server.is_file():
        parser.error("model and server binary must exist")
    if subprocess.run(["pgrep", "-x", "llama-server"], capture_output=True).returncode == 0:
        parser.error("another llama-server is running; stop it first (one model resident at a time)")
    if not port_free(args.port):
        parser.error(f"port {args.port} is in use")
    args.out.mkdir(parents=True, exist_ok=False)

    result = {"model_label": args.label, "model_path": str(args.model.resolve()),
              "model_file_bytes": args.model.stat().st_size, "model_sha256": sha256(args.model),
              "settings": {"ctx": args.ctx, "threads": args.threads, "batch": 128, "ubatch": 128, "ngl": 0,
                           "temperature": 0, "max_tokens": args.max_tokens, "enable_thinking": False,
                           "jinja": True, "load_timeout_s": args.load_timeout},
              "before": board()}
    command = [str(args.server.resolve()), "-m", str(args.model.resolve()), "-c", str(args.ctx),
               "-t", str(args.threads), "-b", "128", "-ub", "128", "-ngl", "0", "--jinja",
               "--host", "127.0.0.1", "--port", str(args.port)]
    result["command"] = command

    def write(name, obj):
        with (args.out / name).open("x") as handle:
            handle.write(json.dumps(obj, indent=2) + "\n")

    base = f"http://127.0.0.1:{args.port}"
    log_path = args.out / "server.log"

    with log_path.open("x") as log:
        started = time.monotonic()
        server = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        sampler = Sampler(args.out / "telemetry.csv", server.pid)
        sampler.start()
        try:
            loaded, timed_out = False, False
            while server.poll() is None:
                if time.monotonic() - started > args.load_timeout:
                    timed_out = True
                    break
                try:
                    code, _ = http(f"{base}/health", timeout=2)
                    if code == 200:
                        loaded = True
                        break
                except (urllib.error.URLError, OSError, ValueError):
                    pass
                time.sleep(1)
            result["load_seconds"] = round(time.monotonic() - started, 2)
            result["loaded"] = loaded
            if loaded:
                _, props = http(f"{base}/props")
                write("props.json", props)
                result["chat_template_present"] = bool(isinstance(props, dict) and props.get("chat_template"))
                result["n_ctx"] = (props.get("default_generation_settings") or {}).get("n_ctx") \
                    if isinstance(props, dict) else None
                result["build_info"] = props.get("build_info") if isinstance(props, dict) else None
                messages = [{"role": "user", "content": GATE_PROMPT}]
                kwargs = {"enable_thinking": False}
                code, rendered = http(f"{base}/apply-template",
                                      {"messages": messages, "chat_template_kwargs": kwargs})
                write("rendered_prompt.json", {"http_status": code, "body": rendered})
                request = {"messages": messages, "temperature": 0, "max_tokens": args.max_tokens,
                           "stream": False, "chat_template_kwargs": kwargs}
                write("request.json", request)
                chat_started = time.monotonic()
                chat_timed_out = False
                try:
                    code, response = http(f"{base}/v1/chat/completions", request, timeout=args.chat_timeout)
                except (urllib.error.URLError, OSError) as error:
                    chat_timed_out = isinstance(error, TimeoutError) or isinstance(
                        getattr(error, "reason", None), TimeoutError)
                    code, response = None, {"client_error": repr(error)}
                result["chat_wall_seconds"] = round(time.monotonic() - chat_started, 2)
                write("response.json", {"http_status": code, "body": response})
                choice = (response.get("choices") or [{}])[0] if isinstance(response, dict) else {}
                message = choice.get("message") or {}
                content = message.get("content") or ""
                result.update(chat_http_status=code, finish_reason=choice.get("finish_reason"),
                              answer=content, usage=response.get("usage") if isinstance(response, dict) else None,
                              timings=response.get("timings") if isinstance(response, dict) else None,
                              reasoning_present=bool(message.get("reasoning_content")) or "<think>" in content)
                result["server_vm"] = dict(zip(["rss_kib", "hwm_kib", "swap_kib"], proc_mem(server.pid)))
        finally:
            exited_on_its_own = server.poll() is not None
            if not exited_on_its_own:
                os.killpg(server.pid, signal.SIGTERM)
                try:
                    server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(server.pid, signal.SIGKILL)
                    server.wait()
            sampler.stop.set()
            sampler.join()
    result["server_returncode"] = server.returncode
    result["server_exited_on_its_own"] = exited_on_its_own
    result["after"] = board()
    result["telemetry_summary"] = {"min_mem_available_kib": sampler.min_available,
                                   "max_server_hwm_kib": sampler.max_hwm,
                                   "max_server_swap_kib": sampler.max_server_swap,
                                   "min_swap_free_kib": sampler.min_swap_free,
                                   "pswpin_delta": result["after"]["pswpin"] - result["before"]["pswpin"],
                                   "pswpout_delta": result["after"]["pswpout"] - result["before"]["pswpout"]}

    restrictions = []
    if not result["loaded"]:
        result["status"] = classify_load_failure(server.returncode, log_path.read_text(errors="replace"), timed_out)
    elif result.get("chat_http_status") != 200 or not result.get("answer"):
        if chat_timed_out:
            result["status"] = "timeout"
        elif exited_on_its_own:
            result["status"] = classify_load_failure(server.returncode, log_path.read_text(errors="replace"), False)
        else:
            result["status"] = "other_failure"
    else:
        summary = result["telemetry_summary"]
        if result["finish_reason"] != "stop":
            restrictions.append(f"finish_reason={result['finish_reason']}")
        if result["reasoning_present"]:
            restrictions.append("reasoning output present despite enable_thinking=false")
        if summary["pswpout_delta"] > 0 or summary["max_server_swap_kib"]:
            restrictions.append("swap activity during run")
        if result["n_ctx"] != args.ctx:
            restrictions.append(f"n_ctx={result['n_ctx']}")
        throttled = {result["before"]["throttled"], result["after"]["throttled"]}
        if throttled != {"throttled=0x0"}:
            restrictions.append(f"throttle flags {sorted(throttled)}")
        result["status"] = "ready_with_restrictions" if restrictions else "ready"
    result["restrictions"] = restrictions
    result["status_note"] = "Provisional; answer coherence is judged manually."
    write("result.json", result)
    print(json.dumps({k: result.get(k) for k in ["model_label", "status", "restrictions", "load_seconds",
                                                 "chat_wall_seconds", "finish_reason", "answer", "usage",
                                                 "telemetry_summary", "server_returncode"]}, indent=2))
    return 0 if result["status"].startswith("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
