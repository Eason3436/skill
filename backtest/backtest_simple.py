#!/usr/bin/env python3
"""
Simple single-entry / single-exit Bollinger mean-reversion backtest.

STRATEGY
--------
Bollinger Bands: mid = SMA(close, LENGTH), sigma = population stdev(close, LENGTH).
  - ENTRY: buy the FULL position when candle LOW reaches  mid - ENTRY_SIGMA*sigma.
  - EXIT : sell the FULL position when candle HIGH reaches mid + EXIT_SIGMA*sigma.
Fills at the band price (resting limit orders). A cycle ends on exit; re-entry allowed.

Defaults: ENTRY_SIGMA = 2.5, EXIT tested at {2.5, 2.0}. Timeframes: 8H (2x4H) and 12H.

Reports per timeframe x exit-sigma, aggregated over all cached tokens:
  trades, how many reached exit vs still open, win-rate, ROI stats,
  honest ROI including open positions marked to last close, avg bars held.
"""
import json
import os
import statistics as st
from backtest import load_bars, build_8h_from_4h, bollinger, LENGTH, SCRATCH

ENTRY_SIGMA = float(os.environ.get("ENTRY_SIGMA", "2.5"))
EXIT_SIGMAS = [float(x) for x in os.environ.get("EXIT_SIGMAS", "2.5,2.0").split(",")]


def tokens_from_cache():
    return sorted({fn[:-8] for fn in os.listdir(SCRATCH) if fn.endswith("_4H.json")})


def series_for(tok):
    return {"8H": build_8h_from_4h(load_bars(tok, "4H")), "12H": load_bars(tok, "12H")}


def simulate(bars, length, entry_sig, exit_sig):
    mid, sd = bollinger(bars, length)
    trades = []
    in_pos = False
    entry_px = 0.0
    entry_i = 0
    for i in range(length - 1, len(bars)):
        m, s = mid[i], sd[i]
        if m is None:
            continue
        _, o, hi, lo, c = bars[i]
        if not in_pos:
            lb = m - entry_sig * s
            if lo <= lb:
                in_pos = True
                entry_px = lb
                entry_i = i
        else:
            ub = m + exit_sig * s
            if hi >= ub:
                trades.append({"entry": entry_px, "exit": ub, "bars": i - entry_i,
                               "roi": (ub - entry_px) / entry_px, "resolved": True})
                in_pos = False
    if in_pos:
        last_close = bars[-1][4]
        trades.append({"entry": entry_px, "exit": last_close, "bars": len(bars) - 1 - entry_i,
                       "roi": (last_close - entry_px) / entry_px, "resolved": False})
    return trades


def main():
    toks = tokens_from_cache()
    print(f"單進單出布林回測 | BB length={LENGTH} | 進場 -{ENTRY_SIGMA}σ | 出場測 {EXIT_SIGMAS}σ\n"
          f"樣本代幣: {len(toks)} | 進出場皆以軌價成交 (進看最低價 / 出看最高價)\n" + "=" * 74)
    dump = {}
    for tf in ["8H", "12H"]:
        for xs in EXIT_SIGMAS:
            R = res = []  # noqa
            resolved, opened = [], []
            held = []
            toks_used = 0
            for tok in toks:
                bars = series_for(tok)[tf]
                if len(bars) < LENGTH + 5:
                    continue
                trs = simulate(bars, LENGTH, ENTRY_SIGMA, xs)
                if trs:
                    toks_used += 1
                for t in trs:
                    if t["resolved"]:
                        resolved.append(t["roi"])
                        held.append(t["bars"])
                    else:
                        opened.append(t["roi"])
            n_total = len(resolved) + len(opened)
            if n_total == 0:
                continue
            wins = [r for r in resolved if r > 0]
            allc = resolved + opened
            nr = len(resolved)
            print(f"\n### {tf}  |  進 -{ENTRY_SIGMA}σ  →  出 +{xs}σ")
            print(f"  進場觸發(總交易)     : {n_total}   代幣數 {toks_used}")
            print(f"  已到出場(平倉)       : {nr}  ({100*nr/n_total:.1f}%)")
            print(f"  仍未到出場(套牢)     : {len(opened)}  ({100*len(opened)/n_total:.1f}%)")
            if nr:
                lo = [r for r in resolved if r <= 0]
                print(f"  平倉勝率             : {100*len(wins)/nr:.1f}%")
                print(f"  平倉平均 ROI         : {100*st.mean(resolved):+.2f}%   中位數 {100*st.median(resolved):+.2f}%")
                print(f"  平均獲利 / 平均虧損  : {100*st.mean(wins) if wins else 0:+.2f}% / {100*st.mean(lo) if lo else 0:+.2f}%")
                print(f"  最佳 / 最差平倉      : {100*max(resolved):+.1f}% / {100*min(resolved):+.1f}%")
                print(f"  平均持有K棒 / 天     : {st.mean(held):.0f} 根 / {st.mean(held)*(8 if tf=='8H' else 12)/24:.1f} 天")
            if opened:
                print(f"  套牢部位平均未實現   : {100*st.mean(opened):+.2f}%")
            print(f"  ★ 含套牢的誠實平均ROI: {100*st.mean(allc):+.2f}% / 交易")
            dump[f"{tf}|{xs}"] = {
                "entry_sigma": ENTRY_SIGMA, "exit_sigma": xs, "tokens": toks_used,
                "trades": n_total, "resolved": nr, "open": len(opened),
                "reach_exit_pct": 100*nr/n_total,
                "win_rate": 100*len(wins)/nr if nr else 0,
                "avg_roi": 100*st.mean(resolved) if nr else 0,
                "median_roi": 100*st.median(resolved) if nr else 0,
                "avg_win": 100*st.mean(wins) if wins else 0,
                "avg_loss": 100*st.mean([r for r in resolved if r <= 0]) if [r for r in resolved if r <= 0] else 0,
                "best": 100*max(resolved) if nr else 0, "worst": 100*min(resolved) if nr else 0,
                "avg_held_bars": st.mean(held) if held else 0,
                "open_avg": 100*st.mean(opened) if opened else 0,
                "honest_roi": 100*st.mean(allc),
            }
    with open(os.path.join(os.path.dirname(__file__), "results_simple.json"), "w") as f:
        json.dump(dump, f, indent=2)
    print("\n(results_simple.json written)")


if __name__ == "__main__":
    main()
