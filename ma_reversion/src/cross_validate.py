#!/usr/bin/env python3
"""Run the MU-derived strategy, unchanged, across other OKX stock-token perps.

This is the falsification test. The rules and every parameter were fitted on
MU, so MU is not evidence about MU. If the edge really comes from the structure
of the Taipei 08:00-16:00 window - thin overnight books, dislocations that
revert - it has to show up in names that were never looked at. If it only shows
up in MU, the strategy is a five-month fluke.

Nothing here is tuned per instrument. The config is loaded once and frozen.

    python src/cross_validate.py --params config/params_15m.json \
        --instruments NVDA AAPL TSLA ... --discovery MU

Two independent readouts per instrument:

  event study - non-overlapping first-touch events and their forward return
                over `max_hold_bars`, before costs. Measures the raw signal.
  backtest    - the full strategy with costs, limit fills, stops and the
                session flat. Measures what is actually harvestable.

Pooled significance is reported two ways. The naive t-stat treats every event
as independent, which it is not: these names move together, so a single wild
night contributes a dozen correlated observations. The clustered t-stat first
averages events within a session date and then tests across dates, which is the
number to believe.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import run_backtest
from features import add_features, load_candles
from metrics import summarize
from strategy import DEFAULT_PARAMS

ROOT = Path(__file__).resolve().parents[1]


def tstat(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 3 or x.std() == 0:
        return float("nan")
    return float(x.mean() / x.std() * np.sqrt(len(x)))


def event_study(feat: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Non-overlapping first-touch events and their forward return, in %."""
    z = feat["z"]
    s = feat["in_session"]
    ze = p["z_entry"]
    h = p["max_hold_bars"]
    fwd = (feat["close"].shift(-h) / feat["close"] - 1.0) * 100.0

    ev_l = (z <= -ze) & (z.shift(1) > -ze) & s
    ev_s = (z >= ze) & (z.shift(1) < ze) & s
    out = pd.concat([
        pd.DataFrame({"r": fwd[ev_l], "side": "long"}),
        pd.DataFrame({"r": -fwd[ev_s], "side": "short"}),
    ]).dropna().sort_index()
    if out.empty:
        return out
    out["session"] = out.index.tz_convert("Asia/Taipei").strftime("%Y-%m-%d")
    return out


def run_one(path: Path, p: dict) -> tuple[dict, pd.DataFrame]:
    df = load_candles(str(path))
    feat = add_features(df, p)
    ev = event_study(feat, p)
    res = run_backtest(feat, p)
    summ = summarize(res)

    # Thin books show up as bars that never traded or never moved. Those bars
    # collapse sigma and manufacture huge z values out of nothing, so the rate
    # has to be read alongside any result from a low-volume name.
    sess = feat[feat["in_session"]]
    dead = float(((sess["volume"] <= 0) | (sess["high"] <= sess["low"])).mean() * 100) \
        if len(sess) else float("nan")

    # A percentage edge is not comparable across names with different
    # volatility, but a sigma-denominated one is: the strategy always fades the
    # same number of sigma and always pays the same bps. Expressing both the
    # edge and the cost in sigma is what makes the cross-section readable.
    sigma_pct = float((sess["sd"] / sess["close"] * 100).median()) if len(sess) else float("nan")
    cost_sd = (2 * p["maker_bps"] / 10_000.0 * 100) / sigma_pct if sigma_pct else float("nan")
    ev_mean = float(ev["r"].mean()) if len(ev) else float("nan")

    row = {
        "bars": len(df),
        "first": f"{df.index[0]:%Y-%m-%d}",
        "dead_bar_pct": dead,
        "sigma_pct": sigma_pct,
        "events": len(ev),
        "ev_mean_pct": ev_mean,
        "ev_mean_sd": ev_mean / sigma_pct if sigma_pct else float("nan"),
        "cost_sd": cost_sd,
        "net_sd": ev_mean / sigma_pct - cost_sd if sigma_pct else float("nan"),
        "ev_t": tstat(ev["r"]) if len(ev) else float("nan"),
        "ev_win_pct": float((ev["r"] > 0).mean() * 100) if len(ev) else float("nan"),
        "trades": summ["trades"],
        "return_pct": summ["total_return_pct"],
        "sharpe": summ.get("sharpe", float("nan")),
        "win_pct": summ.get("win_rate_pct", float("nan")),
        "pf": summ.get("profit_factor", float("nan")),
        "max_dd_pct": summ.get("max_dd_pct", float("nan")),
    }
    return row, ev


