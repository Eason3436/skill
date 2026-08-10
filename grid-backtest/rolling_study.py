#!/usr/bin/env python3
"""Rolling-window study: long vs short vs neutral grid over many start dates.

Each window sets its grid range from the trailing lookback period *before* the
window starts, so no future information leaks into the parameters. Windows are
then bucketed by what the market actually did (buy & hold return) so the
direction-vs-regime relationship is visible instead of averaged away.
"""
import argparse
import csv
import json
import os
import statistics as st

from grid_backtest import MS_DAY, auto_range, load_candles, load_funding, run_grid, slice_range

MODES = ("long", "short", "neutral")


def pct(xs):
    return {
        "n": len(xs),
        "mean": st.mean(xs) if xs else 0.0,
        "median": st.median(xs) if xs else 0.0,
        "p10": sorted(xs)[max(0, int(0.10 * len(xs)) - 1)] if xs else 0.0,
        "p90": sorted(xs)[min(len(xs) - 1, int(0.90 * len(xs)))] if xs else 0.0,
        "min": min(xs) if xs else 0.0,
        "max": max(xs) if xs else 0.0,
        "win": 100.0 * sum(1 for x in xs if x > 0) / len(xs) if xs else 0.0,
    }


def regime(bh):
    if bh > 5:
        return "up"
    if bh < -5:
        return "down"
    return "range"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", required=True)
    ap.add_argument("--insts", default="BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP,DOGE-USDT-SWAP")
    ap.add_argument("--bar", default="15m")
    ap.add_argument("--window", type=int, default=30, help="test window length in days")
    ap.add_argument("--step", type=int, default=3, help="days between window starts")
    ap.add_argument("--lookback", type=int, default=30)
    ap.add_argument("--grids", type=int, default=50)
    ap.add_argument("--investment", type=float, default=10000)
    ap.add_argument("--leverage", type=float, default=1.0)
    ap.add_argument("--fee", type=float, default=0.0002)
    ap.add_argument("--spacing", default="arithmetic")
    ap.add_argument("--no-funding", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    samples = []
    for inst in args.insts.split(","):
        inst = inst.strip()
        candles = load_candles(os.path.join(args.datadir, f"{inst}_{args.bar}.csv"))
        funding = [] if args.no_funding else load_funding(
            os.path.join(args.datadir, f"{inst}_funding.csv")
        )
        t0, t1 = candles[0][0], candles[-1][0]
        first_start = t0 + args.lookback * MS_DAY
        last_start = t1 - args.window * MS_DAY
        start = first_start
        while start <= last_start:
            end = start + args.window * MS_DAY
            win = slice_range(candles, start, end)
            if len(win) < 10:
                start += args.step * MS_DAY
                continue
            try:
                lo, hi = auto_range(candles, start, args.lookback)
            except ValueError:
                start += args.step * MS_DAY
                continue
            fw = [f for f in funding if start <= f[0] < end]
            row = {"inst": inst, "start_ms": start}
            ok = True
            for m in MODES:
                try:
                    r = run_grid(
                        win, fw, m, lo, hi, args.grids, args.investment,
                        args.leverage, args.fee, args.spacing, inst,
                    )
                except ValueError:
                    ok = False
                    break
                row[m] = {
                    "ret": r.ret_pct,
                    "grid": r.grid_ret_pct,
                    "float": r.float_pnl / r.investment * 100,
                    "fee": -r.fees / r.investment * 100,
                    "fund": r.funding / r.investment * 100,
                    "dd": r.max_dd_pct,
                    "fills": r.trades,
                    "in_range": r.time_in_range_pct,
                }
                row["bh"] = r.bh_ret_pct
                row["date"] = r.start
                row["has_funding"] = len(fw) > 0
            if ok:
                samples.append(row)
            start += args.step * MS_DAY

    with open(args.out, "w") as fh:
        json.dump({"params": vars(args), "samples": samples}, fh)

    # ---------------- summary ----------------
    print(f"windows: {len(samples)}  ({args.window}d test / {args.lookback}d range lookback)")
    print()
    hdr = f"{'bucket':<22}{'mode':<9}{'mean%':>8}{'med%':>8}{'win%':>7}{'p10%':>8}{'p90%':>8}{'grid%':>8}{'float%':>8}{'fee%':>7}{'fund%':>7}{'DD%':>7}"
    print(hdr)
    print("-" * len(hdr))

    def block(label, rows):
        for m in MODES:
            s = pct([r[m]["ret"] for r in rows])
            g = st.mean([r[m]["grid"] for r in rows]) if rows else 0
            fl = st.mean([r[m]["float"] for r in rows]) if rows else 0
            fe = st.mean([r[m]["fee"] for r in rows]) if rows else 0
            fu = st.mean([r[m]["fund"] for r in rows]) if rows else 0
            dd = st.mean([r[m]["dd"] for r in rows]) if rows else 0
            print(
                f"{label + ' n=' + str(len(rows)):<22}{m:<9}{s['mean']:>8.2f}{s['median']:>8.2f}"
                f"{s['win']:>7.0f}{s['p10']:>8.2f}{s['p90']:>8.2f}{g:>8.2f}{fl:>8.2f}"
                f"{fe:>7.2f}{fu:>7.2f}{dd:>7.2f}"
            )
        print()

    block("ALL", samples)
    for reg in ("up", "range", "down"):
        rows = [r for r in samples if regime(r["bh"]) == reg]
        if rows:
            block(f"market {reg}", rows)
    for inst in args.insts.split(","):
        rows = [r for r in samples if r["inst"] == inst.strip()]
        if rows:
            block(inst.strip().replace("-USDT-SWAP", ""), rows)


if __name__ == "__main__":
    main()
