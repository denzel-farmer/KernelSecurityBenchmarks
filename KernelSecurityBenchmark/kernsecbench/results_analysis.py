#!/usr/bin/env python3
import csv
import os
import re
import statistics
from textwrap import dedent
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from collections import defaultdict
import math
from scipy.stats import linregress   # SciPy gives r², stderr, etc.


def _fit_power_law(x: np.ndarray, y: np.ndarray):
    """
    Fit y = k * x^alpha  (equivalently:  log y = log k + alpha * log x )
    Returns (k, alpha, r_value)   where r_value is Pearson’s r.
    """
    logx = np.log(x)
    logy = np.log(y)
    slope, intercept, r, *_ = linregress(logx, logy)
    k = np.exp(intercept)
    alpha = slope
    return k, alpha, r


def fit_stream_iterations(df_long: pd.DataFrame, stream_key: str,
                          min_points: int = 4, r_thresh: float = 0.85):
    """
    Fit every (run, iteration) of *stream_key*.
    Returns
    -------
    results : dict
        { run : [ (k, alpha) , … ] }   only if fit passes r‑squared threshold.
    """
    res = defaultdict(list)
    subset = df_long[(df_long["stream"] == stream_key) & df_long["z"].isna()]
    if subset.empty:
        raise ValueError(f"No 2‑col data for {stream_key}")

    for (run, it), grp in subset.groupby(["run", "iteration"]):
        if len(grp) < min_points:
            continue
        k, alpha, r = _fit_power_law(grp["x"].values, grp["y"].values)
        if r**2 >= r_thresh:
            res[run].append((k, alpha))
    return res

def _avg_params(param_list):
    arr = np.array(param_list)
    return arr.mean(axis=0), arr.std(axis=0)

def average_fit_params(fit_dict: dict):
    """
    Parameters
    ----------
    fit_dict  –  output of fit_stream_iterations()

    Returns
    -------
    { run : {"k": k̄, "alpha": ᾱ, "k_std": σ_k, "alpha_std": σ_α} }
    """
    out = {}
    for run, plist in fit_dict.items():
        (k_mean, alpha_mean), (k_std, alpha_std) = _avg_params(plist)
        out[run] = dict(k=k_mean, alpha=alpha_mean,
                        k_std=k_std, alpha_std=alpha_std,
                        n=len(plist))
    return out

def plot_stream_fits(df_long: pd.DataFrame,
                     stream_key: str,
                     dpi: int = 120,
                     figsize=(7, 5),
                     x_samples: int = 50):
    """
    Draw the averaged power‑law curves for each run on ONE figure.
    """
    fit_raw   = fit_stream_iterations(df_long, stream_key)
    fit_avgs  = average_fit_params(fit_raw)
    if not fit_avgs:
        print(f"[!] Nothing to plot for {stream_key}")
        return

    # common x‑range = union of raw data for this stream
    data = df_long[df_long["stream"] == stream_key]
    xmin, xmax = data["x"].min(), data["x"].max()
    xs = np.logspace(np.log10(xmin), np.log10(xmax), x_samples)

    colors = _run_color_map(fit_avgs.keys())

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    for run, p in fit_avgs.items():
        ys = p["k"] * xs**p["alpha"]
        label = f"{run}  (α={p['alpha']:+.2f}, k={p['k']:.0f})"
        ax.plot(xs, ys, color=colors[run], label=label, lw=2)

    ax.set_xscale("log")
    ax.set_xlabel("Block / working‑set size")
    ax.set_ylabel("Value")
    ax.set_title(f"{stream_key} – power‑law fit")
    ax.grid(True, which="both", ls="--", alpha=0.3)
    ax.legend(fontsize="small")
    plt.tight_layout()

    out = os.path.join(FIG_DIR, f"{stream_key}_fit.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[+] saved {os.path.basename(out)}")
    return fig, ax

def plot_all_stream_fits(df_long: pd.DataFrame, dpi: int = 120):
    for stream_key in stream_title_regexes.keys():
        try:
            plot_stream_fits(df_long, stream_key, dpi=dpi)
        except ValueError:
            continue    # skip streams without 2‑col data


_PAIR_RE = re.compile(r'^\s*([0-9.]+)\s+([0-9.]+)(?:\s+([0-9.]+))?\s*$')

# Scalar line formats:
# Simple syscall: 0.0464 microseconds
# Simple read: 0.0761 microseconds
# Simple write: 0.0762 microseconds
# Simple stat: 0.2787 microseconds
# Simple fstat: 0.1033 microseconds
# Simple open/close: 0.4533 microseconds
# Select on 10 fd's: 0.1364 microseconds
# Select on 100 fd's: 0.5960 microseconds
# Select on 250 fd's: 1.3695 microseconds
# Select on 500 fd's: 2.6646 microseconds
# Select on 10 tcp fd's: 0.1753 microseconds
# Select on 100 tcp fd's: 2.6039 microseconds
# Select on 250 tcp fd's: 6.6985 microseconds
# Select on 500 tcp fd's: 13.6352 microseconds
# Pipe latency: 14.2450 microseconds
# AF_UNIX sock stream latency: 13.8401 microseconds
# Process fork+exit: 55.2078 microseconds
# Process fork+execve: 176.6574 microseconds
# Process fork+/bin/sh -c: 385.2794 microseconds
# # File /var/tmp/XXX write bandwidth: 903583 KB/sec


