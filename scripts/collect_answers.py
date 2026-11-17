#!/usr/bin/env python3
"""Collect one answer per prompt from one model through llama-server's chat API.

Each prompt is a fresh single-turn chat containing only the `prompt` field (never `reference` or
`criteria`), greedy, thinking disabled, prompt cache off. Writes <out>/ result.json, props.json,
server.log, telemetry.csv, and answers/<id>.json + answers/<id>.txt. Refuses to reuse <out>.
Per-answer status: complete (finish_reason stop), truncated (length), timeout, runtime_error.
"""
import argparse
import json
from pathlib import Path

from common import LlamaServer, add_server_args, base_result, board, preflight, sha256, write_json

STATUS = {"stop": "complete", "length": "truncated"}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_server_args(parser)
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--ids", help="comma-separated prompt ids to run (default: all, in file order)")
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.prompts.read_text().splitlines() if line.strip()]
    if args.ids:
        wanted = args.ids.split(",")
        unknown = set(wanted) - {row["id"] for row in rows}
        if unknown:
            parser.error(f"unknown prompt ids: {sorted(unknown)}")
        rows = [row for row in rows if row["id"] in wanted]
    preflight(parser, args)
    answers = args.out / "answers"
    answers.mkdir()

    result = base_result(args)
    result.update(prompts_file=str(args.prompts), prompts_sha256=sha256(args.prompts),
                  prompt_ids=[row["id"] for row in rows], cache_prompt=False,
                  latency_note="wall_seconds: client-observed, non-streaming, includes prompt processing "
                               "and generation; warm model, prompt cache off. Not TTFT.")
    per_prompt = []
    with LlamaServer(args) as server:
        result["command"] = server.command
        loaded, timed_out, result["load_seconds"] = server.wait_healthy(args.load_timeout)
        result["loaded"] = loaded
        if loaded:
            props = server.props()
            write_json(args.out, "props.json", props)
            result["n_ctx"] = (props.get("default_generation_settings") or {}).get("n_ctx")
            result["build_info"] = props.get("build_info")
            for row in rows:
                if server.died():
                    status, chat = "runtime_error", None
                else:
                    messages = [{"role": "user", "content": row["prompt"]}]
                    rendered = server.render(messages)
                    chat = server.chat(messages, args.max_tokens, args.chat_timeout, cache_prompt=False)
                    if chat["timed_out"]:
                        status = "timeout"
                    elif chat["http_status"] != 200:
                        status = "runtime_error"
                    else:
                        status = STATUS.get(chat["finish_reason"], "runtime_error")
                    write_json(answers, f"{row['id']}.json",
                               {"prompt_id": row["id"], "category": row["category"], "status": status,
                                "rendered_prompt": rendered, **chat})
                    with (answers / f"{row['id']}.txt").open("x") as handle:
                        handle.write(chat["content"])
                usage = (chat or {}).get("usage") or {}
                per_prompt.append({"prompt_id": row["id"], "category": row["category"], "status": status,
                                   "completion_tokens": usage.get("completion_tokens"),
                                   "prompt_tokens": usage.get("prompt_tokens"),
                                   "wall_seconds": (chat or {}).get("wall_seconds"),
                                   "reasoning_present": (chat or {}).get("reasoning_present")})
                print(json.dumps({**per_prompt[-1], "answer": (chat or {}).get("content", "")[:100]},
                                 ensure_ascii=False), flush=True)
            result["server_vm_end"] = server.vm()
    result["server_returncode"] = server.process.returncode
    result["server_exited_on_its_own"] = server.exited_on_its_own
    result["after"] = board()
    result["telemetry_summary"] = server.summary(result["before"], result["after"])
    result["status"] = "collected" if loaded else server.failure_status(timed_out)
    result["answers"] = per_prompt
    write_json(args.out, "result.json", result)
    counts = {}
    for item in per_prompt:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print(json.dumps({"model_label": args.label, "status": result["status"], "load_seconds": result["load_seconds"],
                      "answer_status_counts": counts, "telemetry_summary": result["telemetry_summary"],
                      "throttled": [result["before"]["throttled"], result["after"]["throttled"]]}))
    return 0 if loaded else 1


if __name__ == "__main__":
    raise SystemExit(main())
