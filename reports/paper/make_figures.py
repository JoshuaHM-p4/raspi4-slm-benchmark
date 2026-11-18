#!/usr/bin/env python3
"""Build the paper's figures (vector PDF, IEEE single-column width) from results/processed and raw telemetry.

Run from the repository root:  python3 reports/paper/make_figures.py
"""
import csv
import datetime as dt
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

PROC, RAW, OUT = Path("results/processed"), Path("results/raw"), Path("reports/paper/figures")
MODELS = ["qwen35-08b-q4km", "lfm25-12b-q4km", "gemma4-e2b-q4_0"]
SHORT = {"qwen35-08b-q4km": "Qwen3.5-0.8B", "lfm25-12b-q4km": "LFM2.5-1.2B", "gemma4-e2b-q4_0": "Gemma 4 E2B"}
COLOR = {"qwen35-08b-q4km": "#4C72B0", "lfm25-12b-q4km": "#DD8452", "gemma4-e2b-q4_0": "#55A868"}
HATCH = {"qwen35-08b-q4km": "", "lfm25-12b-q4km": "//", "gemma4-e2b-q4_0": ".."}
CATEGORIES = ["instruction", "extraction", "reasoning", "summarization", "coding"]
COL_W = 3.5  # IEEE column width, inches
BUDGET_S = 10.0

plt.rcParams.update({"font.family": "serif", "font.serif": ["Times", "Times New Roman", "DejaVu Serif"],
                     "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.spines.top": False,
                     "axes.spines.right": False, "pdf.fonttype": 42, "savefig.bbox": "tight",
                     "savefig.pad_inches": 0.02, "hatch.linewidth": 0.5})


def rows(name):
    return list(csv.DictReader((PROC / name).open()))


def save(fig, name):
    fig.savefig(OUT / name, metadata={"CreationDate": None})  # deterministic bytes across rebuilds
    plt.close(fig)
    print(OUT / name)


def fig_speed():
    data = {(r["model_label"], r["test"]): (float(r["mean_tokens_per_s"]), float(r["sd_tokens_per_s"]))
            for r in rows("speed.csv")}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(COL_W, 1.7), gridspec_kw={"width_ratios": [2, 1]})
    width = 0.26
    for ax, tests, title in ((ax1, ["pp128", "pp512"], "Prompt processing"), (ax2, ["tg64"], "Generation")):
        x = np.arange(len(tests))
        for i, m in enumerate(MODELS):
            means = [data[(m, t)][0] for t in tests]
            sds = [data[(m, t)][1] for t in tests]
            bars = ax.bar(x + (i - 1) * width, means, width, yerr=sds, capsize=1.5, color=COLOR[m],
                          hatch=HATCH[m], edgecolor="black", linewidth=0.4, label=SHORT[m])
            ax.bar_label(bars, fmt="%.1f", fontsize=6, padding=1)
        ax.set_xticks(x, tests)
        ax.set_title(title)
        ax.set_ylim(0, max(data[(m, t)][0] for m in MODELS for t in tests) * 1.22)
    ax1.set_ylabel("tokens/s (mean ± SD, n = 3)")
    ax1.legend(frameon=False, loc="upper center", ncol=3, bbox_to_anchor=(0.75, -0.16))
    save(fig, "speed.pdf")


def fig_quality():
    q = {(r["model_label"], r["category"]): r for r in rows("quality_by_category.csv") if r["set"] == "greedy"}
    fig, axes = plt.subplots(2, 1, figsize=(COL_W, 2.6), sharex=True)
    x = np.arange(len(CATEGORIES))
    width = 0.26
    for ax, field, label in ((axes[0], "correctness", "Correctness (/8)"), (axes[1], "adherence", "Adherence (/8)")):
        for i, m in enumerate(MODELS):
            values = [int(q[(m, c)][field]) for c in CATEGORIES]
            bars = ax.bar(x + (i - 1) * width, values, width, color=COLOR[m], hatch=HATCH[m], edgecolor="black",
                          linewidth=0.4, label=SHORT[m])
            ax.bar_label(bars, fontsize=5.5, padding=0.5)
        ax.set_ylim(0, 9.3)
        ax.set_yticks([0, 2, 4, 6, 8])
        ax.set_ylabel(label)
    axes[1].set_xticks(x, ["Instruct.", "Extract.", "Reason.", "Summar.", "Coding"])
    axes[0].legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    save(fig, "quality.pdf")


