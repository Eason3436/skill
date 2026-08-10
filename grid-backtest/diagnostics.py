#!/usr/bin/env python3
"""Regime diagnostics + robustness sweeps on top of the rolling study."""
import argparse
import json
import statistics as st
import subprocess
import sys

MODES = ("long", "short", "neutral")


def regime(bh):
    return "up" if bh > 5 else ("down" if bh < -5 else "range")


def sample_shape(path):
    d = json.load(open(path))
    s = d["samples"]
    print(f"=== sample shape: {len(s)} windows, {d['params']['window']}d each ===")
    for reg in ("up", "range", "down"):
        rows = [r for r in s if regime(r["bh"]) == reg]
        bh = [r["bh"] for r in rows]
        print(
            f"{reg:<6} n={len(rows):<4} buy&hold mean {st.mean(bh):+7.2f}%  "
            f"median {st.median(bh):+7.2f}%  extreme {min(bh):+7.2f}/{max(bh):+7.2f}"
        )
    all_bh = [r["bh"] for r in s]
    print(f"all    n={len(s):<4} buy&hold mean {st.mean(all_bh):+7.2f}%  median {st.median(all_bh):+7.2f}%")
    print()

    # Is the grid engine itself direction-neutral? Compare realised grid profit only.
    print("=== grid profit only (the market-making component, excludes float PnL) ===")
    for reg in ("up", "range", "down", "all"):
        rows = s if reg == "all" else [r for r in s if regime(r["bh"]) == reg]
        line = f"{reg:<6} n={len(rows):<4}"
        for m in MODES:
            line += f"  {m}={st.mean([r[m]['grid'] for r in rows]):+6.2f}%"
        print(line)
    print()

    # Adverse-move efficiency: loss suffered per 1% of adverse price move.
    print("=== loss per 1% adverse move (long in down markets vs short in up markets) ===")
    dn = [r for r in s if regime(r["bh"]) == "down"]
    up = [r for r in s if regime(r["bh"]) == "up"]
    lr = [r["long"]["ret"] / abs(r["bh"]) for r in dn if abs(r["bh"]) > 1e-9]
    sr = [r["short"]["ret"] / abs(r["bh"]) for r in up if abs(r["bh"]) > 1e-9]
    print(f"long grid,  market down: {st.mean(lr):+6.3f}% return per 1% drop   (n={len(lr)})")
    print(f"short grid, market up:   {st.mean(sr):+6.3f}% return per 1% rally  (n={len(sr)})")
    print()

    # Funding: only windows fully covered by OKX's funding history are meaningful.
    fund = [r for r in s if r.get("has_funding")]
    print(f"=== funding (windows with OKX funding history: {len(fund)}/{len(s)}) ===")
    for m in MODES:
        v = [r[m]["fund"] for r in fund]
        print(f"{m:<8} mean {st.mean(v):+6.3f}%  median {st.median(v):+6.3f}%  range {min(v):+.2f}/{max(v):+.2f}")
    print()


def sweep(datadir, base_args, variations, out_prefix):
    print("=== robustness sweep (mean 30d return, all windows) ===")
    hdr = f"{'variant':<34}{'long':>9}{'short':>9}{'neutral':>9}{'L grid%':>10}{'S grid%':>10}{'n':>6}"
    print(hdr)
    print("-" * len(hdr))
    for label, extra in variations:
        out = f"{out_prefix}_{label.replace(' ', '_').replace('/', '-')}.json"
        cmd = [sys.executable, "rolling_study.py", "--datadir", datadir, "--out", out] + base_args + extra
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"{label:<34} FAILED: {res.stderr.strip().splitlines()[-1][:60]}")
            continue
        s = json.load(open(out))["samples"]
        row = f"{label:<34}"
        for m in MODES:
            row += f"{st.mean([r[m]['ret'] for r in s]):>9.2f}"
        row += f"{st.mean([r['long']['grid'] for r in s]):>10.2f}"
        row += f"{st.mean([r['short']['grid'] for r in s]):>10.2f}"
        row += f"{len(s):>6}"
        print(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", required=True)
    ap.add_argument("--rolling", required=True)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--skip-sweep", action="store_true")
    args = ap.parse_args()

    sample_shape(args.rolling)
    if args.skip_sweep:
        return

    base = ["--window", "30", "--step", "3", "--lookback", "30"]
    variations = [
        ("baseline 15m/50 grids/1x", ["--bar", "15m", "--grids", "50"]),
        ("1H candles", ["--bar", "1H", "--grids", "50"]),
        ("5m candles (BTC,SOL only)", ["--bar", "5m", "--grids", "50",
                                       "--insts", "BTC-USDT-SWAP,SOL-USDT-SWAP"]),
        ("15m BTC,SOL only (5m control)", ["--bar", "15m", "--grids", "50",
                                           "--insts", "BTC-USDT-SWAP,SOL-USDT-SWAP"]),
        ("20 grids", ["--bar", "15m", "--grids", "20"]),
        ("100 grids", ["--bar", "15m", "--grids", "100"]),
        ("geometric spacing", ["--bar", "15m", "--grids", "50", "--spacing", "geometric"]),
        ("taker fee 0.05%", ["--bar", "15m", "--grids", "50", "--fee", "0.0005"]),
        ("zero fee", ["--bar", "15m", "--grids", "50", "--fee", "0"]),
        ("2x leverage", ["--bar", "15m", "--grids", "50", "--leverage", "2"]),
        ("no funding", ["--bar", "15m", "--grids", "50", "--no-funding"]),
        ("60d window", ["--bar", "15m", "--grids", "50", "--window", "60"]),
        ("14d window", ["--bar", "15m", "--grids", "50", "--window", "14"]),
        ("60d range lookback", ["--bar", "15m", "--grids", "50", "--lookback", "60"]),
    ]
    sweep(args.datadir, base, variations, f"{args.scratch}/sweep")


if __name__ == "__main__":
    main()
