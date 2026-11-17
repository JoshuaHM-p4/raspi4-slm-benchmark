# Hardware and software record

Fill before collecting scored results. Keep a snapshot for each session if anything changes.

| Field | Value |
| --- | --- |
| Device / board revision | Raspberry Pi 4B / TBD |
| Installed RAM / available before load | TBD |
| OS version / 64-bit userspace | TBD |
| Kernel / firmware | TBD |
| CPU clock / governor / overclock | TBD / stock initially |
| Cooling / fan configuration / case | TBD |
| Power supply model and rating | TBD |
| Storage type and model / free disk | TBD |
| Swap/zram configuration | TBD |
| Ambient temperature if available | TBD |
| Runtime full commit SHA | TBD |
| Compiler / CMake / build flags | TBD |
| CPU-only confirmation | TBD |
| Baseline temperature / throttling flags | TBD |
| Background services / SSH / monitor | TBD |

Use `python3 scripts/capture_environment.py` for an initial snapshot. Missing commands become unavailable fields; record them manually where necessary. Do not treat an unavailable measurement as zero.
