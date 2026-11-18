# Small Language Models on Raspberry Pi 4B

**Suggested academic title:** *A Comparative Evaluation of Quantized Small Language Models on Raspberry Pi 4B: Inference Performance, Resource Usage, and Task Quality*

A personal, reproducible evaluation of selected Gemma 4, Qwen3.5, and Liquid AI LFM2.5 deployments. The goal is to find which model is useful on **my actual Raspberry Pi 4B**, and understand the trade-offs behind that choice.

**Status:** first comparison complete (18 November 2026): feasibility, speed, and a blinded 20-prompt quality evaluation of three models on one Pi 4B (4 GB). Findings and the personal recommendation are in [reports/REPORT_TEMPLATE.md](reports/REPORT_TEMPLATE.md); the frozen protocol is in [docs/PROTOCOL_FREEZE.md](docs/PROTOCOL_FREEZE.md). Settings are the declared experiment choices, not measured optimal settings.

## Start here

1. Identify the Pi's RAM capacity, OS architecture, cooling, power supply, and storage.
2. Read [PROJECT_PLAN.md](PROJECT_PLAN.md) and complete [configs/hardware.md](configs/hardware.md).
3. Build a pinned version of llama.cpp and load **one** small model successfully.
4. Complete the feasibility checklist before downloading the remaining candidates.
5. Freeze the prompt set and settings, benchmark each supported model, then score its answers.
6. Write the findings in [reports/REPORT_TEMPLATE.md](reports/REPORT_TEMPLATE.md), including unsuccessful attempts.

## Candidate deployments

| Candidate | Initial role | Artifact choice |
| --- | --- | --- |
| Qwen3.5-0.8B | Small starting candidate | Instruction/chat checkpoint; compatible GGUF; approximately 4-bit |
| LFM2.5-1.2B-Instruct | Second starting candidate | Official GGUF, initially Q4_K_M |
| Gemma 4 E2B instruction-tuned | Conditional third candidate | Compatible approximately 4-bit GGUF, subject to actual RAM and runtime support |
| Qwen3.5-2B | Optional extension | Add only after the initial comparison works |

Use exact checkpoint names, not just family names, in the results. The Qwen 0.8B and 2B variants appear in its official model documentation [2]. Liquid provides an official GGUF repository [3]. Google describes E2B as an effective-parameter model: its memory footprint is not equivalent to a conventional dense 2B model [1].

The official LFM2.5 Q4_K_M artifact is about **731 MB on disk** at the checked revision [3]. That is a download size, not total runtime RAM. Do not infer Pi throughput from vendor measurements on phones, desktops, or Pi 5 hardware.

This is a comparison of **deployable configurations with different sizes and architectures**, not an experiment that isolates architecture or parameter count as the only variable.

## Minimal experiment

| Aspect | Initial choice |
| --- | --- |
| Hardware | One Raspberry Pi 4B; record RAM and stock operating conditions |
| Runtime | One pinned llama.cpp commit, CPU only |
| Parallelism | 4 CPU threads initially; one request at a time |
| Quantization | Prefer Q4_K_M when available; disclose every difference |
| Quality context | 2,048 tokens; batch and microbatch 128 |
| Quality generation | Greedy baseline, maximum 128 generated tokens |
| Reasoning mode | Disable optional thinking through supported template settings; verify in a pilot |
| Speed | Synthetic prompt processing at 128 and 512 tokens; generation at 64 tokens |
| Repetitions | Three measured speed repetitions per condition, after a separate warm-up |
| Quality | 20 fixed prompts across five categories; one response per prompt |
| Scoring | 0–2 correctness and 0–2 instruction adherence; preserve all raw answers |

Greedy decoding is a reproducible starting condition, not a claim that every model performs best with it. Keep model-specific recommended sampling as a separately labelled follow-up. Every model gets its own correct native chat template, while receiving the same user prompt. If reasoning cannot be disabled consistently, disclose that and do not silently mix reasoning modes.

## Setup on the Pi

Use a 64-bit OS and check that `uname -m` reports `aarch64`. The commands below assume a Debian-based Raspberry Pi OS with Git, CMake, a compiler, Python 3, GNU time, and coreutils available. Install missing prerequisites through your OS package manager.

```bash
sudo apt update
sudo apt install git cmake build-essential python3 time coreutils
git clone https://github.com/ggml-org/llama.cpp vendor/llama.cpp
```

Choose a known-working llama.cpp commit after the compatibility pilot, record its full SHA, and use it for every model. Do not assume that an arbitrary old release supports these architectures. This study uses tag `v1.0.0`, commit `b1b770d90d94cad9e9ea5b993bdbc383a522fb28`.

```bash
git clone --depth 1 --branch v1.0.0 https://github.com/ggml-org/llama.cpp vendor/llama.cpp
cmake -S vendor/llama.cpp -B vendor/llama.cpp/build -DCMAKE_BUILD_TYPE=Release \
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_OPENSSL=OFF \
  -DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_BUILD_UI=OFF
cmake --build vendor/llama.cpp/build --config Release -j 2 --target llama-bench llama-server llama-cli
python3 scripts/capture_environment.py --output results/raw/environment-<date>.json
```

The web UI is disabled: answers are collected through the server API, and in a shallow clone the prebuilt-UI download resolves the wrong asset version and fails the build. The server therefore reports version `1.0.0-dev (build 1, commit b1b770d)`; the commit SHA is the identity to record.

Replace angle-bracket placeholders before executing commands. Build with fewer jobs if RAM is limited. Keep the same build options for all models and inspect the build log to confirm CPU execution. Consult upstream build instructions [4] if your OS needs different dependencies.