# Regular expression to match each line:
scalar_regexes = {
    "syscall": r"^Simple syscall:\s*([0-9.]+)\s+(\w+)$",
    "read": r"^Simple read:\s*([0-9.]+)\s+(\w+)$",
    "write": r"^Simple write:\s*([0-9.]+)\s+(\w+)$",
    "stat": r"^Simple stat:\s*([0-9.]+)\s+(\w+)$",
    "fstat": r"^Simple fstat:\s*([0-9.]+)\s+(\w+)$",
    "open_close": r"^Simple open/close:\s*([0-9.]+)\s+(\w+)$",
    "select_N": r"^Select on (\d+) fd's:\s*([0-9.]+)\s+(\w+)$",
    "select_N_tcp": r"^Select on (\d+) tcp fd's:\s*([0-9.]+)\s+(\w+)$",
    "pipe_latency": r"^Pipe latency:\s*([0-9.]+)\s+(\w+)$",
    "unix_sock_stream_latency": r"^AF_UNIX sock stream latency:\s*([0-9.]+)\s+(\w+)$",
    "fork_exit": r"^Process fork\+exit:\s*([0-9.]+)\s+(\w+)$",
    "fork_execve": r"^Process fork\+execve:\s*([0-9.]+)\s+(\w+)$",
    "fork_bin_sh": r"^Process fork\+/bin/sh -c:\s*([0-9.]+)\s+(\w+)$",
    "file_write_bandwidth": r"^File /var/tmp/XXX write bandwidth:\s*([0-9.]+)\s+(\w+)$",
}


def parse_scalar_metric(line: str):
    # Extract each scalar metric from each line

    # Check if the result is in the scalar regexes
    metric = None
    for key, regex in scalar_regexes.items():
        # print("Checking regex:", regex)
        # print("Checking line:", line)
        if re.match(regex, line):
            metric_name = key
            # print(f"Found metric: {metric_name} in line: {line}")
            new_metric = None
            if metric_name == "select_N" or metric_name == "select_N_tcp":
                # Extract the number of file descriptors from the regex
                match = re.match(regex, line)
                if match:
                    num_fds = match.group(1)
                    metric_name = f"select_{num_fds}"
                    float_value = float(match.group(2))
                    unit = match.group(3)
                    new_metric = {
                        "metric": metric_name,
                        "value": float_value,
                        "unit": unit
                    }

                    # metric_map[metric_name] = metric
                else:
                    print(
                        f"Could not extract number of file descriptors from row: {line}")

            else:
                # Extract the metric name, value, and unit from the regex
                match = re.match(regex, line)
                if match:
                    metric_name = key
                    float_value = float(match.group(1))
                    unit = match.group(2)
                    new_metric = {
                        "metric": metric_name,
                        "value": float_value,
                        "unit": unit
                    }
                else:
                    raise print(f"Could not extract metric from row: {line}")

            if (metric is not None and new_metric is not None):
                raise print(
                    f"Duplicate metric found: {metric} and {new_metric['metric']}")
            metric = new_metric

    return metric

# Example inkscape format:
# Operation: SVG Files To PNG:
# 33.815
# 32.37
# 32.303
# 32.135

_OPERATION_LINE = re.compile(r'^Operation:\s*([^:]+):', re.IGNORECASE)
def parse_inkscape_scalars(text: str):
    """
    Walk through the file line‑by‑line.
    Every time a line matches 'Operation: <name>:',
    collect the next three lines as floats and emit
    {'metric': <name>, 'value': <float>} dictionaries.

    Returns
    -------
    List[dict]
    """
    lines   = text.splitlines()          # keeps order and empty lines :contentReference[oaicite:0]{index=0}
    metrics = []
    i = 0

    while i < len(lines):
        m = _OPERATION_LINE.match(lines[i])   # anchor at current line :contentReference[oaicite:1]{index=1}
        if m:
            name = m.group(1).strip()
            # Read exactly the next three lines.
            for j in range(1, 4):
                if i + j >= len(lines):
                    break                    # premature EOF
                try:
                    value = float(lines[i + j].strip())
                except ValueError:
                    break                    # line wasn't numeric; abandon this block
                metrics.append({"metric": name, "value": value, "unit": "s"})
            i += 4                            # skip header + 3 value lines
        else:
            i += 1                            # move to next line
    return metrics


# Example glibc scalar format:
# Benchmark: cos:
# 90.7372
# 90.7282
# 90.4056

_BENCHMARK_LINE = re.compile(r'^Benchmark:\s*([^:]+):', re.IGNORECASE)