def fig_latency():
    times = {m: [float(r["wall_seconds"]) for r in rows("answer_times.csv")
                 if r["set"] == "greedy" and r["model_label"] == m] for m in MODELS}
    fig, ax = plt.subplots(figsize=(COL_W, 1.9))
    rng = np.random.default_rng(0)
    for i, m in enumerate(MODELS):
        values = np.array(times[m])
        ax.boxplot(values, positions=[i], widths=0.45, orientation="horizontal", showfliers=False,
                   medianprops={"color": "black"}, boxprops={"linewidth": 0.6}, whiskerprops={"linewidth": 0.6},
                   capprops={"linewidth": 0.6})
        ax.scatter(values, i + rng.uniform(-0.14, 0.14, len(values)), s=7, color=COLOR[m], edgecolor="black",
                   linewidth=0.3, zorder=3)
        within = int((values <= BUDGET_S).sum())
        ax.text(values.max() + 1.0, i, f"{within}/20 ≤ 10 s", va="center", fontsize=6.5)
    ax.axvline(BUDGET_S, color="crimson", linestyle="--", linewidth=0.8)
    ax.text(BUDGET_S + 0.4, 2.45, "10 s budget", color="crimson", fontsize=6.5)
    ax.set_yticks(range(len(MODELS)), [SHORT[m] for m in MODELS])
    ax.set_xlabel("Client-observed answer time per prompt (s)")
    ax.set_xlim(0, 70)
    save(fig, "latency.pdf")


def fig_memory():
    mem = rows("memory.csv")
    pick = lambda model, kind: next((int(r["vmhwm_kib"]) for r in mem
                                     if r["model_label"] == model and r["kind"].startswith(kind)
                                     and r["set"] in ("speed", "greedy", "diagnostic")), None)
    total_mib = 3886836 / 1024
    fig, ax = plt.subplots(figsize=(COL_W, 1.75))
    y = np.arange(len(MODELS))
    bench = [pick(m, "llama-bench") / 1024 for m in MODELS]
    server = [pick(m, "chat server (default") / 1024 for m in MODELS]
    ax.barh(y + 0.18, bench, 0.34, color=[COLOR[m] for m in MODELS], edgecolor="black", linewidth=0.4,
            label="llama-bench peak RSS")
    ax.barh(y - 0.18, server, 0.34, color="white", edgecolor=[COLOR[m] for m in MODELS], hatch="////",
            linewidth=0.8, label="chat server VmHWM, default prompt cache")
    diag = pick("qwen35-08b-q4km", "chat server --cache-ram 0")
    if diag:
        ax.plot([diag / 1024], [-0.18], marker="|", color="black", markersize=9, mew=1.2)
        ax.annotate("same server, --cache-ram 0", (diag / 1024, -0.18), xytext=(server[0] + 120, -0.18),
                    fontsize=6, va="center", arrowprops={"arrowstyle": "-", "linewidth": 0.5})
    ax.axvline(total_mib, color="crimson", linestyle="--", linewidth=0.8)
    ax.text(total_mib - 30, 2.55, "MemTotal 3796 MiB", color="crimson", fontsize=6.5, ha="right")
    ax.set_yticks(y, [SHORT[m] for m in MODELS])
    ax.set_xlabel("Resident memory (MiB)")
    ax.set_xlim(0, 4100)
    ax.set_ylim(-0.55, 2.75)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=2, fontsize=6)
    save(fig, "memory.pdf")