def pooled_stats(ev_all: pd.DataFrame) -> dict:
    """Naive and session-clustered significance for the pooled event set."""
    naive = tstat(ev_all["r"])
    by_session = ev_all.groupby("session")["r"].mean()
    return {
        "events": len(ev_all),
        "sessions": int(by_session.size),
        "mean_pct": float(ev_all["r"].mean()),
        "win_pct": float((ev_all["r"] > 0).mean() * 100),
        "t_naive": naive,
        "t_clustered": tstat(by_session),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=str(ROOT / "config" / "params_15m.json"))
    ap.add_argument("--instruments", nargs="+", required=True,
                    help="base symbols, e.g. NVDA AAPL TSLA")
    ap.add_argument("--discovery", default="MU",
                    help="symbol the parameters were fitted on; reported separately")
    ap.add_argument("--datadir", default=str(ROOT / "data"))
    ap.add_argument("--outdir", default=str(ROOT / "results"))
    ap.add_argument("--session-hours", nargs=2, type=int, default=None)
    ap.add_argument("--tag", default="cross")
    args = ap.parse_args()

    p = dict(DEFAULT_PARAMS)
    p.update(json.loads(Path(args.params).read_text()))
    if args.session_hours:
        p["session_start_hour"], p["session_end_hour"] = args.session_hours

    datadir = Path(args.datadir)
    rows, evs = {}, {}
    for sym in args.instruments:
        path = datadir / f"{sym}-USDT-SWAP_{p['bar']}.csv"
        if not path.exists():
            path = path.with_suffix(".csv.gz")
        if not path.exists():
            print(f"  {sym}: no data, skipped")
            continue
        row, ev = run_one(path, p)
        rows[sym] = row
        if len(ev):
            ev = ev.copy()
            ev["sym"] = sym
            evs[sym] = ev

    if not rows:
        print("no instruments processed")
        return 1

    tbl = pd.DataFrame(rows).T
    tbl.index.name = "symbol"
    out_of_sample = [s for s in tbl.index if s != args.discovery]

    session = f"{p['session_start_hour']:02d}-{p['session_end_hour']:02d}"
    print(f"\n=== frozen {args.discovery} config, Taipei {session}, {p['bar']} "
          f"(z_entry={p['z_entry']}, ma_len={p['ma_len']}, hold={p['max_hold_bars']}) ===\n")
    num = tbl.drop(columns=["first"]).astype(float)
    show = num[["sigma_pct", "dead_bar_pct", "events", "ev_mean_pct", "ev_t", "ev_win_pct",
                "trades", "return_pct", "sharpe", "pf", "max_dd_pct"]].round(3)
    print(show.to_string())

    print("\n--- edge vs cost, both in sigma (why some names are untradeable) ---")
    econ = num[["sigma_pct", "ev_mean_sd", "cost_sd", "net_sd", "return_pct"]].round(3)
    print(econ.sort_values("sigma_pct", ascending=False).to_string())
    oos_econ = econ.loc[[s for s in econ.index if s != args.discovery]]
    if len(oos_econ) > 2:
        c = oos_econ["sigma_pct"].corr(oos_econ["ev_mean_sd"])
        c2 = oos_econ["sigma_pct"].corr(oos_econ["return_pct"])
        print(f"\n  out-of-sample correlation, sigma_pct vs edge-in-sigma : {c:+.2f}")
        print(f"  out-of-sample correlation, sigma_pct vs backtest return: {c2:+.2f}")

    if evs:
        pooled_all = pd.concat(evs.values())
        oos = pooled_all[pooled_all["sym"] != args.discovery]
        print("\n--- pooled event study ---")
        for label, frame in (("all instruments", pooled_all),
                             ("out-of-sample only", oos)):
            if frame.empty:
                continue
            st = pooled_stats(frame)
            print(f"  {label:<20} n={st['events']:>4}  sessions={st['sessions']:>3}  "
                  f"mean={st['mean_pct']:+.3f}%  win={st['win_pct']:.1f}%  "
                  f"t_naive={st['t_naive']:+.2f}  t_clustered={st['t_clustered']:+.2f}")
        pooled_all.to_csv(Path(args.outdir) / f"{args.tag}_events_{session}.csv")

    if out_of_sample:
        oos_tbl = num.loc[out_of_sample]
        pos = int((oos_tbl["return_pct"] > 0).sum())
        print(f"\n--- backtest across the {len(out_of_sample)} out-of-sample names ---")
        print(f"  profitable            {pos}/{len(out_of_sample)}")
        print(f"  median return         {oos_tbl['return_pct'].median():+.2f}%")
        print(f"  mean return           {oos_tbl['return_pct'].mean():+.2f}%")
        print(f"  median Sharpe         {oos_tbl['sharpe'].median():+.2f}")
        print(f"  total trades          {int(oos_tbl['trades'].sum())}")
        ev_pos = int((oos_tbl["ev_mean_pct"] > 0).sum())
        print(f"  positive event edge   {ev_pos}/{len(out_of_sample)}")

    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    tbl.to_csv(Path(args.outdir) / f"{args.tag}_summary_{session}.csv")
    print(f"\nwrote {args.outdir}/{args.tag}_summary_{session}.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
