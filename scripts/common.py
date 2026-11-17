"""Shared llama-server lifecycle, chat request, and board telemetry for the gate and collection scripts.

Standard library only. Every file is written with exclusive create so nothing is overwritten.
"""
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

# Frozen baseline (README "Minimal experiment"); recorded verbatim in every result.json.
BATCH = UBATCH = 128
PARALLEL_SLOTS = 1
THINKING = {"enable_thinking": False}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(directory, name, obj):
    with (Path(directory) / name).open("x") as handle:
        handle.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


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


def classify_failure(returncode, log_text, timed_out):
    text = log_text.lower()
    if timed_out:
        return "timeout"
    if "unknown model architecture" in text or "unsupported model" in text:
        return "unsupported"
    if returncode == -signal.SIGKILL or "failed to allocate" in text or "cannot allocate memory" in text \
            or "out of memory" in text:
        return "oom"
    return "other_failure"


def add_server_args(parser):
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


def preflight(parser, args):
    """Validate inputs, enforce one resident model, then create the (new) output directory."""
    if not args.model.is_file() or not args.server.is_file():
        parser.error("model and server binary must exist")
    if subprocess.run(["pgrep", "-x", "llama-server"], capture_output=True).returncode == 0:
        parser.error("another llama-server is running; stop it first (one model resident at a time)")
    if not port_free(args.port):
        parser.error(f"port {args.port} is in use")
    args.out.mkdir(parents=True, exist_ok=False)


def base_result(args):
    return {"model_label": args.label, "model_path": str(args.model.resolve()),
            "model_file_bytes": args.model.stat().st_size, "model_sha256": sha256(args.model),
            "settings": {"ctx": args.ctx, "threads": args.threads, "batch": BATCH, "ubatch": UBATCH, "ngl": 0,
                         "parallel_slots": PARALLEL_SLOTS, "temperature": 0, "max_tokens": args.max_tokens,
                         **THINKING, "jinja": True, "load_timeout_s": args.load_timeout},
            "before": board()}


class LlamaServer:
    """One llama-server process with a 1 Hz sampler. Use as a context manager."""

    def __init__(self, args):
        self.out, self.port = args.out, args.port
        self.base = f"http://127.0.0.1:{args.port}"
        self.log_path = args.out / "server.log"
        self.command = [str(args.server.resolve()), "-m", str(args.model.resolve()), "-c", str(args.ctx),
                        "-t", str(args.threads), "-b", str(BATCH), "-ub", str(UBATCH), "-ngl", "0",
                        "-np", str(PARALLEL_SLOTS), "--jinja", "--host", "127.0.0.1", "--port", str(args.port)]
        self.exited_on_its_own = False

    def __enter__(self):
        self._log = self.log_path.open("x")
        self.started = time.monotonic()
        self.process = subprocess.Popen(self.command, stdout=self._log, stderr=subprocess.STDOUT,
                                        start_new_session=True)
        self.sampler = Sampler(self.out / "telemetry.csv", self.process.pid)
        self.sampler.start()
        return self

    def wait_healthy(self, timeout):
        """Returns (loaded, timed_out, seconds)."""
        while self.process.poll() is None:
            if time.monotonic() - self.started > timeout:
                return False, True, round(time.monotonic() - self.started, 2)
            try:
                code, _ = http(f"{self.base}/health", timeout=2)
                if code == 200:
                    return True, False, round(time.monotonic() - self.started, 2)
            except (urllib.error.URLError, OSError, ValueError):
                pass
            time.sleep(1)
        return False, False, round(time.monotonic() - self.started, 2)

    def props(self):
        _, props = http(f"{self.base}/props")
        return props if isinstance(props, dict) else {"raw": props}

    def render(self, messages):
        code, body = http(f"{self.base}/apply-template", {"messages": messages, "chat_template_kwargs": THINKING})
        return {"http_status": code, "body": body}

    def chat(self, messages, max_tokens, timeout, **extra):
        """Non-streaming chat; client-observed wall time covers prompt processing and generation."""
        request = {"messages": messages, "temperature": 0, "max_tokens": max_tokens, "stream": False,
                   "chat_template_kwargs": THINKING, **extra}
        started = time.monotonic()
        timed_out = False
        try:
            code, response = http(f"{self.base}/v1/chat/completions", request, timeout=timeout)
        except (urllib.error.URLError, OSError) as error:
            timed_out = isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError)
            code, response = None, {"client_error": repr(error)}
        wall = round(time.monotonic() - started, 2)
        choice = (response.get("choices") or [{}])[0] if isinstance(response, dict) else {}
        message = choice.get("message") or {}
        content = message.get("content") or ""
        return {"request": request, "http_status": code, "response": response, "wall_seconds": wall,
                "timed_out": timed_out, "finish_reason": choice.get("finish_reason"), "content": content,
                "usage": response.get("usage") if isinstance(response, dict) else None,
                "reasoning_present": bool(message.get("reasoning_content")) or "<think>" in content}

    def vm(self):
        return dict(zip(["rss_kib", "hwm_kib", "swap_kib"], proc_mem(self.process.pid)))

    def died(self):
        return self.process.poll() is not None

    def __exit__(self, *exc):
        self.exited_on_its_own = self.process.poll() is not None
        if not self.exited_on_its_own:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
        self.sampler.stop.set()
        self.sampler.join()
        self._log.close()
        return False

    def failure_status(self, timed_out=False):
        return classify_failure(self.process.returncode, self.log_path.read_text(errors="replace"), timed_out)

    def summary(self, before, after):
        s = self.sampler
        return {"min_mem_available_kib": s.min_available, "max_server_hwm_kib": s.max_hwm,
                "max_server_swap_kib": s.max_server_swap, "min_swap_free_kib": s.min_swap_free,
                "pswpin_delta": after["pswpin"] - before["pswpin"],
                "pswpout_delta": after["pswpout"] - before["pswpout"]}
