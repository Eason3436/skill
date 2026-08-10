#!/usr/bin/env python3
"""Run every analysis once and emit a single JSON the HTML report embeds."""
import argparse
import json
import os
import statistics as st

from grid_backtest import MS_DAY, auto_range, load_candles, load_funding, run_grid, slice_range
from mirror_test import mirror

MODES = ("long", "short", "neutral")
INSTS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "DOGE-USDT-SWAP"]


def load(datadir, inst, bar):
    return (
        load_candles(os.path.join(datadir, f"{inst}_{bar}.csv")),
        load_funding(os.path.join(datadir, f"{inst}_funding.csv")),
    )


def headline(datadir, days, bar="15m", grids=50, lookback=30):
    out = []
    for inst in INSTS:
        candles, funding = load(datadir, inst, bar)
        end = candles[-1][0] + 1
        start = end - days * MS_DAY
        lo, hi = auto_range(candles, start, lookback)
        win = slice_range(candles, start, end)
        fw = [f for f in funding if start <= f[0] < end]
        row = {"inst": inst.replace("-USDT-SWAP", ""), "lower": lo, "upper": hi}
        for m in MODES:
            r = run_grid(win, fw, m, lo, hi, grids, 10000, 1.0, 0.0002, "arithmetic", inst)
            row[m] = {
                "ret": round(r.ret_pct, 2), "apr": round(r.apr_pct, 1),
                "grid": round(r.grid_ret_pct, 2),
                "float": round(r.float_pnl / r.investment * 100, 2),
                "fee": round(-r.fees / r.investment * 100, 2),
                "fund": round(r.funding / r.investment * 100, 2),
                "dd": round(r.max_dd_pct, 2), "fills": r.trades,
            }
            row["bh"] = round(r.bh_ret_pct, 2)
            row["in_range"] = round(r.time_in_range_pct, 1)
            row["start"], row["end"] = r.start, r.end
        out.append(row)
    return out


def rolling(datadir, bar="15m", window=30, step=3, lookback=30, grids=50,
            leverage=1.0, fee=0.0002, spacing="arithmetic", insts=None, funding_on=True):
    samples = []
    for inst in (insts or INSTS):
        candles, funding = load(datadir, inst, bar)
        if not funding_on:
            funding = []
        start = candles[0][0] + lookback * MS_DAY
        last = candles[-1][0] - window * MS_DAY
        while start <= last:
            end = start + window * MS_DAY
            win = slice_range(candles, start, end)
            if len(win) < 10:
                start += step * MS_DAY
                continue
            try:
                lo, hi = auto_range(candles, start, lookback)
            except ValueError:
                start += step * MS_DAY
                continue
            fw = [f for f in funding if start <= f[0] < end]
            row = {"inst": inst.replace("-USDT-SWAP", ""), "has_funding": bool(fw)}
            for m in MODES:
                r = run_grid(win, fw, m, lo, hi, grids, 10000, leverage, fee, spacing, inst)
                row[m] = {
                    "ret": round(r.ret_pct, 3), "grid": round(r.grid_ret_pct, 3),
                    "float": round(r.float_pnl / r.investment * 100, 3),
                    "fund": round(r.funding / r.investment * 100, 4),
                    "dd": round(r.max_dd_pct, 2), "fills": r.trades,
                    "in_range": round(r.time_in_range_pct, 1),
                }
                row["bh"] = round(r.bh_ret_pct, 3)
            samples.append(row)
            start += step * MS_DAY
    return samples


def agg(rows, key="ret"):
    o = {}
    for m in MODES:
        v = [r[m][key] for r in rows]
        o[m] = {
            "mean": round(st.mean(v), 2), "median": round(st.median(v), 2),
            "win": round(100 * sum(1 for x in v if x > 0) / len(v)),
            "p10": round(sorted(v)[max(0, int(0.1 * len(v)) - 1)], 2),
            "p90": round(sorted(v)[min(len(v) - 1, int(0.9 * len(v)))], 2),
            "grid": round(st.mean([r[m]["grid"] for r in rows]), 2),
            "float": round(st.mean([r[m]["float"] for r in rows]), 2),
            "fund": round(st.mean([r[m]["fund"] for r in rows]), 3),
            "dd": round(st.mean([r[m]["dd"] for r in rows]), 2),
            "fills": round(st.mean([r[m]["fills"] for r in rows])),
            "in_range": round(st.mean([r[m]["in_range"] for r in rows]), 1),
        }
    o["n"] = len(rows)
    o["bh"] = round(st.mean([r["bh"] for r in rows]), 2)
    return o