Download one selected GGUF per candidate from a documented source and place it under `models/`. No model weights are included. Record its repository revision, filename, license, byte size, and checksum in `configs/models.csv`.

```bash
sha256sum models/<exact-model-filename>.gguf
vendor/llama.cpp/build/bin/llama-bench --help
vendor/llama.cpp/build/bin/llama-server --help
```

## Run a speed benchmark

```bash
python3 scripts/benchmark.py \
  --model models/<exact-model-filename>.gguf \
  --label qwen35-08b-q4 \
  --out results/raw/qwen35-08b-speed
```

The wrapper runs an excluded warm-up followed by one llama-bench invocation with three internal repetitions per condition. It saves JSONL, logs, GNU time output, the exact command, file checksum, and success/failure metadata. By default, each invocation has a 30-minute ceiling; change `--timeout` only under a documented policy applied equally to all candidates. It refuses to overwrite an existing run directory.

Synthetic `pp` and `tg` are separate tests. `tg64` is not the same as decoding an answer after a 512-token user prompt. These tests provide runtime microbenchmarks, not application latency or answer quality [5]. The batch size is 128; no claim is made that it is optimal.

For optional thermal monitoring, run this in a second terminal before the benchmark and stop it with Ctrl+C afterwards:

```bash
python3 scripts/monitor.py --output results/raw/qwen35-08b-telemetry.csv
```

Use the same monitoring setup for every model. The script samples temperature, throttling, CPU clock, and system memory. It does not measure process peak RAM or electrical power. GNU time reports the benchmark process peak RSS separately.

## Collect task answers

Answers are collected through the llama-server chat API, one model resident at a time, with the frozen settings in [docs/PROTOCOL_FREEZE.md](docs/PROTOCOL_FREEZE.md): a fresh single-turn chat per prompt containing the **prompt field only**, greedy decoding, 128 generated tokens, thinking disabled through `chat_template_kwargs`, prompt cache off. Qwen's official documentation warns that `/nothink` is not the supported switching mechanism [2]; the template kwarg is used instead and verified in each saved rendered prompt.

```bash
scripts/session.sh speed   qwen35-08b-q4km models/Qwen3.5-0.8B-Q4_K_M.gguf
scripts/session.sh quality qwen35-08b-q4km models/Qwen3.5-0.8B-Q4_K_M.gguf
```

`session.sh quality` verifies the frozen prompt checksum, waits for a comparable start temperature, and runs `scripts/collect_answers.py`, which saves each request, rendered prompt, full response, finish reason, token counts, and client-observed wall time under `results/raw/quality/<label>/`. Never send the answer key to the model. Score using `data/quality_scores.csv` and [docs/EVALUATION.md](docs/EVALUATION.md).

## Repository contents

| Path | Purpose |
| --- | --- |
| `README.md` | Project overview and quick start |
| `PROJECT_PLAN.md` | Scope, research questions, controls, and decision rules |
| `configs/hardware.md` | Hardware and software recording sheet |
| `configs/models.csv` | Exact artifact manifest; initially unfilled |
| `data/prompts.jsonl` | 20 original prompts with reference answers and criteria |
| `data/pilot_prompts.jsonl` | Two non-scored pilot prompts (format check, output-cap check) |
| `data/prompts.jsonl.sha256` | Frozen checksum of the scored prompt set |
| `docs/PROTOCOL_FREEZE.md` | Frozen settings, pilot findings, and the deviation log |
| `data/quality_scores.csv` | Empty scoring table with documented columns |
| `docs/EVALUATION.md` | Run order, metrics, scoring, and interpretation |
| `docs/TITLES.md` | Academic title alternatives |
| `docs/REFERENCES.md` | Official documentation checked for this plan |
| `scripts/capture_environment.py` | Best-effort environment snapshot |
| `scripts/benchmark.py` | Timed synthetic benchmark wrapper |
| `scripts/monitor.py` | Optional Pi telemetry sampler |
| `scripts/fetch_model.sh` | Download a GGUF from a pinned Hugging Face revision and verify its SHA-256 |
| `scripts/feasibility.py` | Feasibility gate: load in llama-server, one non-scored chat, telemetry, provisional status |
| `scripts/collect_answers.py` | API answer collection: one fresh chat per prompt, saves request, response, status, wall time |
| `scripts/common.py` | Shared llama-server lifecycle, chat request, and telemetry for the two scripts above |
| `scripts/pilot.sh` | Phase 4 pilot: short llama-bench run plus the two pilot prompts |
| `scripts/session.sh` | Measured speed or quality session for one model: cooldown, checksum check, telemetry, throttle flags |
| `scripts/score_tools.py` | Blinded scoring on the workstation: coded sheets, isolated code tests, unblind, category totals |
| `pi` | Sync the repo to the Pi (`bagwis-core`), run commands there, pull raw results back |
| `results/raw/` | Local raw outputs; ignored by Git |
| `results/processed/` | Curated tables to commit |
| `reports/REPORT_TEMPLATE.md` | Report structure with blank results |
| `models/`, `vendor/` | Local weights and runtime source; ignored by Git |

## Scope and limits

No training, fine-tuning, vision/audio inputs, retrieval system, agents, web access, or accelerator hardware is required. Energy measurement is optional and requires an external meter; CPU usage is not a power measurement. Twenty hand-authored prompts establish personal usefulness, not a comprehensive standardized intelligence ranking. Keep speed, resource usage, and task quality separate when making the final recommendation.

## References

Numbered links and access date: [docs/REFERENCES.md](docs/REFERENCES.md).