def parse_glibc_scalars(text: str):
    """
    Walk through the file line‑by‑line.
    Every time a line matches 'Benchmark: <name>:',
    collect the next three lines as floats and emit
    {'metric': <name>, 'value': <float>} dictionaries.

    Returns
    -------
    List[dict]
    """
    lines   = text.splitlines()          # keeps order and empty lines :contentReference[oaicite:0]{index=0}
    metrics = []
    i = 0

    while i < len(lines):
        m = _BENCHMARK_LINE.match(lines[i])   # anchor at current line :contentReference[oaicite:1]{index=1}
        if m:
            name = m.group(1).strip()
            # Read exactly the next three lines.
            for j in range(1, 4):
                if i + j >= len(lines):
                    break                    # premature EOF
                try:
                    value = float(lines[i + j].strip())
                except ValueError:
                    break                    # line wasn't numeric; abandon this block
                metrics.append({"metric": name, "value": value, "unit": "ns"})
            i += 4                            # skip header + 3 value lines
        else:
            i += 1                            # move to next line
    return metrics

# Threads / Copies: 4
# 0.0000
# 0.0000
# 0.0000
# 0.0000
_THREAD_COPIES_LINE = re.compile(r'^Threads / Copies:\s*([0-9]+)', re.IGNORECASE)

def parse_sqlite_scalars(text: str):
    print("Parsing SQLite scalars")
    lines  = text.splitlines()          # keeps order and empty lines :contentReference[oaicite:0]{index=0}
    metrics = []
    i = 0

    while i < len(lines):
        m = _THREAD_COPIES_LINE.match(lines[i])
        if m:
            name = "sqlite_ops"
            # Read exactly the next three lines.
            for j in range(1, 4):
                if i + j >= len(lines):
                    break                    # premature EOF
                try:
                    value = float(lines[i + j].strip())
                except ValueError:
                    break                    # line wasn't numeric; abandon this block
                metrics.append({"metric": name, "value": value, "unit": "s"})
            i += 4                            # skip header + 3 value lines
        else:
            i += 1                            # move to next line


    return metrics

def parse_lmbench_scalars(text: str):
    text = dedent(text)  # remove leading whitespace
    scalar_metrics = []              # list[dict]

    for raw in text.splitlines():
        line = raw.strip()
        # print(f"Parsing line: {line}")
        if not line:
            continue    

        # ----- scalar "name: number unit"
        new_metric = parse_scalar_metric(line)
        if new_metric is not None:
            scalar_metrics.append(new_metric)
            continue

    return scalar_metrics

# ╭────────────────────────────────────────────────────────────────╮
# │  STREAM‑STYLE (range) BENCHMARKS                              │
# ╰────────────────────────────────────────────────────────────────╯

# List of stream headers: mappings
'''
"File system latency


"mappings
"read bandwidth
"read open2close bandwidth
"Mmap read bandwidth

"Mmap read open2close bandwidth
"libc bcopy unaligned
"libc bcopy aligned
Memory bzero bandwidth
"unrolled bcopy unaligned
"unrolled partial bcopy unaligned
Memory read bandwidth
Memory partial read bandwidth
Memory write bandwidth
Memory partial write bandwidth
Memory partial read/write bandwidth

"size=Nk ovr=i (where N is an number, i is a float)

'''
# Stream title regexes for all supported stream-style benchmarks
stream_title_regexes: dict[str, str] = {
    # 2‑column bandwidth tables
    "mem_read_bw"          : r"^Memory read bandwidth$",
    "mem_write_bw"         : r"^Memory write bandwidth$",
    "mem_partial_rw_bw"    : r"^Memory partial read/write bandwidth$",
    "mem_partial_read_bw"  : r"^Memory partial read bandwidth$",
    "mem_partial_write_bw" : r"^Memory partial write bandwidth$",
    
    "mmap_read_bw"         : r'^"?Mmap read bandwidth"?$',
    "mmap_read_open_bw"    : r'^"?Mmap read open2close bandwidth"?$',
    "read_bw"              : r'^"?read bandwidth"?$',
    "read_open_bw"         : r'^"?read open2close bandwidth"?$',
    "libc_bcopy_unaligned" : r'^"?libc bcopy unaligned"?$',
    "libc_bcopy_aligned"   : r'^"?libc bcopy aligned"?$',
    "mem_bzero_bw"         : r'^"?Memory bzero bandwidth"?$',
    "unrolled_bcopy_unaligned" : r'^"?unrolled bcopy unaligned"?$',
    "unrolled_partial_bcopy_unaligned" : r'^"?unrolled partial bcopy unaligned"?$',
    
    # file system latency
    "fs_latency"           : r'^"?File system latency"?$',
    
    # mappings
    "mappings"             : r'^"?mappings"?$',
    
    # latency vs working‑set size tables (variable header)
    "size_latency"         : r'^"size=\d+k ovr=.*$',    # we'll normalise later
}


# stream_title_regexes: dict[str, str] = {
#     # 2‑column bandwidth tables
#     # "mem_read_bw"          : r"^Memory read bandwidth$",
#     # "mem_write_bw"         : r"^Memory write bandwidth$",
#     # "mem_partial_rw_bw"    : r"^Memory partial read/write bandwidth$",
#     "mem_partial_read_bw"  : r"^Memory partial read bandwidth$",
#     # "mem_partial_write_bw" : r"^Memory partial write bandwidth$",