def fig_tradeoff():
    q = {r["model_label"]: r for r in rows("quality_by_category.csv") if r["set"] == "greedy" and r["category"] == "total"}
    times = {m: np.median([float(r["wall_seconds"]) for r in rows("answer_times.csv")
                           if r["set"] == "greedy" and r["model_label"] == m]) for m in MODELS}
    rss = {r["model_label"]: int(r["benchmark_peak_rss_kib"]) / 1024 for r in rows("speed.csv") if r["test"] == "tg64"}
    fig, ax = plt.subplots(figsize=(COL_W, 1.9))
    offsets = {"qwen35-08b-q4km": (9, -9), "lfm25-12b-q4km": (9, 7), "gemma4-e2b-q4_0": (11, -3)}
    for m in MODELS:
        ax.scatter(times[m], int(q[m]["correctness"]), s=rss[m] / 9, color=COLOR[m], edgecolor="black",
                   linewidth=0.5, alpha=0.85, zorder=3)
        ax.annotate(f"{SHORT[m]}, {rss[m]:.0f} MiB", (times[m], int(q[m]["correctness"])), xytext=offsets[m],
                    textcoords="offset points", fontsize=6.5, va="center")
    ax.axvline(BUDGET_S, color="crimson", linestyle="--", linewidth=0.8)
    ax.text(BUDGET_S + 0.1, 39.3, "10 s budget", color="crimson", fontsize=6.5)
    ax.set_xlim(5, 15)
    ax.set_ylim(30, 40)
    ax.set_xlabel("Median answer time (s)")
    ax.set_ylabel("Correctness (/40)")
    save(fig, "tradeoff.pdf")


def fig_thermal():
    fig, ax = plt.subplots(figsize=(COL_W, 1.6))
    for m in MODELS:
        samples = list(csv.DictReader((RAW / "speed" / m / "telemetry.csv").open()))
        t0 = dt.datetime.fromisoformat(samples[0]["timestamp_utc"])
        t = [(dt.datetime.fromisoformat(s["timestamp_utc"]) - t0).total_seconds() for s in samples]
        temp = [float(s["temperature_c"]) for s in samples]
        ax.plot(t, temp, color=COLOR[m], linewidth=0.9, label=SHORT[m])
    ax.axhline(80, color="crimson", linestyle="--", linewidth=0.8)
    ax.text(5, 76.5, "80 °C soft-throttle threshold", color="crimson", fontsize=6.5)
    ax.set_xlabel("Time since session start (s)")
    ax.set_ylabel("SoC temperature (°C)")
    ax.set_ylim(35, 85)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.18))
    save(fig, "thermal.pdf")


def fig_repetition():
    data = [r for r in rows("pilot_p02_repetition.csv")]
    sets = [s for s in ("greedy", "vendor") if any(r["set"] == s for r in data)]
    fig, ax = plt.subplots(figsize=(COL_W, 1.5))
    width = 0.36 if len(sets) == 2 else 0.5
    x = np.arange(len(MODELS))
    for j, s in enumerate(sets):
        values, totals = [], []
        for m in MODELS:
            r = next((r for r in data if r["set"] == s and r["model_label"] == m), None)
            values.append(int(r["distinct_items"]) / int(r["list_items"]) if r else 0)
            totals.append(f"{r['distinct_items']}/{r['list_items']}" if r else "")
        offset = (j - (len(sets) - 1) / 2) * width
        bars = ax.bar(x + offset, values, width, color=[COLOR[m] for m in MODELS], edgecolor="black",
                      linewidth=0.4, hatch="" if s == "greedy" else "xxx", label=f"{s} decoding")
        ax.bar_label(bars, labels=totals, fontsize=6, padding=1)
    ax.set_xticks(x, [SHORT[m] for m in MODELS])
    ax.set_ylim(0, 1.25)
    ax.set_ylabel("Distinct / listed items")
    if len(sets) == 2:
        ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.2))
    save(fig, "repetition.pdf")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig_speed()
    fig_quality()
    fig_latency()
    fig_memory()
    fig_tradeoff()
    fig_thermal()
    fig_repetition()
