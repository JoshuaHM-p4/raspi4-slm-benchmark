#!/usr/bin/env python3
"""Feasibility gate for one model: load in llama-server, one short chat, telemetry; keep every outcome.

Writes <out>/ result.json, request.json, response.json, rendered_prompt.json, props.json,
server.log, telemetry.csv. Refuses to reuse an existing <out>. Status is provisional:
coherence of the answer is a human judgment recorded afterwards in configs/models.csv.
"""
import argparse
import json

from common import LlamaServer, add_server_args, base_result, board, preflight, write_json

# Not one of the 20 scored prompts in data/prompts.jsonl.
GATE_PROMPT = "In one short sentence, what is a single-board computer?"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_server_args(parser)
    args = parser.parse_args()
    preflight(parser, args)
    result = base_result(args)
    chat = None
    with LlamaServer(args) as server:
        result["command"] = server.command
        loaded, timed_out, result["load_seconds"] = server.wait_healthy(args.load_timeout)
        result["loaded"] = loaded
        if loaded:
            props = server.props()
            write_json(args.out, "props.json", props)
            result["chat_template_present"] = bool(props.get("chat_template"))
            result["n_ctx"] = (props.get("default_generation_settings") or {}).get("n_ctx")
            result["build_info"] = props.get("build_info")
            messages = [{"role": "user", "content": GATE_PROMPT}]
            write_json(args.out, "rendered_prompt.json", server.render(messages))
            chat = server.chat(messages, args.max_tokens, args.chat_timeout)
            write_json(args.out, "request.json", chat["request"])
            write_json(args.out, "response.json", {"http_status": chat["http_status"], "body": chat["response"]})
            result.update(chat_wall_seconds=chat["wall_seconds"], chat_http_status=chat["http_status"],
                          finish_reason=chat["finish_reason"], answer=chat["content"], usage=chat["usage"],
                          timings=chat["response"].get("timings") if isinstance(chat["response"], dict) else None,
                          reasoning_present=chat["reasoning_present"])
            result["server_vm"] = server.vm()
    result["server_returncode"] = server.process.returncode
    result["server_exited_on_its_own"] = server.exited_on_its_own
    result["after"] = board()
    result["telemetry_summary"] = summary = server.summary(result["before"], result["after"])

    restrictions = []
    if not loaded:
        result["status"] = server.failure_status(timed_out)
    elif chat["http_status"] != 200 or not chat["content"]:
        if chat["timed_out"]:
            result["status"] = "timeout"
        elif server.exited_on_its_own:
            result["status"] = server.failure_status()
        else:
            result["status"] = "other_failure"
    else:
        if chat["finish_reason"] != "stop":
            restrictions.append(f"finish_reason={chat['finish_reason']}")
        if chat["reasoning_present"]:
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
    write_json(args.out, "result.json", result)
    print(json.dumps({k: result.get(k) for k in ["model_label", "status", "restrictions", "load_seconds",
                                                 "chat_wall_seconds", "finish_reason", "answer", "usage",
                                                 "telemetry_summary", "server_returncode"]}, indent=2))
    return 0 if result["status"].startswith("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
