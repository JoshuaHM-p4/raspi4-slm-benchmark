# A Comparative Evaluation of Quantized Small Language Models on Raspberry Pi 4B

## Abstract

TODO after measurements: objective, device/RAM, exact candidates, method, key measured trade-offs, and limitations. Do not insert expected results as observations.

## 1. Introduction

Motivation: a useful local assistant on affordable hardware. Explain why this personal evaluation focuses on feasibility, speed, resource use, and task quality.

## 2. Method

Link the filled hardware record, manifest, frozen prompt-set checksum, runtime commit, exact commands, and run identifiers. Declare quantization, native templates, reasoning mode, decoding, context/output caps, warm-up, and scoring method. Explain any deviation from the initial plan.

## 3. Feasibility

| Configuration | Loads | Completes pilot | Swap observations | Status / failure evidence |
| --- | --- | --- | --- | --- |
| Qwen3.5-0.8B / unsloth Q4_K_M | Yes, 3.1 s (r2) | Pilot not run; gate chat completed (`stop`, 23 tokens) | None (r1, r2) | Ready. Server VmHWM 687268 KiB with `-np 1` (r2); 751048 KiB with default 4 slots (r1) |
| LFM2.5-1.2B-Instruct / official Q4_K_M | Yes, 2.1 s (r1) | Pilot not run; gate chat completed (`stop`, 31 tokens) | None | Ready. Server VmHWM 779560 KiB |
| Gemma 4 E2B-it / ggml-org Q4_0 | Yes; 80.3 s first load (r1), 8.1 s warm (r2) | Pilot not run; gate chat completed (`stop`, 26 tokens) | r1: 56921 pages swapped out during load only, server VmSwap peak 81368 KiB, ~33 MB swapped back in during generation. r2: no swap-out | Ready with restrictions: VmHWM 2915456 KiB (r2) of 3886836 KiB total; first load from a full page cache swaps to zram. Quantization differs (Q4_0) |

## 4. Performance and resources

| Configuration / run | pp128 token/s mean ± SD | pp512 token/s mean ± SD | tg64 token/s mean ± SD | Benchmark peak RSS KiB | Sampled max temp C | Throttle / swap notes |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen3.5-0.8B Q4_K_M / `speed/qwen35-08b-q4km` | 19.61 ± 0.05 | 19.31 ± 0.01 | 5.24 ± 0.00 | 640292 | 56.5 | `0x0` throughout (214 samples); start 38.9 °C; no swap activity |
| LFM2.5-1.2B-Instruct Q4_K_M / `speed/lfm25-12b-q4km` | 12.29 ± 0.01 | 12.23 ± 0.01 | 5.00 ± 0.00 | 767292 | 57.0 | `0x0` throughout (312 samples); start 43.3 °C; system SwapFree dipped ≤ 16 MB |
| Gemma 4 E2B-it Q4_0 / `speed/gemma4-e2b-q4_0` | 15.45 ± 0.01 | 14.86 ± 0.01 | 2.35 ± 0.00 | 2906572 | 55.0 | `0x0` throughout (384 samples); start 43.8 °C; no swap-out |

llama-bench, 4 threads, batch/microbatch 128, one excluded warm-up then 3 measured repetitions per condition; order Qwen → LFM → Gemma, each session started at ≤ 45 °C. Peak RSS is GNU time `%M` of the measured llama-bench process and includes resident file-backed (mmap) weight pages. The `ondemand` governor sampled 700–1800 MHz across idle gaps and load; no throttle or undervoltage flag was ever set on the 5 V 2 A supply.

**Chat-server memory (quality sessions, 20 requests each).** Server VmHWM: Qwen 1432168 KiB, LFM 803788 KiB, Gemma 2932480 KiB. These include llama-server's default host-RAM prompt cache (`--cache-ram`, default 8192 MiB), which stores each finished request's state even with `cache_prompt: false`; Qwen's grew about 40 MB per request. A labelled diagnostic rerun of Qwen with `--cache-ram 0` peaked at 689340 KiB with no swap and produced 20/20 byte-identical answers (`results/raw/diagnostic/qwen35-08b-q4km-cache-ram-0`). For deployment sizing, use the benchmark RSS or a server with the cache capped, not the default-server VmHWM.

**Client-observed answer time** (non-streaming, warm model, prompt cache off; includes prompt processing and generation; not TTFT), 20 scored prompts per model, against the pre-declared 10 s personal budget:

| Configuration | Median s | Max s | Answers ≤ 10 s | Median generated tokens | Truncated at 128 |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-0.8B Q4_K_M | 6.88 | 26.95 | 17 / 20 | 25 | R04 |
| LFM2.5-1.2B-Instruct Q4_K_M | 6.93 | 29.37 | 17 / 20 | 20 | R04 |
| Gemma 4 E2B-it Q4_0 | 10.96 | 58.55 | 8 / 20 | 20 | R04 |

## 5. Quality

| Configuration | Category | Completed / attempted | Correctness / 8 | Adherence / 8 | Failure or truncation notes |
| --- | --- | --- | --- | --- | --- |
| TBD | Instruction following | Not run | — | — | TBD |
| TBD | Extraction/classification | Not run | — | — | TBD |
| TBD | Reasoning | Not run | — | — | TBD |
| TBD | Summarization | Not run | — | — | TBD |
| TBD | Coding | Not run | — | — | TBD |

Include a few representative saved answers and explain scoring judgments. State whether code was executed or reviewed manually. Clearly label all-attempts versus completed-only scores.

## 6. Discussion and personal recommendation

Which configuration is useful for which task? How much waiting is acceptable to me? Do smaller models sacrifice correctness for speed? Did a candidate fail due to RAM, unsupported runtime, or another cause? Avoid claiming to isolate architecture effects.

## 7. Limitations

One board; small custom prompt set; manual scorer; differing sizes/architectures/tokenizers; selected quantizations and runtime; warm-cache microbenchmarks; sampling/thermal effects; no measured electrical energy unless added.

## 8. Conclusion

TODO after results: concise evidence-based recommendation and one useful next experiment.

## References

See [references](../docs/REFERENCES.md); add exact revisions used.