#     # "mmap_read_bw"         : r'^"?Mmap read bandwidth"?$',
#     # "mmap_read_open_bw"    : r'^"?Mmap read open2close bandwidth"?$',
#     # "read_bw"              : r'^"?read bandwidth"?$',
#     # "read_open_bw"         : r'^"?read open2close bandwidth"?$',
#     # "libc_bcopy_unaligned" : r'^"?libc bcopy unaligned"?$',
#     # "libc_bcopy_aligned"   : r'^"?libc bcopy aligned"?$',
#     # "mem_bzero_bw"         : r'^"?Memory bzero bandwidth"?$',
#     # "unrolled_bcopy_unaligned"         : r'^"?unrolled bcopy unaligned"?$',
#     # "unrolled_partial_bcopy_unaligned" : r'^"?unrolled partial bcopy unaligned"?$',

#     # latency vs working‑set size tables (variable header)
#     "size_latency"         : r'^"size=\d+k ovr=.*$',    # we'll normalise later
# }

_stream_header_res = {k: re.compile(v, re.I) for k, v in stream_title_regexes.items()}


def _match_stream_header(line: str) -> tuple[str | None, str]:
    """
    If the line is a recognised stream header, return a canonical title key
    *and* the "pretty" title exactly as it appears (after stripping quotes).
    Otherwise (None, "").
    """
    clean = line.strip().strip('"')
    for key, cre in _stream_header_res.items():
        m = cre.match(clean)
        if m:
            if key == "size_latency":
                # include size value (e.g. size=0k) in the key so each block is unique
                size_part = clean.split()[0]           # "size=0k"
                return f"{key}_{size_part}", clean
            return key, clean
    return None, ""


def parse_lm_streams(text: str) -> dict[str, list[tuple[float, ...]]]:
    """
    Parse *range* sections of an lmbench run.

    Returns
    -------
    streams : dict
        { title_key : [ (x, y [, z …]), … ] }
    """
    streams: dict[str, list[tuple[float, ...]]] = {}
    current_key: str | None = None

    lines = dedent(text).splitlines()
    for raw in lines:
        line = raw.strip()
        if not line:
            current_key = None          # blank → terminate current block
            continue

        # print(f"Parsing line (current key={current_key}):", line)
        # 1) scalar line?  (skip so it never becomes a header candidate)
        if parse_scalar_metric(line):
            current_key = None
            continue

        # 2) header?
        key, pretty = _match_stream_header(line)
        if key:
            # print("Matched stream header:", key, pretty)
            current_key = key
            streams[current_key] = []
            continue

        # 3) numeric row?
        if current_key:
            # print("Paircheck:", line)
            m = _PAIR_RE.match(line)
            if m:
                tup = tuple(float(x) for x in m.groups() if x)
                # print("Matched pair:", tup)
                streams[current_key].append(tup)
                continue
            # if we reach here the current block is over
            current_key = None

    return streams



def print_key_figures(streams):
    print("\n=== Stream figures (2‑column tables) ===")
    for title, rows in streams.items():
        if not rows or len(rows[0]) != 2:
            continue
        xs, ys = zip(*rows)
        y_max = max(ys)
        x_at_max = xs[ys.index(y_max)]
        y_min = min(ys)
        x_at_min = xs[ys.index(y_min)]
        y_mean = statistics.mean(ys)
        print(f"{title:30s}  peak={y_max:,.2f} at {x_at_max} | "
              f"worst={y_min:,.2f} at {x_at_min} | mean={y_mean:,.2f}")


# # ----------------------------------------------------------------------
# # 1.  Build a tidy DataFrame
# # ----------------------------------------------------------------------
# def runs_to_dataframe(run_map: dict[str, list[dict]]) -> pd.DataFrame:
#     """
#     Parameters
#     ----------
#     run_map : dict
#         { run_name : [ {metric,value,unit}, ...] }

#     Returns
#     -------
#     pd.DataFrame
#         index = run_name
#         columns = metric names
#         values = float numbers (units are kept in .attrs['units'])
#     """
#     frames = []
#     units  = {}
#     for run_name, results in run_map.items():
#         row = {}
#         scalars = results[0]
#         for m in scalars:
#             # print("Analyzing metric:", m)
#             metric, value, unit = m["metric"], m["value"], m["unit"]
#             row[metric] = value
#             units.setdefault(metric, unit)
#         frames.append(pd.Series(row, name=run_name))
#     df = pd.DataFrame(frames)
#     df.attrs["units"] = units
#     return df

def runs_to_dataframes(merged_map: dict[str, list[dict]]):
    """
    Returns
    -------
    df_mean : pd.DataFrame (index = run, columns = metric, values = mean)
    df_std  : pd.DataFrame (same shape, values = stdev)
    """
    mean_rows, std_rows = [], []
    units = {}

    for run_name, scalars in merged_map.items():
        mean_row, std_row = {}, {}
        for m in scalars:
            mean_row[m["metric"]] = m["value"]
            std_row[m["metric"]]  = m["stdev"]
            units.setdefault(m["metric"], m["unit"])
        mean_rows.append(pd.Series(mean_row, name=run_name))
        std_rows.append(pd.Series(std_row,  name=run_name))

    df_mean = pd.DataFrame(mean_rows)
    df_std  = pd.DataFrame(std_rows)
    # keep unit information on the mean‑frame
    df_mean.attrs["units"] = units
    return df_mean, df_std

