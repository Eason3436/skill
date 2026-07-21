#!/usr/bin/env python3
"""Proper return analysis: ROI on deployed capital, incl. open-position drawdown."""
import os
import statistics as st
from backtest import (load_bars, build_8h_from_4h, simulate, LENGTH, SCRATCH,
                      PARTIAL_VARIANTS)

W = {1: 0.30, 2: 0.60, 3: 1.00}  # deployed fraction of intended full position


def tokens_from_cache():
    seen = set()
    for fn in os.listdir(SCRATCH):
        if fn.endswith("_4H.json"):
            seen.add(fn[:-len("_4H.json")])
    return sorted(seen)


def series_for(tok):
    return {"8H": build_8h_from_4h(load_bars(tok, "4H")), "12H": load_bars(tok, "12H")}


def analyze():
    import json
    dump = {}
    toks = tokens_from_cache()
    print(f"BB length={LENGTH}  |  ROI = (賣出-買入)/買入 on capital actually deployed that cycle\n")
    for tf in ["8H", "12H"]:
        for var in PARTIAL_VARIANTS:
            realized = []          # roi% on deployed capital, resolved cycles
            realized_full = []     # roi% scaled to 100%-reserved capital
            deployed_frac = []
            open_roi = []          # unrealized roi% on deployed capital
            open_full = []
            by_depth = {1: [], 2: [], 3: []}
            for tok in toks:
                bars = series_for(tok)[tf]
                if len(bars) < LENGTH + 5:
                    continue
                last_close = bars[-1][4]
                for cy in simulate(bars, LENGTH, var):
                    bc = cy["buy_cost"]
                    if bc <= 0:
                        continue
                    frac = cy["filled_weight"]  # 0.3 / 0.6 / 1.0
                    if cy["resolved"]:
                        roi = (cy["proceeds"] - bc) / bc
                        realized.append(roi)
                        realized_full.append(roi * frac)      # weight by capital deployed
                        deployed_frac.append(frac)
                        by_depth[cy["max_level"]].append(roi)
                    else:
                        mark = frac * last_close
                        roi = (mark - bc) / bc
                        open_roi.append(roi)
                        open_full.append(roi * frac)
            n = len(realized)
            if n == 0:
                continue
            wins = [r for r in realized if r > 0]
            losses = [r for r in realized if r <= 0]
            allc = realized + open_roi          # honest: resolved + still-open
            allc_full = realized_full + open_full
            print(f"### {tf}  |  部分倉出場 +{var}σ")
            print(f"  已平倉週期            : {n}")
            print(f"  平均 ROI(投入資金)    : {100*st.mean(realized):+.2f}%   中位數 {100*st.median(realized):+.2f}%")
            print(f"  勝率                  : {100*len(wins)/n:.1f}%   平均獲利 {100*st.mean(wins):+.2f}%   平均虧損 {100*st.mean(losses) if losses else 0:+.2f}%")
            print(f"  最佳 / 最差           : {100*max(realized):+.1f}% / {100*min(realized):+.1f}%")
            print(f"  平均動用倉位          : {100*st.mean(deployed_frac):.0f}% (of intended full)")
            print(f"  平均 ROI(以滿倉本金計): {100*st.mean(realized_full):+.2f}% / 週期")
            for d, lab in [(1, "止步30%"), (2, "止步60%"), (3, "滿倉100%")]:
                arr = by_depth[d]
                if arr:
                    wr = 100*len([x for x in arr if x > 0])/len(arr)
                    print(f"    └ {lab:8}: {len(arr):3d} 筆  平均ROI {100*st.mean(arr):+6.2f}%  勝率 {wr:4.0f}%")
            print(f"  未平倉(套牢)週期      : {len(open_roi)}   平均未實現 {100*st.mean(open_roi) if open_roi else 0:+.2f}%")
            print(f"  ★ 含未平倉的誠實平均  : {100*st.mean(allc):+.2f}% / 週期(投入資金)  |  "
                  f"{100*st.mean(allc_full):+.2f}% / 週期(滿倉本金)")
            print()
            dump[f"{tf}|{var}"] = {
                "resolved": n,
                "avg_roi": 100*st.mean(realized),
                "median_roi": 100*st.median(realized),
                "win_rate": 100*len(wins)/n,
                "avg_win": 100*st.mean(wins),
                "avg_loss": 100*st.mean(losses) if losses else 0,
                "best": 100*max(realized), "worst": 100*min(realized),
                "avg_deployed": 100*st.mean(deployed_frac),
                "avg_roi_full": 100*st.mean(realized_full),
                "depth": {d: (len(by_depth[d]), 100*st.mean(by_depth[d]) if by_depth[d] else 0,
                              100*len([x for x in by_depth[d] if x > 0])/len(by_depth[d]) if by_depth[d] else 0)
                          for d in (1, 2, 3)},
                "open_n": len(open_roi),
                "open_avg": 100*st.mean(open_roi) if open_roi else 0,
                "honest_deployed": 100*st.mean(allc),
                "honest_full": 100*st.mean(allc_full),
            }
    with open(os.path.join(os.path.dirname(__file__), "returns.json"), "w") as f:
        json.dump(dump, f, indent=2)
    print("(returns.json written)")


if __name__ == "__main__":
    analyze()
