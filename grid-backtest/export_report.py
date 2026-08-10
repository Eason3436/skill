#!/usr/bin/env python3
"""Export the numbers the HTML report renders (scatter, regimes, equity curves)."""
import argparse
import json
import os
import statistics as st

from grid_backtest import MS_DAY, auto_range, load_candles, load_funding, run_grid, slice_range

MODES = ("long", "short", "neutral")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", required=True)
    ap.add_argument("--rolling", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--curve-inst", default="BTC-USDT-SWAP")
    ap.add_argument("--curve-days", type=int, default=180)
    args = ap.parse_args()

    roll = json.load(open(args.rolling))
    s = roll["samples"]

    scatter = [
        {
            "bh": round(r["bh"], 3),
            "l": round(r["long"]["ret"], 3),
            "s": round(r["short"]["ret"], 3),
            "n": round(r["neutral"]["ret"], 3),
            "inst": r["inst"].replace("-USDT-SWAP", ""),
        }
        for r in s
    ]

    def bucket(f):
        rows = [r for r in s if f(r["bh"])]
        return {
            m: {
                "ret": round(st.mean([r[m]["ret"] for r in rows]), 2),
                "grid": round(st.mean([r[m]["grid"] for r in rows]), 2),
                "float": round(st.mean([r[m]["float"] for r in rows]), 2),
                "dd": round(st.mean([r[m]["dd"] for r in rows]), 2),
                "win": round(100 * sum(1 for r in rows if r[m]["ret"] > 0) / len(rows), 0),
            }
            for m in MODES
        } | {"n": len(rows), "bh": round(st.mean([r["bh"] for r in rows]), 2)}

    regimes = {
        "up": bucket(lambda b: b > 5),
        "range": bucket(lambda b: -5 <= b <= 5),
        "down": bucket(lambda b: b < -5),
        "all": bucket(lambda b: True),
    }

    # equity curves for one instrument, all three modes, same grid
    candles = load_candles(os.path.join(args.datadir, f"{args.curve_inst}_15m.csv"))
    funding = load_funding(os.path.join(args.datadir, f"{args.curve_inst}_funding.csv"))
    end = candles[-1][0] + 1
    start = end - args.curve_days * MS_DAY
    lo, hi = auto_range(candles, start, 30)
    win = slice_range(candles, start, end)
    fw = [f for f in funding if start <= f[0] < end]
    curves, meta = {}, {}
    for m in MODES:
        r = run_grid(win, fw, m, lo, hi, 50, 10000, 1.0, 0.0002, "arithmetic", args.curve_inst)
        step = max(1, len(r.equity) // 400)
        curves[m] = [round(e / 10000 * 100 - 100, 3) for _, e in r.equity[::step]]
        meta[m] = {"ret": round(r.ret_pct, 2), "dd": round(r.max_dd_pct, 2),
                   "grid": round(r.grid_ret_pct, 2), "fills": r.trades}
    px = [round(c[4], 2) for c in win[:: max(1, len(win) // 400)]]
    ts = [c[0] for c in win[:: max(1, len(win) // 400)]]

    json.dump(
        {
            "scatter": scatter,
            "regimes": regimes,
            "curve": {
                "inst": args.curve_inst, "days": args.curve_days,
                "lower": round(lo, 2), "upper": round(hi, 2),
                "ts": ts, "px": px, "curves": curves, "meta": meta,
            },
        },
        open(args.out, "w"),
    )
    print("wrote", args.out)


if __name__ == "__main__":
    main()