def merge_run_map(raw_run_map: dict[str, list[list[dict]]]):
    """
    Parameters
    ----------
    raw_run_map
        { run_name : [ scalar_metrics_iteration1, scalar_metrics_iteration2, … ] }
        where *scalar_metrics_iterationX* is the list produced by `parse_lmbench()`.

    Returns
    -------
    merged_map
        { run_name : [ {metric, value, stdev, sample_count, unit}, … ] }
        ready for the rest of the pipeline.
    """
    merged_map: dict[str, list[dict]] = {}
    # print("Raw run map: ", raw_run_map)
    for run_name, iterations in raw_run_map.items():
        # bucket: metric_name → [values]
        buckets: defaultdict[str, list[tuple[float, str]]] = defaultdict(list)

        for scalars in iterations:
            for m in scalars:
                # print("Analyzing metric:", m)
                buckets[m["metric"]].append((m["value"], m["unit"]))

        # reduce buckets → mean / stdev / n
        merged_rows = []
        for metric, vals in buckets.items():
            numbers, units = zip(*vals)
            # assert consistent units
            if len(set(units)) != 1:
                raise ValueError(f"Unit mismatch for '{metric}' in run '{run_name}'")
            n       = len(numbers)
            mean    = statistics.mean(numbers)
            stdev   = statistics.stdev(numbers) if n > 1 else 0.0
            merged_rows.append({
                "metric":        metric,
                "value":         mean,
                "stdev":         stdev,
                "sample_count":  n,
                "unit":          units[0],
            })

        merged_map[run_name] = merged_rows

    return merged_map


# ----------------------------------------------------------------------
# 2.  Simple descriptive statistics
# ----------------------------------------------------------------------
def describe_runs(df: pd.DataFrame, baseline: str | None = None) -> pd.DataFrame:
    """
    Returns a table with mean, std, min, max (per metric).
    If `baseline` is given (must be one of df.index),
    also adds %-difference vs that baseline for every other run.
    """
    stats = df.agg(["mean", "std", "min", "max"]).T
    if baseline and baseline in df.index:
        baseline_row = df.loc[baseline]
        pct_diff = ((df.subtract(baseline_row) / baseline_row) * 100)\
                     .rename(columns=lambda m: f"{m}_pct_from_{baseline}")
        stats = stats.join(pct_diff.T)   # one row per metric
    return stats


