# Small Language Models on Raspberry Pi 4B

[![Read the Paper](https://img.shields.io/badge/Read_the_Paper-IEEE_PDF-b31b1b?style=for-the-badge&logo=adobeacrobatreader&logoColor=white)](reports/paper/paper.pdf)
[![Full Report](https://img.shields.io/badge/Full_Report-Markdown-0969da?style=for-the-badge&logo=markdown&logoColor=white)](reports/REPORT.md)
[![Raw Data](https://img.shields.io/badge/Raw_Data-SHA--256_verified-2da44e?style=for-the-badge&logo=databricks&logoColor=white)](results/README.md)

![Raspberry Pi 4B](https://img.shields.io/badge/Raspberry_Pi_4B-4_GB-C51A4A?logo=raspberrypi&logoColor=white)
![llama.cpp](https://img.shields.io/badge/llama.cpp-v1.0.0_%C2%B7_CPU_only-555?logo=cplusplus)
![Models](https://img.shields.io/badge/models-Qwen3.5_%C2%B7_LFM2.5_%C2%B7_Gemma_4-6f42c1)

A reproducible comparison of three quantized small language models running locally on one Raspberry Pi 4B: **Qwen3.5-0.8B**, **LFM2.5-1.2B-Instruct**, and **Gemma 4 E2B-it**. Feasibility, speed, memory, thermals, and blind-scored answer quality are measured separately, and every raw log, answer, and score sheet is published.

## Results at a glance

| Model (quantization) | Generation | Prompt processing (pp512) | Peak RAM | Median answer | Answers ≤ 10 s | Correctness | Adherence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.5-0.8B (Q4_K_M) | 5.24 tok/s | 19.31 tok/s | 625 MiB | 6.75 s | 17 / 20 | 32 / 40 | 31 / 40 |
| LFM2.5-1.2B-Instruct (Q4_K_M) | 5.00 tok/s | 12.23 tok/s | 749 MiB | 6.72 s | 17 / 20 | 34 / 40 | 34 / 40 |
| Gemma 4 E2B-it (Q4_0) | 2.35 tok/s | 14.86 tok/s | 2,838 MiB | 10.92 s | 8 / 20 | 37 / 40 | 39 / 40 |

Speed from llama-bench (mean of 3 runs, SD ≤ 0.05 tok/s); peak RAM of the benchmark process; quality on 20 hand-written prompts scored 0–2 per dimension, greedy decoding. No throttling or undervoltage occurred at any point.

**Recommendation for this board:** LFM2.5-1.2B-Instruct as the interactive default (fast, small, and stable across decoding settings); Gemma 4 E2B when accuracy matters more than a 10–60 s wait. Qwen3.5-0.8B loops on long lists under greedy decoding; its vendor-recommended sampling fixes that but lowered its correctness to 25/40 in the follow-up. Details, caveats, and the vendor-sampling follow-up are in the [paper](reports/paper/paper.pdf) and [report](reports/REPORT.md).

## Setup

| | |
| --- | --- |
| Board | Raspberry Pi 4 Model B Rev 1.5, 4 GB, heatsink + 5 V fan, 5 V 2 A supply |
| OS | Debian 13 (aarch64), kernel 6.18, 2 GiB zram swap |
| Runtime | llama.cpp `v1.0.0` (`b1b770d`), CPU backend only, 4 threads |
| Models | Pinned by revision and SHA-256 in [configs/models.csv](configs/models.csv) |
| Protocol | Feasibility gate → pilot → frozen settings ([docs/PROTOCOL_FREEZE.md](docs/PROTOCOL_FREEZE.md)) → speed → answers → blind scoring |

## Try the models yourself

On the Pi, from `~/raspi4bench-slm` (one model at a time; 4 GB does not fit two):

```bash
# Interactive chat (Ctrl+C to quit); add -st -p "question" for a single answer
vendor/llama.cpp/build/bin/llama-cli -m models/LFM2.5-1.2B-Instruct-Q4_K_M.gguf \
  -t 4 -c 2048 --temp 0 --chat-template-kwargs '{"enable_thinking":false}'

# OpenAI-compatible server; from a laptop: ssh -L 8080:127.0.0.1:8080 <pi>
vendor/llama.cpp/build/bin/llama-server -m models/gemma-4-E2B-it-Q4_0.gguf \
  -t 4 -c 2048 -np 1 --cache-ram 0 --host 127.0.0.1 --port 8080
```

```bash
curl -s localhost:8080/v1/chat/completions -H "Content-Type: application/json" -d '{
  "messages":[{"role":"user","content":"Name two output devices."}],
  "max_tokens":128, "temperature":0, "chat_template_kwargs":{"enable_thinking":false}}'
```

`--cache-ram 0` keeps llama-server's prompt cache from growing memory per request. Vendor-recommended sampling settings per model are in [configs/vendor_sampling.json](configs/vendor_sampling.json).

## Reproduce the study

**1. Build llama.cpp on the Pi** (needs `git cmake build-essential python3 time`):

```bash
git clone --depth 1 --branch v1.0.0 https://github.com/ggml-org/llama.cpp vendor/llama.cpp
cmake -S vendor/llama.cpp -B vendor/llama.cpp/build -DCMAKE_BUILD_TYPE=Release \
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_OPENSSL=OFF \
  -DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_BUILD_UI=OFF
cmake --build vendor/llama.cpp/build --config Release -j 2 --target llama-bench llama-server llama-cli
```

The web UI is disabled: in a shallow clone its prebuilt-asset download resolves the wrong version and fails the build, and all answers go through the API.

**2. Fetch the pinned models** (revision and checksum from [configs/models.csv](configs/models.csv)):

```bash
scripts/fetch_model.sh LiquidAI/LFM2.5-1.2B-Instruct-GGUF 8ed288026e23958ad9dfa92d53ed773a8eee7125 \
  LFM2.5-1.2B-Instruct-Q4_K_M.gguf b1b3de114215d9507409a662a501a631095a479a419584e8a2ded6304b19b4f5
```

**3. Run the measured sessions** (each waits for ≤ 45 °C and records telemetry and throttle flags):

```bash
scripts/feasibility.py --model models/<file>.gguf --label <label> --out results/raw/feasibility/<label>-r1
scripts/session.sh speed          <label> models/<file>.gguf   # llama-bench pp128, pp512, tg64
scripts/session.sh quality        <label> models/<file>.gguf   # 20 frozen prompts, greedy
scripts/session.sh quality-vendor <label> models/<file>.gguf   # same, vendor sampling, seed 42
```

**4. Score blind and build the outputs** (on a workstation; coding answers run in a network-less container):

```bash
python3 scripts/score_tools.py sheets            # then fill results/scoring/blind_scores.csv
python3 scripts/score_tools.py unblind
reports/paper/build.sh                           # processed tables, figures, paper PDF
sha256sum -c results/SHA256SUMS                  # verify every raw and scoring file
```

From a separate machine, `./pi run '<command>'` syncs the repository to the Pi and runs a command there; `./pi pull` copies raw results back.

## Repository layout

| Path | Contents |
| --- | --- |
| [`reports/paper/`](reports/paper) | IEEE conference paper (`paper.pdf`, `paper.tex`), figures, build script |
| [`reports/REPORT.md`](reports/REPORT.md) | Full report with per-category tables and representative answers |
| [`results/`](results/README.md) | Raw logs, answers, telemetry, blind score sheets and keys, curated tables, checksums |
| [`data/`](data) | Frozen prompt set and checksum, pilot prompts, final score tables |
| [`configs/`](configs) | Hardware record, model manifest, vendor sampling presets |
| [`docs/`](docs) | Project plan details, evaluation rubric, protocol freeze and deviation log, references |
| [`scripts/`](scripts) | Fetch, feasibility gate, benchmark, answer collection, sessions, scoring, processing |
| [`PROJECT_PLAN.md`](PROJECT_PLAN.md) | Scope, research questions, controls, and decision rules |

Model weights and the llama.cpp source are not included (`models/`, `vendor/`).

## Limitations

One board, one runtime build, and one quantization per model (Gemma at Q4_0, the others at Q4_K_M). Twenty prompts with one answer each and a single scorer support descriptive comparisons, not statistical ones; part of the scoring was revised after unblinding, as documented in the report. Speeds are synthetic and warm; answer times are non-streaming. Energy was not measured.
