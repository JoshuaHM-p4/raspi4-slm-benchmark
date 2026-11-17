# References

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