def _timestamp() -> str:
    """Return YYYYMMDD‑HHMMSS for unique filenames."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")

ANALYSIS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results-analysis")
FIG_DIR = os.path.join(ANALYSIS_DIR, "figs")


kconfig_short_names = {
    "no_sec_conf": "none",
    "retpoline": "retpoline",
    "page_table_isolation": "KPTI",
    "retbleed": "IBPB",
    "spectre_v2": "IBRS",
    "page_poisoning": "poison",
    "memory_leak_detector": "kmemleak",
    "kernel_address_sanitizer": "KASAN",
    "init_on_free_alloc": "init_free_alloc",
}
def plot_metric(df_mean, df_std, metric: str, dpi: int = 120):
    """Bar chart for one metric across runs (mean ± stdev)."""
    if metric not in df_mean.columns:
        raise ValueError(f"{metric!r} not found")

    # Create a copy with renamed index using the short names mapping
    df_plot = df_mean.copy()
    df_plot.index = [kconfig_short_names.get(run, run) for run in df_plot.index]
    
    # Also rename the index in df_std if we're using it for error bars
    if df_std is not None:
        df_std_plot = df_std.copy()
        df_std_plot.index = [kconfig_short_names.get(run, run) for run in df_std.index]
        errors = df_std_plot[metric] if metric in df_std_plot else None
    else:
        errors = None

    # Abbreviate units
    unit_abbrev = {
        "microseconds": "μs",
        "nanoseconds": "ns",
        "milliseconds": "ms",
        "seconds": "s",
        "KB/sec": "KB/s",
        "MB/sec": "MB/s",
        "GB/sec": "GB/s"
    }
    
    unit = df_mean.attrs['units'].get(metric, '')
    display_unit = unit_abbrev.get(unit, unit)

    fig, ax = plt.subplots(figsize=(6, 4), dpi=dpi)
    df_plot[metric].plot(kind="bar", yerr=errors, ax=ax, capsize=4)

    # Angle the bar names
    plt.xticks(rotation=45, ha='right')

    ax.set_ylabel(f"{metric} ({display_unit})")
    ax.set_title(f"{metric}: mean ± stdev")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()

    out = os.path.join(FIG_DIR, f"{metric}_bar.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[+] saved {os.path.basename(out)}")
    return fig, ax


def plot_all_metrics(df_mean, df_std, figsize=(12, 6), dpi: int = 120):
    """Clustered bar chart for every metric, with error bars."""
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    df_mean.T.plot(kind="bar", ax=ax, yerr=df_std.T, capsize=3)

    ax.set_xlabel("Metric")
    ax.set_ylabel("Value (units vary)")
    ax.set_title("lmbench scalar metrics – mean ± stdev")
    ax.legend(title="Run")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    out = os.path.join(FIG_DIR, f"all_metrics_bar.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[+] saved {os.path.basename(out)}")
    return fig, ax


# ---------------------------------------------------------------------
# 3. Normalised heat‑map
# ---------------------------------------------------------------------
def heatmap(df, cmap="viridis", figsize=(8, 6), dpi: int = 120):
    norm = (df - df.min()) / (df.max() - df.min())
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    im = ax.imshow(norm, aspect="auto", cmap=cmap)
    ax.set_xticks(np.arange(len(df.columns)), df.columns, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(df.index)), df.index)
    ax.set_title("Normalised scalar metrics (0 = best, 1 = worst)")
    fig.colorbar(im, ax=ax, shrink=0.8)
    plt.tight_layout()

    out = os.path.join(FIG_DIR, f"heatmap.png")
    fig.savefig(out)
    print(f"[+] saved {os.path.basename(out)}")
    plt.close(fig)
    return fig, ax

# ╭────────────────────────────────────────────────────────────────╮
# │  2.  QUICK  PLOT  –  2‑COLUMN STREAMS ONLY                     │
# ╰────────────────────────────────────────────────────────────────╯
import itertools
import matplotlib.pyplot as plt

def _run_color_map(runs):
    """Assign one distinct color per run (tab10 palette repeated if >10)."""
    base = plt.cm.get_cmap("tab10").colors
    return {run: base[i % len(base)] for i, run in enumerate(runs)}

# ╭─────────────────────────────────────────────────────────────╮
# │  PLOT  “MEAN ± STDEV”  FROM stream_stat DATAFRAMES          │
# ╰─────────────────────────────────────────────────────────────╯
import matplotlib.pyplot as plt
import itertools

def plot_stream_stat_scatter_avg(df_mean: pd.DataFrame,
                             df_std : pd.DataFrame | None,
                             stream_key: str,
                             dpi: int = 120,
                             figsize=(7, 5),
                             log_x: bool = True):
    """
    Parameters
    ----------
    df_mean , df_std  – output of build_stream_stat_dataframes()
                        (df_std can be None to omit error bars)
    stream_key        – canonical stream name (same key you passed earlier)
    log_x             – use log‑scale for the X axis (bandwidth tables)

    Produces a scatter chart:

        · one color per run (tab10 palette cycles if >10)
        · identical X grid for all runs (guaranteed by build_stream_stat_dataframes)
        · y‑error bars = stdev (if df_std is given)
    """
    # --- slice the frame -------------------------------------------------
    try:
        sub_mean = df_mean.xs(stream_key, level="stream")
    except KeyError:
        raise ValueError(f"No stats for stream '{stream_key}'")

    sub_std  = None
    if df_std is not None and stream_key in df_std.index.get_level_values("stream"):
        sub_std = df_std.xs(stream_key, level="stream")

    x_vals = sub_mean.columns.astype(float)
    runs   = sub_mean.index.tolist()

    # --- colour & marker helpers ----------------------------------------
    colors = plt.cm.get_cmap("tab10").colors
    color_map = {run: colors[i % len(colors)] for i, run in enumerate(runs)}
    markers = itertools.cycle(("o", "s", "^", "D", "v", "P", "X", "*"))

    # --- plotting --------------------------------------------------------
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    for run in runs:
        y = sub_mean.loc[run].values
        err = sub_std.loc[run].values if sub_std is not None else None
        ax.errorbar(
            x_vals, y,
            yerr=err,
            fmt=next(markers),
            color=color_map[run],
            label=run,
            markersize=5,
            linewidth=0,
            capsize=3,
            alpha=0.9,
        )

    if log_x:
        ax.set_xscale("log")

    ax.set_xlabel("Block / working‑set size")
    ax.set_ylabel("Value")
    ax.set_title(f"{stream_key} – mean ± stdev per run")
    ax.grid(True, which="both", ls="--", alpha=0.3)
    ax.legend(title="Run", fontsize="small")
    plt.tight_layout()

    out = os.path.join(FIG_DIR, f"{stream_key}_stat_scatter.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[+] saved {os.path.basename(out)}")
    return fig, ax



def plot_stream_scatter(df_long: pd.DataFrame, stream_key: str,
                        dpi: int = 120, figsize=(7, 5)):
    """
    Scatter‑plot all iterations of *stream_key* across runs.

    * Each **run** gets a unique color
    * Iterations of the same run share that color but cycle markers

    Only plots (x, y); ignores tables with >2 numeric columns.
    """
    subset = df_long[(df_long["stream"] == stream_key) & df_long["z"].isna()]
    if subset.empty:
        raise ValueError(f"No 2‑column data for stream '{stream_key}'")

    runs = sorted(subset["run"].unique())
    colors = _run_color_map(runs)
    markers = itertools.cycle(("o", "s", "^", "v", "D", "P", "*", "X"))

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    for run in runs:
        run_data = subset[subset["run"] == run]
        for iter_idx, grp in run_data.groupby("iteration"):
            marker = next(markers)
            ax.scatter(grp["x"], grp["y"],
                       label=f"{run} #{iter_idx}",
                       color=colors[run], marker=marker, s=35, alpha=0.8)

    ax.set_xscale("log")
    ax.set_xlabel("Block / working‑set size")
    ax.set_ylabel("Value")
    ax.set_title(f"{stream_key} – all iterations")
    ax.grid(True, which="both", ls="--", alpha=0.3)

    # Deduplicate legend entries (marker cycling can repeat)
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), fontsize="small")

    plt.tight_layout()
    out = os.path.join(FIG_DIR, f"{stream_key}_scatter.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"[+] saved {os.path.basename(out)}")
    return fig, ax


def build_full_dataframe(raw_run_map: dict[str, list[list[dict]]]) -> pd.DataFrame:
    """
    Returns a tidy/long pandas DataFrame with one row per observation:

        run       iteration   metric                   value    unit
        ------------------------------------------------------------------
        baseline  0           syscall                  0.0464   microseconds
        baseline  0           read                     0.0761   microseconds
        …
        hardened  1           syscall                  0.0522   microseconds
        …

    The DataFrame is perfectly suited for:
      • grouping (`df.groupby(["run","metric"]).agg(...)`)
      • seaborn “catplot” / boxplot / violin
      • CSV archival of *all* raw numbers
    """
    rows = []
    for run_name, iterations in raw_run_map.items():
        for iter_idx, scalars in enumerate(iterations):
            for m in scalars:
                rows.append(
                    {
                        "run":       run_name,
                        "iteration": iter_idx,
                        "metric":    m["metric"],
                        "value":     m["value"],
                        "unit":      m["unit"],
                    }
                )
    return pd.DataFrame(rows)

# ╭──────────────────────────────────────────────────────────────────╮
# │  4.  BUILD  “MEAN / STDEV”  TABLES  FOR  STREAM SECTIONS        │
# ╰──────────────────────────────────────────────────────────────────╯
def build_stream_stat_dataframes(df_long: pd.DataFrame):
    """
    Parameters
    ----------
    df_long   –  the tidy table from build_full_stream_dataframe()

    Returns
    -------
    df_mean , df_std   (two wide tables, like the scalar ones)

        · index  -> MultiIndex  (run, stream)
        · columns -> x  (the block / size)
        · values  -> mean or stdev across iterations
                      (NaN where a run‑stream is skipped)

    A run/stream is **kept** only if all iterations share the identical set of x.
    """
    mean_rows = []
    std_rows  = []
    index     = []

    for (run, stream), grp in df_long.groupby(["run", "stream"]):
        # ----- 1.  group by iteration → set of x
        x_sets = grp.groupby("iteration")["x"].apply(set)
        if len(x_sets) == 0:
            continue
        if not all(xs == x_sets.iloc[0] for xs in x_sets):
            # skip: iterations disagree on x grid
            print(f"Skipping {run}/{stream}: x sets differ across iterations")
            continue

        common_x = sorted(x_sets.iloc[0])
        index.append((run, stream))

        # ----- 2.  aggregate for every x across iterations
        means = grp.groupby("x")["y"].mean()
        stdev = grp.groupby("x")["y"].std(ddof=1).fillna(0.0)

        mean_rows.append(means.reindex(common_x))
        std_rows.append(stdev.reindex(common_x))

    if not index:
        raise ValueError("No run/stream pairs had identical x‑sets")

    # assemble into wide frames
    df_mean = pd.DataFrame(mean_rows, index=pd.MultiIndex.from_tuples(index))
    df_std  = pd.DataFrame(std_rows,  index=pd.MultiIndex.from_tuples(index))

    df_mean.index.names = ["run", "stream"]
    df_std.index.names  = ["run", "stream"]

    return df_mean, df_std



def dump_full_dataframe(df: pd.DataFrame, out_path: str = "all_runs_long.csv"):
    """
    Persist the long DataFrame to CSV (UTF‑8, comma‑sep).  If the target
    directory doesn’t exist it is created automatically.
    """
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"[+] full dataset → {out_path}")


# ────────────────── streams → one scalar value ──────────────────
def stream_to_scalar(stream_key: str,
                     xy_tuples: list[tuple[float, float | int]]) -> dict:
    """
    Reduce *one* 2‑column stream to a scalar metric.
    Current rule:  max(y)

    Returns a metric‑dict compatible with scalar pipeline:
        { "metric": f"{stream_key}_max",  "value": <float>,  "unit": "raw" }
    """
    if not xy_tuples:
        raise ValueError(f"Empty stream for {stream_key}")
    
    new_scalars = []
    for (x,y) in xy_tuples:
        if (x < 1 or x > 32):
            continue
        
        new_scalar = {
            "metric": f"{stream_key}_{x}",
            "value":  y,
            "unit":   "s",
        }

        new_scalars.append(new_scalar)
        
    return new_scalars


def streams_to_scalar_run_map(raw_stream_map: dict[str, list[dict]]) \
                               -> dict[str, list[list[dict]]]:
    """
    Convert the nested stream structure into the SAME nesting style used
    for scalars:

        { run : [ scalar_list_iter0, scalar_list_iter1, … ] }

    Each scalar‑list contains 1 dict per stream *of that iteration*.
    """
    out: dict[str, list[list[dict]]] = {}

    for run, iterations in raw_stream_map.items():
        iter_list = []
        for stream_dict in iterations:            # one iteration
            scalars_this_iter = []
            for skey, rows in stream_dict.items():
                # skip 3‑column tables
                if rows and len(rows[0]) != 2:
                    continue
                # Skip empty streams
                if not rows:
                    print(f"Skipping empty stream for {skey}")
                    continue

                print("Converting stream to scalar:", skey)
                print("Rows:", rows)
                scalars_this_iter.extend(stream_to_scalar(skey, rows))
            iter_list.append(scalars_this_iter)
        out[run] = iter_list
    return out


# ╭───────────────────────────────────────────────────────────────────╮
# │  1.  BUILD  A  “LONG”  DATAFRAME  FOR  STREAMS                   │
# │      raw_stream_map = { run : [ streams_iter0, streams_iter1…] } │
# │      streams_iter  = output of parse_lm_streams()                │
# ╰───────────────────────────────────────────────────────────────────╯

def build_full_stream_dataframe(raw_stream_map: dict[str, list[dict]]
                                ) -> pd.DataFrame:
    """
    Returns
    -------
    pd.DataFrame
        long / tidy table with columns

        run   iteration   stream           x        y        z
        ---------------------------------------------------------
        base  0           mem_read_bw      0.000512 32409.27  NaN
        base  0           mem_read_bw      0.001024 32490.55  NaN
        …
        hard  1           mem_read_bw      0.000512 31055.12  NaN
        …

    * If a row has more than two numeric columns (rare 3‑col tables),
      the third value is stored in **z**.
    * Columns **y** and **z** are floats; z may contain NaNs for 2‑col tables.
    """
    rows = []
    for run_name, iterations in raw_stream_map.items():
        for iter_idx, stream_dict in enumerate(iterations):
            for stream_key, tuples in stream_dict.items():
                for t in tuples:
                    # ensure length ≤ 3 (lmbench never has more than 3 in practice)
                    x = t[0]
                    y = t[1] if len(t) > 1 else float("nan")
                    z = t[2] if len(t) > 2 else float("nan")
                    rows.append(
                        {
                            "run":       run_name,
                            "iteration": iter_idx,
                            "stream":    stream_key,
                            "x":         x,
                            "y":         y,
                            "z":         z,
                        }
                    )
    return pd.DataFrame(rows)


def dump_full_stream_dataframe(df: pd.DataFrame,
                               out_path: str = "all_runs_streams_long.csv"):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"[+] full stream dataset → {out_path}")

def plot_all_scatters(df_long: pd.DataFrame, dpi: int = 120):
    streams = stream_title_regexes.keys()
    for stream_key in streams:
        try:
            plot_stream_scatter(df_long, stream_key, dpi=dpi)
        except ValueError as e:
            print(f"Failed to plot stream {stream_key}: {e}")
            continue

def plot_all_stream_stats(df_mean, df_std, dpi: int = 120):
    streams = stream_title_regexes.keys()
    for stream_key in streams:
        try:
            plot_stream_stat_scatter_avg(df_mean, df_std, stream_key, dpi=dpi)
        except ValueError as e:
            print(f"Failed to plot stream {stream_key}: {e}")
            continue

def analyze_streams_across_runs(raw_stream_map):
    """
    raw_run_map  = { run_name : [ stream_metrics_iter1, stream_metrics_iter2, … ] }
    """
    df = build_full_stream_dataframe(raw_stream_map)
    plot_all_stream_fits(df)

    outpath = os.path.join(ANALYSIS_DIR, "all_runs_streams_long.csv")
    dump_full_stream_dataframe(df, outpath)

    df_mean, df_std = build_stream_stat_dataframes(df)
    
    plot_all_stream_stats(df_mean, df_std)
    # plot_all_scatters(df)




def analyze_scalars_across_runs(raw_run_map):
    """
    raw_run_map  = { run_name : [ scalar_metrics_iter1, scalar_metrics_iter2, … ] }
    """
    df = build_full_dataframe(raw_run_map)
    outpath = os.path.join(ANALYSIS_DIR, "all_runs_long.csv")
    dump_full_dataframe(df, outpath)
    merged = merge_run_map(raw_run_map)
    df_mean, df_std = runs_to_dataframes(merged)

    # Rename the test configs kernel_address for clarity with kconfig_short_name
    

    print("\n=== Mean values ===")
    print(df_mean.round(4))
    print("\n=== Stdev ===")
    print(df_std.round(4))

    # per‑metric plots
    for metric in df_mean.columns:
        plot_metric(df_mean, df_std, metric)

    plot_all_metrics(df_mean, df_std)
    heatmap(df_mean)
