# Project plan

A Comparative Evaluation of Quantized Small Language Models on Raspberry Pi 4B: Inference Performance, Resource Usage, and Task Quality

Prepared 18 November 2026. A personal evaluation plan; no hardware measurements have been collected.

Start with Qwen3.5-0.8B and LFM2.5-1.2B-Instruct; pilot Gemma 4 E2B as a conditional third candidate. Exact artifacts, RAM fit, and runtime support must be verified on the actual board. The accompanying repository includes the prompt set, helper scripts, and report template.

## Purpose

Determine which selected quantized small language model offers the most useful balance of response quality, inference speed, and resource use on one Raspberry Pi 4B. Produce a clear personal recommendation supported by saved outputs, rather than a claim about a universally best model.

## Questions

1. Which exact model configurations can load and complete tasks reliably within this Pi's practical memory budget?
2. How do synthetic prompt-processing and generation speeds differ under fixed CPU settings?
3. How do correctness and instruction adherence differ on a small fixed task suite?
4. What temperature, throttling, and memory conditions accompany those results?
5. Which trade-offs matter most for my intended local assistant use?

## First considerations

### Hardware budget comes first

Record the installed RAM, available memory before loading, storage medium, free disk space, OS/kernel, CPU clock/governor, power supply, and cooling. Use stock clocks initially. Since cooling was recently being set up on this Pi, confirm the fan is working and keep its configuration constant for all tests. Check `vcgencmd measure_temp` and `vcgencmd get_throttled` before and after each session.

| Installed RAM | Proposed starting scope, subject to pilot |
| --- | --- |
| 1 GB | Feasibility only; do not promise a three-model comparison |
| 2 GB | Pilot one approximately 1B quantized model with short context; Gemma is conditional |
| 4 GB | Start Qwen 0.8B and LFM 1.2B; evaluate Gemma E2B memory fit explicitly |
| 8 GB | More headroom for Gemma E2B and optional Qwen 2B, still subject to measurement |

These are planning suggestions, not verified fit guarantees. The operating system, model weights, model-specific state/cache, and compute buffers all need RAM. A GGUF fitting on disk does not guarantee that inference fits in RAM. Memory mapping does not make out-of-core inference free: page faults and storage bandwidth may dominate.

Record swap configuration and swap-in/out counters. A result relying on sustained swapping belongs in a separate feasibility/stress section. Do not present it as an ordinary RAM-resident run. Avoid changing OS swap settings just to make the first benchmark pass.

### Models and runtime

Use instruction-tuned or chat-capable checkpoints. Freeze the exact artifacts and record their SHA-256 checksums and source revisions. Prefer similarly quantized GGUF artifacts, but do not force identical labels if unsupported. Quantization labels do not guarantee equal numeric error or memory use across architectures.

Use llama.cpp as the initial shared runtime. A successful build is not proof that every candidate architecture is supported by that commit. Test model loading, chat-template handling, context allocation, and a short answer first. Record unsupported architecture, failed conversion, out-of-memory, timeout, or malformed output as distinct outcomes.

Google's LiteRT-LM is a possible separate Gemma experiment. If it is used, describe the comparison as model-plus-runtime deployment configurations; do not attribute a runtime change's effect to model weights alone. MLX targets Apple Silicon, so its artifacts are not the chosen path for this ARM Linux Pi project.

### What to control

Keep one board, OS image, runtime commit, build flags, thread count, batch settings, cooling, storage, and idle workload policy constant. Keep Wi-Fi/downloads and unrelated background CPU work quiet during measurement. Run offline after setup if practical. Use one request at a time.

For quality, use identical user text, fresh chats, the correct model-specific template, a shared context/output budget, and a declared decoding policy. Equal user text will tokenize differently between models. Record output lengths and avoid treating token/s as a tokenizer-independent unit of useful work. Short correct answers can be more useful than long fast answers.

## Feasibility gate

- [ ] Record actual hardware and environment.
- [ ] Confirm a 64-bit userspace and compatible runtime build.
- [ ] Identify exact model artifact, quantization, revision, license, and checksum.
- [ ] Load the model with 2,048-token context and no other model resident.
- [ ] Generate a coherent short response with the expected chat template.
- [ ] Verify reasoning mode and output limit, including what tokens the limit counts.
- [ ] Observe RAM, swap activity, temperature, clock, and throttling.
- [ ] Mark status as ready, ready with restrictions, unsupported, OOM, timeout, or other failure.

If a model fails, preserve the error and settings. A smaller context or different quantization is an additional labelled configuration. It is not a replacement for the original failure record. If a common baseline context must change for feasibility, repeat all comparable baseline runs with the revised value and document the change.

## Small, achievable experiment

**Pilot:** Try two non-scored prompts and one short microbenchmark per model. Adjust the protocol before scoring starts. Do not tune prompts after seeing final answers.

**Performance:** For each ready configuration, use one warm-up and three measured repetitions of the initial llama-bench conditions. Report mean and standard deviation from llama-bench; keep raw output. The wrapper's GNU time RSS covers its measured benchmark invocation, not the separate chat server.

**Quality:** Use 20 prompts: four instruction-following, four extraction/classification, four reasoning, four summarization, and four small coding tasks. Score one answer per prompt. Small coding tasks are included as a personal workload, not because all candidates are designed for coding. Leave model identifiers out of answer sheets while scoring where practical.

**Optional latency:** Add client-observed request completion time only with a consistent method. Add time to first token only after implementing streaming timestamps. Do not substitute synthetic prefill time, first network byte, or UI page-rendering time for measured TTFT.

