# Evaluation protocol

## Keep three kinds of evidence separate

1. Feasibility: does the configuration load, stay within a practical memory budget, and finish?
2. Performance/resources: how fast does the runtime process/generate tokens, and what resources does it use?
3. Task quality: is the answer correct and does it follow the request?

## Metrics

| Metric | Method | Interpretation |
| --- | --- | --- |
| Prompt throughput, token/s | llama-bench pp128 and pp512 | Synthetic input processing; tokenizer dependent |
| Generation throughput, token/s | llama-bench tg64 | Synthetic decode; not a real answer after a fixed user prompt |
| Peak benchmark RSS, KiB | GNU time `%M` | Peak resident memory of the timed benchmark process, not entire board or chat server |
| System MemAvailable, KiB | `/proc/meminfo`, periodic | System headroom; not model-only RAM |
| Temperature, degrees C | Pi thermal sysfs, periodic | Sampled temperature, not guaranteed exact peak |
| Throttling flags | `vcgencmd get_throttled` | Current and historical events; save both baseline and final values |
| CPU clock, Hz | `vcgencmd measure_clock arm` | Sampled clock; missing command means unavailable |
| Completion/failure | Exit status and logs | Preserve load errors, OOM, timeouts, and truncation |
| Task correctness, 0–2 | Reference and manual rubric | Small personal suite, per category |
| Instruction adherence, 0–2 | Prompt constraints | Separate from correctness |
| Complete-response latency, optional | Same client/timing method | Includes prompt processing and generated length; declare load/cache state |
| TTFT, optional | Streaming request to first generated token content | Excludes metadata-only events; requires a real measurement implementation |

GNU time's RSS includes resident file-backed pages but excludes nonresident mappings and other processes. Do not add model file size to RSS as if they were disjoint quantities. The monitor's one-second sampling may miss brief peaks. For chat-server peak memory, collect that server process's own high-water mark (for example Linux VmHWM) or time its full lifetime separately, and label that measurement.

Use `vmstat 1` when diagnosing swap-in/out; record the method and overhead. CPU utilization and temperature cannot establish energy use. An external meter can support an optional separate energy experiment if the measurement boundary is documented.

## Session checklist

1. Record model and runtime identities, environment, settings, and starting temperature/throttle flags.
2. Ensure no other model process remains resident and background load is quiet.
3. Start optional monitoring before the warm-up. Use it consistently.
4. Run the wrapper and retain warm-up and measured logs. Mark any current thermal/power issue.
5. Record final temperature, throttle flags, and swap observations.
6. Run the quality suite with a fresh conversation per prompt and no answer-key leakage.
7. Save full output, generation settings, finish reason if available, and truncation/failure status.
8. Stop the server. Keep results even if unsuccessful.

**Warm versus cold:** the wrapper warms the model and repeats tests in process. It does not measure model loading or cold storage access. OS page cache may survive process restarts. Do not describe a server restart as a guaranteed cold load. A true cold-cache experiment is optional and requires a separately specified method.

## Quality rubric

Read `reference` and `criteria` in the prompt file before scoring, but do not expose them in the model input.

| Score | Correctness | Instruction adherence |
| --- | --- | --- |
| 0 | Wrong core result, unsupported claim central to answer, or unusable code | Ignores the requested task or major output constraint |
| 1 | Partly correct; meaningful omission or error remains | Mostly follows request with one material constraint violation |
| 2 | Meets the reference facts/behavior; equivalent wording or implementation accepted | Meets all explicit constraints |

For coding, actually run the given tiny cases in an isolated disposable environment if you want to award behavior-based correctness. Otherwise mark the evaluation as manual code review and do not call it pass rate. Avoid executing model-produced commands on the Pi that holds your data.

`quality_scores.csv` columns:

- `model_label`, `run_id`, `prompt_id`, `category`: identity.
- `correctness_0_2`, `adherence_0_2`: manual scores, initially blank.
- `status`: complete, truncated, timeout, runtime_error, or unscored.
- `output_path`: relative path to the saved complete answer.
- `notes`: evidence for the score, settings deviations, observed failures.

A completed answer gets its ordinary scores. A truncated answer is scored as received and also flagged. Timeouts/runtime errors get zero in an all-attempts view and remain visible as failures; an additional completed-only score is allowed if its denominator is explicit. Unsupported models get feasibility status N/A for quality, not fabricated per-prompt zeros. Report completed/attempted counts alongside every quality table. There are four prompts per category, so each dimension has a maximum of eight points per category and forty overall.

Do not merge speed repetitions into the quality score. Repeating deterministic quality prompts three times offers little extra information; use additional sampling seeds only as a separate extension.

## Reporting

Use llama-bench's mean and standard deviation for each synthetic condition. Do not invent p95 latency from three measurements. Report exact prompt count, category scores, output limits, thinking mode, quantization, and failure counts. Do not treat a few score points on this tiny suite as a statistically established advantage. If a slower answer is substantially more useful, show that trade-off directly.
