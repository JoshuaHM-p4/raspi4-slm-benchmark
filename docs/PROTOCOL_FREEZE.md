# Protocol freeze

Frozen 18 November 2026, after the Phase 4 pilot and before any scored answer was collected. Changes after this point are deviations: record them here with a date and reason, and never edit the frozen prompt file.

## Frozen inputs

| Item | Value |
| --- | --- |
| Scored prompt set | `data/prompts.jsonl`, 20 prompts, SHA-256 `caec2891b8601aa9a2c839680c3566974ade66ab59acdeb449924d3df7cbb3b6` (verify: `sha256sum -c data/prompts.jsonl.sha256`) |
| Pilot prompts (never scored) | `data/pilot_prompts.jsonl`, SHA-256 `54c9ebfed0734896a0d8ea9adcba679f6844371d14e9922b78b40521e7a62de5` |
| Runtime | llama.cpp `b1b770d90d94cad9e9ea5b993bdbc383a522fb28`, CPU only, build flags in `configs/hardware.md` |
| Artifacts | Exact files, revisions, and checksums in `configs/models.csv` |

## Frozen settings

| Setting | Value |
| --- | --- |
| Server | `-c 2048 -t 4 -b 128 -ub 128 -ngl 0 -np 1 --jinja`, one model resident |
| Request | single-turn fresh chat, `prompt` field only, `temperature 0` (greedy), `max_tokens 128`, `chat_template_kwargs {"enable_thinking": false}`, `cache_prompt false`, non-streaming |
| Speed | `scripts/benchmark.py`: warm-up `-p 128 -n 16 -r 1`, measured `-p 128,512 -n 64 -r 3`, same thread/batch flags |
| Session order | Qwen → LFM → Gemma; each session starts at ≤ 45.0 °C (wait up to 10 min; actual start temperature recorded) |
| Personal acceptable wait | 10 s per complete answer (decision aid for the recommendation; not part of scoring) |

## Pilot findings that shaped the freeze

- The 128-token cap counts generated tokens only: P02 stopped at `completion_tokens = 128` with `finish_reason = length` for all three models, with prompt tokens reported separately.
- Thinking is off for all three: no `reasoning_content`, no `<think>` text; Qwen's template renders an empty think block, Gemma's renders no thinking marker, LFM has no thinking mode.
- Greedy decoding makes Qwen3.5-0.8B loop on long lists (P02: 25 items, 3 distinct). Greedy is kept as the declared baseline for all models; Qwen's model card recommends sampling with `presence_penalty` for non-thinking mode. That configuration is an optional, separately labelled follow-up, not a replacement.
- Client-observed wall time per answer in the pilot: short answers 2.4–4.0 s; 128-token answers 25.5 s (Qwen), 27.5 s (LFM), 57.1 s (Gemma). Single observations, not results.
- Throttle flags `0x0` before and after every pilot step on the 5 V 2 A supply.

## Deviations

- 2026-11-18, not a protocol change: the quality sessions ran with llama-server's default host-RAM prompt cache (`--cache-ram` 8192 MiB), which grew Qwen's server memory by ~40 MB per request (VmHWM 1432168 KiB). A labelled diagnostic rerun with `--cache-ram 0` (`results/raw/diagnostic/qwen35-08b-q4km-cache-ram-0`) gave 20/20 byte-identical answers and VmHWM 689340 KiB. Scored answers are unaffected; chat-server memory is reported with this caveat. `--server-arg` was added to the scripts for labelled diagnostics only.
