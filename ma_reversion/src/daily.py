#!/usr/bin/env python3
"""Daily P&L breakdown for a finished backtest.

Monthly figures hide how lumpy this strategy is, and per-trade figures hide how
often it does nothing at all. The daily view is the one that answers "what does
running this actually feel like".

The denominator matters more than anything else here. Averaging only over days
that produced a trade flatters the result, because capital sits idle on the
other days but is still committed to the strategy. Every average below is taken
over the **full session calendar**, no-trade days included as zeros, which is
what a live account would experience.

    python src/daily.py --trades results/portfolio_trades.csv \
        --calendar data/MU-USDT-SWAP_15m.csv --equity 10000
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from features import load_candles, mark_session

ROOT = Path(__file__).resolve().parents[1]
TRADING_DAYS_PER_MONTH = 21
TRADING_DAYS_PER_YEAR = 252


def session_calendar(path: str, start_hour: int, end_hour: int) -> pd.Index:
    """Every Taipei session in the sample, whether or not it was traded."""
    marked = mark_session(load_candles(path), start_hour, end_hour)
    days = sorted(set(marked.loc[marked["in_session"], "session_id"]))
    return pd.Index(pd.to_datetime(days).date, name="session")


def daily_series(trades: pd.DataFrame, calendar: pd.Index) -> pd.DataFrame:
    """Per-session return (% of equity) and trade count, zero-filled."""
    t = trades.copy()
    t["session"] = pd.to_datetime(t["exit_ts"]).dt.tz_convert("Asia/Taipei").dt.date
    g = t.groupby("session")["ret_pct"].agg(trades="size", ret="sum")
    out = pd.DataFrame({"ret": 0.0, "trades": 0}, index=calendar)
    common = g.index.intersection(calendar)
    out.loc[common, "ret"] = g.loc[common, "ret"]
    out.loc[common, "trades"] = g.loc[common, "trades"]
    return out


def max_losing_streak(returns: pd.Series) -> int:
    best = run = 0
    for v in returns:
        run = run + 1 if v < 0 else 0
        best = max(best, run)
    return best


def report(d: pd.DataFrame, label: str, equity: float, exclude_month: str | None) -> None:
    r = d["ret"]
    active = d["trades"] > 0
    mean = r.mean()

    print(f"\n===== {label} =====")
    print(f"  期間                  {len(d)} 個 session ({d.index[0]} ~ {d.index[-1]})")
    print(f"  總報酬                {r.sum():+.2f}%")
    print(f"  平均每 session        {mean:+.4f}%  →  每 {equity:,.0f} USDT ≈ {mean / 100 * equity:+.2f} USDT/日")
    print(f"  月化 ({TRADING_DAYS_PER_MONTH} 個交易日)   {mean * TRADING_DAYS_PER_MONTH:+.2f}%"
          f"  →  ≈ {mean * TRADING_DAYS_PER_MONTH / 100 * equity:+,.0f} USDT/月")
    print(f"  有進場的日數          {int(active.sum())}/{len(d)} ({active.mean() * 100:.0f}%)"
          f"  ← 其餘 {int((~active).sum())} 天完全空手")
    print(f"  全日曆               賺 {int((r > 0).sum())} / 賠 {int((r < 0).sum())} / 空手 {int((r == 0).sum())}")
    print(f"  有交易日的勝率        {(r[active] > 0).mean() * 100:.1f}%")
    print(f"  日收益標準差          {r.std():.4f}%")
    if r.std() > 0:
        print(f"  年化 Sharpe           {mean / r.std() * np.sqrt(TRADING_DAYS_PER_YEAR):.2f}")
    print(f"  最好 / 最差           {r.max():+.3f}% ({r.idxmax()}) / {r.min():+.3f}% ({r.idxmin()})")
    q = r[active].quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    print("  有交易日分位 5/25/50/75/95   "
          + " / ".join(f"{v:+.3f}" for v in q))
    print(f"  最長連續虧損日        {max_losing_streak(r[active])}")

    if exclude_month:
        months = pd.to_datetime(pd.Series(d.index)).dt.strftime("%Y-%m").to_numpy()
        keep = months != exclude_month
        rx = r[keep]
        print(f"  --- 扣掉 {exclude_month} ---")
        print(f"  總報酬                {rx.sum():+.2f}%  ({int(keep.sum())} 個 session)")
        print(f"  平均每 session        {rx.mean():+.4f}%  →  {rx.mean() / 100 * equity:+.2f} USDT/日")
        if rx.std() > 0:
            print(f"  年化 Sharpe           {rx.mean() / rx.std() * np.sqrt(TRADING_DAYS_PER_YEAR):.2f}")

    monthly = d.copy()
    monthly["month"] = pd.to_datetime(pd.Series(d.index)).dt.strftime("%Y-%m").to_numpy()
    agg = monthly.groupby("month").agg(
        sessions=("ret", "size"),
        traded=("trades", lambda s: int((s > 0).sum())),
        total=("ret", "sum"),
        per_day=("ret", "mean"),
        win=("ret", lambda s: (s > 0).sum()),
    ).round(4)
    print("\n  逐月:")
    print(agg.to_string())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", required=True, help="trades CSV from run.py or portfolio.py")
    ap.add_argument("--calendar", default=str(ROOT / "data" / "MU-USDT-SWAP_15m.csv"),
                    help="any instrument's candles, used only for the session calendar")
    ap.add_argument("--equity", type=float, default=10_000.0)
    ap.add_argument("--label", default=None)
    ap.add_argument("--session-hours", nargs=2, type=int, default=(8, 16))
    ap.add_argument("--exclude-month", default=None,
                    help="e.g. 2026-07, to see the result without the best month")
    args = ap.parse_args()

    cal = session_calendar(args.calendar, *args.session_hours)
    trades = pd.read_csv(args.trades)
    d = daily_series(trades, cal)
    report(d, args.label or Path(args.trades).stem, args.equity, args.exclude_month)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
