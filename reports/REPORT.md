# A Comparative Evaluation of Quantized Small Language Models on Raspberry Pi 4B

## Abstract

Three quantized small language models were deployed with one pinned llama.cpp build (CPU only) on one Raspberry Pi 4 Model B (4 GB RAM, 64-bit Debian 13, stock clocks, heatsink and 5 V fan, 5 V 2 A supply): Qwen3.5-0.8B (Q4_K_M), LFM2.5-1.2B-Instruct (Q4_K_M), and Gemma 4 E2B-it (Q4_0). All three loaded at a 2,048-token context; Gemma used about 2.9 GB of the board's 3.8 GB and swapped to zram on its first load. Synthetic generation ran at 5.24 ± 0.00 (Qwen), 5.00 ± 0.00 (LFM), and 2.35 ± 0.00 (Gemma) tokens/s; prompt processing at pp512 ran at 19.31, 12.23, and 14.86 tokens/s. On a 20-prompt personal suite scored 0–2 for correctness and adherence, Gemma scored 37/40 and 39/40, LFM 34/40 and 34/40, and Qwen 32/40 and 31/40, while only Qwen and LFM answered most prompts within the pre-declared 10 s wait (17/20 each, against 8/20 for Gemma). With each vendor's recommended sampling, LFM and Gemma kept their correctness (34 and 37) while Qwen fell to 25/40. No throttling or undervoltage was observed. Results describe these deployments on this board with a small, single-scorer suite; they do not rank models in general.

## 1. Introduction

The goal is a useful local text assistant on hardware already owned: a Raspberry Pi 4B that also serves other projects. The questions are practical: which candidate fits in memory, how long an answer takes, and whether the answers are right and follow instructions. Feasibility, speed and resources, and task quality are kept as separate evidence, and the recommendation weighs them for one stated use case rather than through a combined score.

## 2. Method

- **Hardware and software:** [configs/hardware.md](../configs/hardware.md); environment snapshot `results/raw/environment-20261118.json`.
- **Runtime:** llama.cpp `b1b770d90d94cad9e9ea5b993bdbc383a522fb28` (tag v1.0.0), CPU backend only (`-mcpu=cortex-a72`, no dot-product), web UI disabled; build logs in `results/raw/build/`.
- **Artifacts:** exact repositories, revisions, SHA-256 checksums, licenses, and template/thinking handling in [configs/models.csv](../configs/models.csv). Qwen is a third-party (unsloth) GGUF; Gemma is Q4_0, not Q4_K_M like the other two.
- **Frozen protocol:** [docs/PROTOCOL_FREEZE.md](../docs/PROTOCOL_FREEZE.md), frozen after a two-prompt pilot and before any scored answer. Prompt set `data/prompts.jsonl`, SHA-256 `caec2891…cbb3b6`.
- **Speed:** llama-bench via `scripts/benchmark.py`, 4 threads, batch/microbatch 128, excluded warm-up, then pp128, pp512, and tg64 with 3 repetitions each; `scripts/monitor.py` at 1 Hz; sessions run Qwen → LFM → Gemma, each starting at ≤ 45 °C.
- **Answers:** `scripts/collect_answers.py` through llama-server (`-c 2048 -np 1 --jinja`, one model resident): one fresh single-turn chat per prompt containing only the prompt text, greedy decoding (temperature 0), at most 128 generated tokens, thinking disabled with `chat_template_kwargs` (verified in every saved rendered prompt), prompt cache off. Every request, rendered prompt, response, finish reason, token count, and wall time is in `results/raw/quality/<label>/`.
- **Scoring:** one scorer (the author) on a blinded sheet (`scripts/score_tools.py`): answers grouped by prompt, shuffled behind random codes. Each answer gets two scores from the rubric below (also in [docs/EVALUATION.md](../docs/EVALUATION.md)); a truncated answer is scored as received. Coding answers were executed against the prompts' test cases in a network-less throwaway container on a separate workstation; correctness for coding follows the executed tests, adherence is manual review.

  | Score | Correctness | Instruction adherence |
  | --- | --- | --- |
  | 0 | Wrong core result, an unsupported claim central to the answer, or unusable code | Ignores the requested task or a major output constraint |
  | 1 | Partly correct; a meaningful omission or error remains | Mostly follows the request, with one material constraint violation |
  | 2 | Meets the reference facts or behaviour; equivalent wording or implementation accepted | Meets all explicit constraints |
