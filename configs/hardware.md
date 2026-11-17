# Hardware and software record

Fill before collecting scored results. Keep a snapshot for each session if anything changes.

| Field | Value |
| --- | --- |
| Device / board revision | Raspberry Pi 4 Model B Rev 1.5 |
| Installed RAM / available before load | 4 GB (MemTotal 3886836 KiB); MemAvailable 3459700 KiB idle on 2026-11-18. Per-run value: `before.mem_available_kib` in each `result.json` |
| OS version / 64-bit userspace | Debian GNU/Linux 13 (trixie); aarch64 userspace (`getconf LONG_BIT` = 64, dpkg arch arm64) |
| Kernel / firmware | 6.18.50+rpt-rpi-v8 / VideoCore firmware Sep 7 2026 10:23:43 |
| CPU clock / governor / overclock | 1.8 GHz max / `ondemand` / none (no `arm_freq`/`over_voltage` in config.txt) |
| Cooling / fan configuration / case | Heatsink with fan on 5 V GPIO pins (always on, not software-controlled; no fan device visible to Linux) |
| Power supply model and rating | 5 V 2 A adapter (below the 5 V 3 A official spec; the usual adapter has the same rating). Fan draws from the same supply |
| Storage type and model / free disk | microSD 29.7 GB (mmcblk0); 11.4 GB free on / |
| Swap/zram configuration | 2 GiB zram0 swap, priority 100; no disk swap; unchanged for the study |
| Ambient temperature if available | Not measured |
| Runtime full commit SHA | llama.cpp `b1b770d90d94cad9e9ea5b993bdbc383a522fb28` (tag v1.0.0) |
| Compiler / CMake / build flags | GCC 14.2.0 / CMake 3.31.6 / Release, `-DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_BUILD_UI=OFF`, GGML_NATIVE default |
| CPU-only confirmation | Only the CPU backend was built: `ggml-cpu` variant `-mcpu=cortex-a72+crc+nodotprod+noi8mm+nosve+nosme` (build logs in `results/raw/build/`) |
| Baseline temperature / throttling flags | Per run: `before`/`after` in each `result.json`. After the 40 min build: 46.7 °C, `throttled=0x0` |
| Background services / SSH / monitor | sshd (one session for control), Docker daemon idle with all bagwis containers stopped; monitor is the in-process 1 Hz sampler in `scripts/feasibility.py` |

Use `python3 scripts/capture_environment.py` for an initial snapshot. Missing commands become unavailable fields; record them manually where necessary. Do not treat an unavailable measurement as zero.
