#!/usr/bin/env python3
"""Decompose the long/short asymmetry into path shape vs grid mathematics.

Each real price window is mirrored geometrically around its entry price
(p' = entry^2 / p), which turns every -x% move into an exactly +x% move while
preserving the path's timing and choppiness. Running a short grid on the
mirrored path is therefore the exact counterfactual of the long grid on the
real path. Any gap that remains is inherent to the grid's mathematics
(margin per unit, percentage compounding), not to the sample.
"""
import argparse
import os
import statistics as st

from grid_backtest import MS_DAY, auto_range, load_candles, run_grid, slice_range


def mirror(candles, entry):
    """Geometric mirror around entry: preserves timing, flips every % move."""
    k = entry * entry
    out = []
    for ts, o, h, l, c in candles:
        # high and low swap places under an inverting transform
        out.append((ts, k / o, k / l, k / h, k / c))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", required=True)
    ap.add_argument("--insts", default="BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP,DOGE-USDT-SWAP")
    ap.add_argument("--bar", default="15m")
    ap.add_argument("--window", type=int, default=30)
    ap.add_argument("--step", type=int, default=3)
    ap.add_argument("--lookback", type=int, default=30)
    ap.add_argument("--grids", type=int, default=50)
    ap.add_argument("--investment", type=float, default=10000)
    ap.add_argument("--fee", type=float, default=0.0002)
    args = ap.parse_args()

    pairs = []  # (bh, long_on_real, short_on_mirror, qty_ratio)
    for inst in args.insts.split(","):
        inst = inst.strip()
        candles = load_candles(os.path.join(args.datadir, f"{inst}_{args.bar}.csv"))
        start = candles[0][0] + args.lookback * MS_DAY
        last = candles[-1][0] - args.window * MS_DAY
        while start <= last:
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
            entry = win[0][1]
            # funding excluded on purpose: the mirrored path has no real funding
            rl = run_grid(win, [], "long", lo, hi, args.grids, args.investment,
                          1.0, args.fee, "arithmetic", inst)
            mwin = mirror(win, entry)
            mlo, mhi = entry * entry / hi, entry * entry / lo
            rs = run_grid(mwin, [], "short", mlo, mhi, args.grids, args.investment,
                          1.0, args.fee, "arithmetic", inst)
            pairs.append((rl.bh_ret_pct, rl.ret_pct, rs.ret_pct,
                          rl.qty_per_grid / rs.qty_per_grid * (entry / entry)))
            start += args.step * MS_DAY

    print(f"=== mirrored counterfactual, {len(pairs)} windows ===")
    print("long grid on the real path vs short grid on the exactly mirrored path")
    print()
    hdr = f"{'bucket':<16}{'n':>5}{'long(real)':>12}{'short(mirror)':>15}{'gap':>9}"
    print(hdr)
    print("-" * len(hdr))
    groups = [
        ("selloff <-15%", lambda b: b < -15),
        ("selloff -15..-5%", lambda b: -15 <= b < -5),
        ("range -5..5%", lambda b: -5 <= b <= 5),
        ("rally 5..15%", lambda b: 5 < b <= 15),
        ("rally >15%", lambda b: b > 15),
        ("ALL", lambda b: True),
    ]
    for label, f in groups:
        g = [p for p in pairs if f(p[0])]
        if not g:
            continue
        a = st.mean([p[1] for p in g])
        b = st.mean([p[2] for p in g])
        print(f"{label:<16}{len(g):>5}{a:>12.2f}{b:>15.2f}{a - b:>9.2f}")
    print()
    print("If the two columns match, the long/short gap seen on real data is purely")
    print("the shape of real price paths (drops are faster than rallies). A residual")
    print("gap is the grid's own mathematics.")
    print()
    qr = [p[3] for p in pairs]
    print(f"qty per grid, long / short (same margin): mean {st.mean(qr):.3f}x")


if __name__ == "__main__":
    main()
