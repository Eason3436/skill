#!/usr/bin/env python3
"""Run one backtest and write a full report.

    python src/run.py --data data/MU-USDT-SWAP_5m.csv --params config/params.json
    python src/run.py --data ... --session-hours 21 5 --tag us_cash   # A/B the window
    python src/run.py --data ... --start 2026-06-01 --tag oos
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from backtest import run_backtest, session_exposure
from features import add_features, load_candles
from metrics import breakdowns, summarize
from strategy import DEFAULT_PARAMS

ROOT = Path(__file__).resolve().parents[1]

HEADLINE = ["trades", "trades_per_week", "total_return_pct", "cagr_pct", "sharpe", "sortino",
            "max_dd_pct", "calmar", "win_rate_pct", "profit_factor", "expectancy",
            "avg_win", "avg_loss", "max_consec_losses", "avg_bars_held",
            "total_costs", "cost_pct_of_gross", "final_equity"]


def load_params(path: str | None, overrides: dict | None = None) -> dict:
    p = dict(DEFAULT_PARAMS)
    if path:
        p.update(json.loads(Path(path).read_text()))
    if overrides:
        p.update({k: v for k, v in overrides.items() if v is not None})
    return p


def _fmt(v) -> str:
    return f"{v:,.2f}" if isinstance(v, float) else str(v)


def format_report(summ: dict, expo: dict, bd: dict, p: dict, data_range: str) -> str:
    L = [f"# MA-reversion backtest — {p['inst']} {p['bar']}", ""]
    L.append(f"- Data: {data_range}")
    L.append(f"- Session (Taipei): {p['session_start_hour']:02d}:00–{p['session_end_hour']:02d}:00, Mon–Fri")
    L.append(f"- Sessions traded: {expo['sessions']} ({expo['session_bars']:,} of "
             f"{expo['total_bars']:,} bars, {expo['session_share_pct']:.1f}% of the clock)")
    L.append(f"- Execution: {p['entry_exec']} entry · {p['maker_bps']}bps maker / "
             f"{p['taker_bps']}bps taker / {p['slip_bps']}bps slippage on taker fills")
    L.append(f"- Sizing: {p['risk_pct']}% equity risked per trade, max {p['max_leverage']}x notional")
    L.append("")
    L.append("## Headline")
    L.append("")
    L.append("| metric | value |")
    L.append("|---|---:|")
    for k in HEADLINE:
        if k in summ:
            L.append(f"| {k} | {_fmt(summ[k])} |")
    L.append("")
    for name, frame in bd.items():
        L.append(f"## {name}")
        L.append("")
        L.append(frame.to_markdown())
        L.append("")
    L.append("## Parameters")
    L.append("")
    L.append("```json")
    L.append(json.dumps(p, indent=2))
    L.append("```")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--params", default=None)
    ap.add_argument("--tag", default="base")
    ap.add_argument("--session-hours", nargs=2, type=int, default=None,
                    metavar=("START", "END"), help="Taipei hours, e.g. 8 16")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="override any parameter, repeatable")
    ap.add_argument("--start", default=None, help="UTC date filter YYYY-MM-DD")
    ap.add_argument("--end", default=None)
    ap.add_argument("--outdir", default=str(ROOT / "results"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    overrides: dict = {}
    if args.session_hours:
        overrides["session_start_hour"], overrides["session_end_hour"] = args.session_hours
    for kv in args.set:
        k, _, v = kv.partition("=")
        overrides[k] = json.loads(v)
    p = load_params(args.params, overrides)

    df = load_candles(args.data)
    # Keep warm-up history in the frame but only trade the requested slice: the
    # indicators need `regime_win` bars before they mean anything.
    warm = max(p["ma_len"], p["regime_win"], p["atr_len"]) + 5
    if args.start:
        cut = pd.Timestamp(args.start, tz="UTC")
        pre = df[df.index < cut].iloc[-warm:]
        df = pd.concat([pre, df[df.index >= cut]])
        trade_from = cut
    else:
        trade_from = None
    if args.end:
        df = df[df.index < pd.Timestamp(args.end, tz="UTC")]

    feat = add_features(df, p)
    if trade_from is not None:
        feat.loc[feat.index < trade_from, "in_session"] = False
    res = run_backtest(feat, p)
    summ = summarize(res)
    expo = session_exposure(res["signals"])
    bd = breakdowns(res)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rng = f"{df.index[0]:%Y-%m-%d %H:%M} → {df.index[-1]:%Y-%m-%d %H:%M} UTC ({len(df):,} bars)"
    (outdir / f"report_{args.tag}.md").write_text(format_report(summ, expo, bd, p, rng))
    if not res["trades"].empty:
        res["trades"].to_csv(outdir / f"trades_{args.tag}.csv", index=False)
    res["equity"].to_csv(outdir / f"equity_{args.tag}.csv")
    (outdir / f"summary_{args.tag}.json").write_text(
        json.dumps({**summ, **expo}, indent=2, default=str))

    if not args.quiet:
        print(f"[{args.tag}] {rng}")
        print(f"  sessions {expo['sessions']}  session bars {expo['session_bars']:,}")
        for k in HEADLINE:
            if k in summ:
                print(f"  {k:<22} {_fmt(summ[k])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
