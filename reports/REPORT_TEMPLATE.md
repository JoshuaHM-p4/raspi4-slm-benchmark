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
| TBD | Not measured | Not measured | Not measured | Not measured | Not measured | TBD |

Peak RSS is for the timed benchmark process. Report chat-server resource measurements separately if collected. Add latency only if its measurement method was implemented and recorded.

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