- **Deviations from the starter plan:** `-np 1` added after the feasibility gate (single request slot, matching the plan's one-request policy); web UI disabled at build time; answers collected through the API instead of the manual web UI; chat-server memory reported with the prompt-cache caveat in section 4.

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
| Qwen3.5-0.8B Q4_K_M | 6.75 | 26.95 | 17 / 20 | 24 | R04 |
| LFM2.5-1.2B-Instruct Q4_K_M | 6.72 | 29.37 | 17 / 20 | 19 | R04 |
| Gemma 4 E2B-it Q4_0 | 10.92 | 58.55 | 8 / 20 | 19.5 | R04 |

Medians are over 20 values (mean of the 10th and 11th), computed from `results/processed/answer_times.csv`.

## 5. Quality

All-attempts view: every model completed 19 of 20 prompts and was truncated at 128 tokens on R04; no timeouts or runtime errors, so the completed-only view differs only by R04 (scored as received and flagged).

| Configuration | Category | Completed / attempted (truncated) | Correctness / 8 | Adherence / 8 | Failure or truncation notes |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-0.8B Q4_K_M | Instruction following | 4 / 4 (0) | 8 | 8 | — |
| Qwen3.5-0.8B Q4_K_M | Extraction/classification | 4 / 4 (0) | 6 | 7 | E02: "positive" for a neutral sentence |
| Qwen3.5-0.8B Q4_K_M | Reasoning | 3 / 4 (1) | 5 | 5 | R02 answered "yes" from world knowledge rather than the premises; R04 truncated without a conclusion |
| Qwen3.5-0.8B Q4_K_M | Summarization | 4 / 4 (0) | 5 | 4 | S01 omitted the electrical-repair reason; S02 three bullets for "exactly two"; S04 22 words for "at most 20"; S03 invented a cause |
| Qwen3.5-0.8B Q4_K_M | Coding | 4 / 4 (0) | 8 | 7 | All tests pass; C04 added an explanation |
| LFM2.5-1.2B-Instruct Q4_K_M | Instruction following | 4 / 4 (0) | 8 | 8 | — |
| LFM2.5-1.2B-Instruct Q4_K_M | Extraction/classification | 4 / 4 (0) | 8 | 8 | — |
| LFM2.5-1.2B-Instruct Q4_K_M | Reasoning | 3 / 4 (1) | 4 | 5 | R01 "9 pens" (correct: 14); R02 answered "yes" without deriving it from the premises; R04 truncated |
| LFM2.5-1.2B-Instruct Q4_K_M | Summarization | 4 / 4 (0) | 6 | 7 | S01 omitted the Monday resumption; S02 overlong bullets |
| LFM2.5-1.2B-Instruct Q4_K_M | Coding | 4 / 4 (0) | 8 | 6 | All tests pass; C03 and C04 wrapped in Markdown fences |
| Gemma 4 E2B-it Q4_0 | Instruction following | 4 / 4 (0) | 8 | 8 | — |
| Gemma 4 E2B-it Q4_0 | Extraction/classification | 4 / 4 (0) | 8 | 8 | — |
| Gemma 4 E2B-it Q4_0 | Reasoning | 3 / 4 (1) | 7 | 7 | R04 listed the five times but was truncated before stating the count |
| Gemma 4 E2B-it Q4_0 | Summarization | 4 / 4 (0) | 6 | 8 | S01 omitted the electrical-repair reason; S02 omitted Fan B |
| Gemma 4 E2B-it Q4_0 | Coding | 4 / 4 (0) | 8 | 8 | All tests pass |

Totals out of 40 (correctness / adherence): Gemma 37 / 39, LFM 34 / 34, Qwen 32 / 31.

Representative answers (full text in `results/raw/quality/<label>/answers/`):

- **R01** (12 pens, remove 3, add 5): Qwen "12 minus 3 equals 9, and 9 plus 5 equals 14. So, 14 pens remain." (2/2); Gemma "14 pens remain. Three were removed and five were added to the original 12." (2/2); LFM "There are 9 pens remaining. The addition of five pens increases the total." (0/1: wrong result, explanation contradicts it).
- **E02** ("The package arrived on Tuesday."): LFM and Gemma "neutral"; Qwen "positive" (0/1: correct format, wrong label).
- **S04** (at most 20 words): Gemma and LFM stayed within the limit; Qwen kept the facts in 22 words (2/0: correct content, constraint violated).
- **R04** (count samples from 0 to 20 s inclusive): all three began a step-by-step explanation and reached the 128-token cap before stating the count, so this item mostly measures verbosity under the cap.

## 5a. Follow-up: vendor-recommended sampling

The pilot and the 20 frozen prompts were rerun with each vendor's recommended non-thinking sampling (`configs/vendor_sampling.json`; unset parameters neutral), seed 42, one answer per prompt, everything else unchanged. Raw files: `results/raw/pilot-vendor/`, `results/raw/quality-vendor/`.

| Configuration | Sampling | P02 distinct / listed (greedy → vendor) | Answers identical to greedy | Code tests passed (greedy → vendor) | Median answer s | Answers ≤ 10 s |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen3.5-0.8B | T 1.0, top-k 20, presence 2.0 | 3/25 → 23/23 | 9 / 20 | 9/9 → 6/9 | 7.08 | 18 / 20 |
| LFM2.5-1.2B | T 0.1, top-k 50, repeat 1.05 | 22/26 → 22/25 | 11 / 20 | 9/9 → 9/9 | 7.06 | 18 / 20 |
| Gemma 4 E2B | T 1.0, top-p 0.95, top-k 64 | 24/24 → 26/26 | 10 / 20 | 9/9 → 9/9 | 10.88 | 9 / 20 |

Qwen's presence penalty removes the greedy looping, but the same settings cost three of nine executed code tests. Answer times, memory, and thermals were essentially unchanged; throttle flags stayed `0x0`.

Blind quality scores for this set (`data/quality_scores_vendor.csv`, scored on `results/scoring-vendor/` with its own key):

| Configuration | Instruction | Extraction | Reasoning | Summarization | Coding | Total / 40 |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen3.5-0.8B, vendor | 6 / 7 | 6 / 8 | 3 / 6 | 6 / 6 | 4 / 8 | **25 / 35** |
| LFM2.5-1.2B, vendor | 8 / 8 | 8 / 8 | 5 / 7 | 5 / 8 | 8 / 6 | **34 / 37** |
| Gemma 4 E2B, vendor | 8 / 8 | 8 / 7 | 6 / 7 | 7 / 8 | 8 / 7 | **37 / 37** |

Cells are correctness / adherence, each out of 8. Under its recommended sampling Qwen lost correctness in instruction following (I04 swapped input and output devices), reasoning (R01 "ten" pens, R02 "no"), and coding (C02 and C03 raise errors on non-empty input), so the looping fix comes at a clear accuracy cost on this suite. LFM's and Gemma's correctness totals match their greedy runs (34 and 37); their adherence moved by a few points in both directions.

## 6. Discussion and personal recommendation

**Use case and constraint.** A local assistant for short instructions, extraction, small summaries, and small code snippets, where I want an answer within 10 s (declared after the pilot, before scoring).

**What the evidence shows.**

- **Gemma 4 E2B** gave the most correct and best-formatted answers (37/40, 39/40; its correctness losses were R04 truncation and two omitted summary details). It costs speed and memory: 2.35 tokens/s generation, a median answer of 10.92 s with only 8/20 answers inside 10 s and up to 58.6 s, and about 2.9 GB resident, which leaves under 1 GB for everything else on a 4 GB board and swapped on a cold first load.
- **Qwen3.5-0.8B and LFM2.5-1.2B** are equally fast for answers on this suite (median 6.75 vs 6.72 s, 17/20 within 10 s each) and fit in under 0.8 GB. Under greedy decoding their totals differ by two correctness and three adherence points (Qwen 32 / 31, LFM 34 / 34), which this suite cannot distinguish. They fail differently: LFM makes reasoning errors (R01 wrong arithmetic) and wraps code in fences; Qwen misses explicit format limits (bullet count, word count) and, in the pilot, looped under greedy decoding on a long list. Under vendor-recommended sampling LFM held 34/40 correctness while Qwen fell to 25/40. Qwen processes prompts about 1.6× faster (19.3 vs 12.2 tokens/s at pp512) and uses the least memory, which matters for longer inputs than this suite contains.
- **Smaller is faster here, but not proportionally more accurate.** Gemma is the slowest generator and the most accurate; the two faster models trade accuracy in reasoning and constraint-following, not in simple instructions or extraction, where all three were near ceiling.
- **No candidate failed** on RAM, runtime support, or thermals; Gemma's restriction is memory headroom, not a failure.

**Recommendation (for this board and use case).** Run **LFM2.5-1.2B-Instruct (Q4_K_M)** as the default interactive assistant: it meets the 10 s budget for most short answers, needs under 0.8 GB, followed instructions and extraction perfectly on this suite, its code passed every test despite the fences, and its correctness held at 34/40 under both greedy decoding and its vendor-recommended sampling. Keep **Gemma 4 E2B** for non-interactive or accuracy-critical requests where a 10–60 s wait is acceptable and nothing else memory-heavy is running. Qwen3.5-0.8B is an equally fast alternative under greedy decoding, worth preferring if inputs are long (faster prompt processing) or RAM is tight; its recommended sampling removes the greedy looping but dropped its correctness to 25/40 on this suite (section 5a), so greedy decoding is the better default for these short tasks.

## 7. Limitations

- One board, one runtime build, one quantization per model (Gemma at Q4_0, the others at Q4_K_M); different sizes, architectures, and tokenizers, so no architecture effect is isolated.
- 20 hand-written prompts with one answer each, scored by one person; a few points per category are not a statistically established difference. Coding correctness is from executed tests; all other scores are manual.
- Scoring was by one person and not fully blind. The first pass was blind (correctness totals Gemma 38, LFM 33, Qwen 32). Two later revisions were made after model identities were shown: separating correctness from adherence, then re-scoring R02 and S01 (final correctness 37, 34, 32). In the vendor set, scored blind, two Qwen coding answers were lowered from correctness 2 to 0 after unblinding because they fail the executed tests, as the behaviour-based coding rubric requires. Every version is in git history and `results/scoring*/`.
- Greedy decoding for all models, which is not every vendor's recommended setting (Qwen's card recommends sampling with a presence penalty for non-thinking mode); R04 shows the 128-token cap penalizes verbose step-by-step answers.
- Speed is synthetic, warm, and single-request; answer times are client-observed, non-streaming, warm-model times, not time to first token. Clock sampled with the `ondemand` governor; ambient temperature not measured; no electrical energy measured.
- Chat-server memory includes llama-server's default prompt cache (section 4).

## 8. Conclusion

On a 4 GB Raspberry Pi 4B, all three candidates run with llama.cpp on the CPU. LFM2.5-1.2B-Instruct and Qwen3.5-0.8B deliver most short answers within 10 s in under 0.8 GB, while Gemma 4 E2B achieved the highest correctness score on this suite, at less than half the generation speed and nearly 3 GB of RAM. The personal default is LFM2.5-1.2B for interactive use, with Gemma 4 E2B for accuracy-critical requests. The vendor-sampling follow-up (section 5a) showed that Qwen's looping is a decoding effect, fixed by its recommended presence penalty at some cost in code correctness. The most useful next experiment is several seeds per prompt under sampling, to separate sampling variance from model differences before drawing quality conclusions from a single sampled answer.

## References

See [references](../docs/REFERENCES.md). Exact artifact revisions and checksums: [configs/models.csv](../configs/models.csv); runtime commit `b1b770d90d94cad9e9ea5b993bdbc383a522fb28`.