**Recommendation:** Inspect feasibility, per-category quality, generation speed, prompt-processing speed, memory, and thermals together. Define a personal acceptable wait time after the pilot and before final comparison. Avoid an arbitrary weighted overall score; explain the use case behind the selection.

## Run order and time budget

Use a balanced model order across speed rounds if expanding beyond the three internal repetitions: A-B-C, B-C-A, C-A-B. For the minimal wrapper, keep the per-model invocation and cool/idle back to a comparable starting temperature before switching. This does not fully eliminate order effects; state that limit. Keep any throttled run and label it; troubleshoot cooling or power, then rerun as a separately identified session.

Begin with the two smaller candidates. Add Gemma only after its feasibility gate passes. A 20-minute pilot is an investigation target, not a guaranteed completion time. The scripts use a generous timeout because Pi speed is unknown. Start with one model and inspect time spent before scheduling the rest.

## Deliverables

- Filled hardware record and model manifest.
- Unmodified raw benchmark logs and model answers.
- Per-model benchmark table and per-category quality table.
- Feasibility/failure log and a short methods/limitations section.
- A concise report with a personal deployment recommendation.

## Non-goals

No training, fine-tuning, large public benchmark suite, statistical population claims, production serving, or broad safety evaluation. This study can compare selected deployments on this one Pi; it cannot isolate causal architecture effects or generalize to all SBCs.

## Evaluation protocol

### Keep three kinds of evidence separate

1. Feasibility: does the configuration load, stay within a practical memory budget, and finish?
2. Performance/resources: how fast does the runtime process/generate tokens, and what resources does it use?
3. Task quality: is the answer correct and does it follow the request?

### Metrics

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

### Session checklist

1. Record model and runtime identities, environment, settings, and starting temperature/throttle flags.
2. Ensure no other model process remains resident and background load is quiet.
3. Start optional monitoring before the warm-up. Use it consistently.
4. Run the wrapper and retain warm-up and measured logs. Mark any current thermal/power issue.
5. Record final temperature, throttle flags, and swap observations.
6. Run the quality suite with a fresh conversation per prompt and no answer-key leakage.
7. Save full output, generation settings, finish reason if available, and truncation/failure status.
8. Stop the server. Keep results even if unsuccessful.

**Warm versus cold:** the wrapper warms the model and repeats tests in process. It does not measure model loading or cold storage access. OS page cache may survive process restarts. Do not describe a server restart as a guaranteed cold load. A true cold-cache experiment is optional and requires a separately specified method.

### Quality rubric

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

### Reporting

Use llama-bench's mean and standard deviation for each synthetic condition. Do not invent p95 latency from three measurements. Report exact prompt count, category scores, output limits, thinking mode, quantization, and failure counts. Do not treat a few score points on this tiny suite as a statistically established advantage. If a slower answer is substantially more useful, show that trade-off directly.

## Academic title options

1. **A Comparative Evaluation of Quantized Small Language Models on Raspberry Pi 4B: Inference Performance, Resource Usage, and Task Quality** — recommended; describes the actual scope without promising a comprehensive benchmark.
2. **Evaluating Gemma 4, Qwen3.5, and LFM2.5 for Local Text Inference on Raspberry Pi 4B** — model-specific; finalize only when exact candidates are confirmed.
3. **Performance–Quality Trade-offs of Small Language Models on a Resource-Constrained Single-Board Computer** — suitable for a broader research-style report; specify Pi 4B in the abstract.
4. **An Exploratory Benchmark of Quantized Language Models on Raspberry Pi 4B** — best if the final suite stays small and descriptive.
5. **Feasibility and Practical Utility of On-Device Language Model Inference on Raspberry Pi 4B** — best if model fit, swapping, and usability become the central findings.

Suggested repository name: `pi-slm-bench`.

Suggested short description: A reproducible personal comparison of quantized language-model deployments on Raspberry Pi 4B, measuring inference speed, resource usage, and task quality.

## References

Checked 17 November 2026. Upstream documentation is mutable; record artifact revisions and the runtime SHA used in the actual experiment. Published benchmark figures on other devices are not results for this project.

1. Google. [Gemma 4 model overview](https://ai.google.dev/gemma/docs/core). Model variants, effective parameters, and memory-planning considerations. GPU/TPU estimates in the source are not measured Pi RAM guarantees.
2. Qwen. [Qwen3.5-0.8B official model card](https://huggingface.co/Qwen/Qwen3.5-0.8B). Candidate family variants, native serving/template guidance, sampling recommendations, and thinking-mode caveats.
3. Liquid AI. [LFM2.5-1.2B-Instruct official model card](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct) and [official GGUF files](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF/tree/main). Exact variant and quantized artifact choices.
4. ggml-org. [llama.cpp build documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md). Platform-dependent setup and compilation.
5. ggml-org. [llama-bench documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md). Synthetic prefill/generation tests, repetitions, and output formats.
6. ggml-org. [llama-server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md). Chat serving, native templates, and request configuration.
7. Raspberry Pi. [Computer hardware documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) and [Raspberry Pi OS](https://www.raspberrypi.com/documentation/computers/os.html). Hardware/platform checks and operating environment.
8. Google. [Gemma 4 with LiteRT-LM](https://developers.google.com/edge/litert-lm/models/gemma-4). Optional alternative-runtime background; its Pi 5 measurements must not be reused as Pi 4 results.

Check and record each selected artifact's own license and redistribution requirements. No model weights are redistributed in this starter.