def mirror_study(datadir, bar="15m", window=30, step=3, lookback=30, grids=50):
    pairs = []
    for inst in INSTS:
        candles, _ = load(datadir, inst, bar)
        start = candles[0][0] + lookback * MS_DAY
        last = candles[-1][0] - window * MS_DAY
        while start <= last:
            end = start + window * MS_DAY
            win = slice_range(candles, start, end)
            if len(win) < 10:
                start += step * MS_DAY
                continue
            try:
                lo, hi = auto_range(candles, start, lookback)
            except ValueError:
                start += step * MS_DAY
                continue
            entry = win[0][1]
            rl = run_grid(win, [], "long", lo, hi, grids, 10000, 1.0, 0.0002, "arithmetic", inst)
            mw = mirror(win, entry)
            rs = run_grid(mw, [], "short", entry * entry / hi, entry * entry / lo,
                          grids, 10000, 1.0, 0.0002, "arithmetic", inst)
            pairs.append({"bh": round(rl.bh_ret_pct, 2), "real_long": round(rl.ret_pct, 2),
                          "mirror_short": round(rs.ret_pct, 2)})
            start += step * MS_DAY
    groups = [("跌 >15%", lambda b: b < -15), ("跌 5–15%", lambda b: -15 <= b < -5),
              ("盤整 ±5%", lambda b: -5 <= b <= 5), ("漲 5–15%", lambda b: 5 < b <= 15),
              ("漲 >15%", lambda b: b > 15)]
    out = []
    for label, f in groups:
        g = [p for p in pairs if f(p["bh"])]
        if g:
            a = st.mean([p["real_long"] for p in g])
            b = st.mean([p["mirror_short"] for p in g])
            out.append({"label": label, "n": len(g), "real_long": round(a, 2),
                        "mirror_short": round(b, 2), "gap": round(a - b, 2)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    D = args.datadir

    base = rolling(D)
    regs = {
        "up": agg([r for r in base if r["bh"] > 5]),
        "range": agg([r for r in base if -5 <= r["bh"] <= 5]),
        "down": agg([r for r in base if r["bh"] < -5]),
        "all": agg(base),
    }
    per_inst = {i.replace("-USDT-SWAP", ""): agg([r for r in base if r["inst"] == i.replace("-USDT-SWAP", "")])
                for i in INSTS}
    fund_rows = [r for r in base if r["has_funding"]]

    # alignment decomposition
    up = [r for r in base if r["bh"] > 5]
    dn = [r for r in base if r["bh"] < -5]
    align = [
        {"case": "多頭網格 / 上漲", "tag": "順勢", "mode": "long",
         "ret": round(st.mean([r["long"]["ret"] for r in up]), 2),
         "grid": round(st.mean([r["long"]["grid"] for r in up]), 2),
         "float": round(st.mean([r["long"]["float"] for r in up]), 2),
         "in_range": round(st.mean([r["long"]["in_range"] for r in up]), 1)},
        {"case": "空頭網格 / 下跌", "tag": "順勢", "mode": "short",
         "ret": round(st.mean([r["short"]["ret"] for r in dn]), 2),
         "grid": round(st.mean([r["short"]["grid"] for r in dn]), 2),
         "float": round(st.mean([r["short"]["float"] for r in dn]), 2),
         "in_range": round(st.mean([r["short"]["in_range"] for r in dn]), 1)},
        {"case": "空頭網格 / 上漲", "tag": "逆勢", "mode": "short",
         "ret": round(st.mean([r["short"]["ret"] for r in up]), 2),
         "grid": round(st.mean([r["short"]["grid"] for r in up]), 2),
         "float": round(st.mean([r["short"]["float"] for r in up]), 2),
         "in_range": round(st.mean([r["short"]["in_range"] for r in up]), 1)},
        {"case": "多頭網格 / 下跌", "tag": "逆勢", "mode": "long",
         "ret": round(st.mean([r["long"]["ret"] for r in dn]), 2),
         "grid": round(st.mean([r["long"]["grid"] for r in dn]), 2),
         "float": round(st.mean([r["long"]["float"] for r in dn]), 2),
         "in_range": round(st.mean([r["long"]["in_range"] for r in dn]), 1)},
    ]

    # robustness sweep
    variants = [
        ("基準 15m / 50 格 / 1x", {}),
        ("1H K 線", {"bar": "1H"}),
        ("5m K 線 (BTC,SOL)", {"bar": "5m", "insts": ["BTC-USDT-SWAP", "SOL-USDT-SWAP"]}),
        ("15m 對照 (BTC,SOL)", {"insts": ["BTC-USDT-SWAP", "SOL-USDT-SWAP"]}),
        ("20 格", {"grids": 20}),
        ("100 格", {"grids": 100}),
        ("等比網格", {"spacing": "geometric"}),
        ("吃單費率 0.05%", {"fee": 0.0005}),
        ("零手續費", {"fee": 0.0}),
        ("2x 槓桿", {"leverage": 2.0}),
        ("不計資金費", {"funding_on": False}),
        ("14 天視窗", {"window": 14}),
        ("60 天視窗", {"window": 60}),
        ("60 天區間回看", {"lookback": 60}),
    ]
    sweep = []
    for label, kw in variants:
        s = rolling(D, **kw)
        sweep.append({
            "label": label, "n": len(s),
            "long": round(st.mean([r["long"]["ret"] for r in s]), 2),
            "short": round(st.mean([r["short"]["ret"] for r in s]), 2),
            "neutral": round(st.mean([r["neutral"]["ret"] for r in s]), 2),
            "lgrid": round(st.mean([r["long"]["grid"] for r in s]), 2),
            "sgrid": round(st.mean([r["short"]["grid"] for r in s]), 2),
        })

    # equity curves, 180d BTC
    candles, funding = load(D, "BTC-USDT-SWAP", "15m")
    end = candles[-1][0] + 1
    start = end - 180 * MS_DAY
    lo, hi = auto_range(candles, start, 30)
    win = slice_range(candles, start, end)
    fw = [f for f in funding if start <= f[0] < end]
    curves, meta = {}, {}
    for m in MODES:
        r = run_grid(win, fw, m, lo, hi, 50, 10000, 1.0, 0.0002, "arithmetic", "BTC-USDT-SWAP")
        k = max(1, len(r.equity) // 360)
        curves[m] = [round(e / 100 - 100, 2) for _, e in r.equity[::k]]
        meta[m] = {"ret": round(r.ret_pct, 2), "dd": round(r.max_dd_pct, 2),
                   "grid": round(r.grid_ret_pct, 2), "fills": r.trades}
    k = max(1, len(win) // 360)
    curve = {"inst": "BTC-USDT-SWAP", "days": 180, "lower": round(lo, 1), "upper": round(hi, 1),
             "ts": [c[0] for c in win[::k]], "px": [round(c[4], 1) for c in win[::k]],
             "curves": curves, "meta": meta,
             "start": headline(D, 180)[0]["start"], "end": headline(D, 180)[0]["end"]}

    data = {
        "meta": {
            "source": "OKX v5 public API — /market/history-candles + /public/funding-rate-history",
            "insts": [i.replace("-USDT-SWAP", "") for i in INSTS],
            "bar": "15m", "grids": 50, "investment": 10000, "leverage": 1,
            "fee": "maker 0.02%", "window": 30, "step": 3, "lookback": 30,
        },
        "headline": {str(d): headline(D, d) for d in (30, 90, 180)},
        "rolling": {"regimes": regs, "per_inst": per_inst, "n": len(base)},
        "funding": dict(
            {m: {"mean": round(st.mean([r[m]["fund"] for r in fund_rows]), 3),
                 "median": round(st.median([r[m]["fund"] for r in fund_rows]), 3)}
             for m in MODES},
            n=len(fund_rows), n_total=len(base),
        ),
        "scatter": [{"bh": r["bh"], "l": r["long"]["ret"], "s": r["short"]["ret"],
                     "n": r["neutral"]["ret"], "inst": r["inst"]} for r in base],
        "align": align,
        "sweep": sweep,
        "mirror": mirror_study(D),
        "curve": curve,
    }
    json.dump(data, open(args.out, "w"), ensure_ascii=False)
    print("wrote", args.out, os.path.getsize(args.out), "bytes")


if __name__ == "__main__":
    main()
