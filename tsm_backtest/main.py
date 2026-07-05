"""Run the TSM weekend Bollinger backtest and emit a full report.

Usage examples
--------------
    python main.py --source okx                 # working here (TSM-USDT-SWAP)
    python main.py --source bybit               # where Bybit is reachable
    python main.py --source okx --weeks 52       # cap to the last N weeks
    python main.py --source okx --csv data/tsm.csv   # cache / reuse raw bars

Outputs (written under ``results/``):
    * report.txt         human-readable summary (also printed to stdout)
    * trades.csv         every buy/sell round-trip
    * weekly.csv         per-weekend breakdown
    * equity_curve.csv   mark-to-market equity per bar
"""

from __future__ import annotations

import argparse
import os
import datetime as dt

import pandas as pd

from data_sources import get_source, DEFAULT_SYMBOLS
from strategy import run_backtest, trade_stats

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")


def load_data(source: str, symbol: str, weeks: int | None, csv: str | None) -> pd.DataFrame:
    if csv and os.path.exists(csv):
        df = pd.read_csv(csv, index_col=0, parse_dates=True)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        print(f"[data] loaded {len(df)} bars from cache {csv}")
    else:
        start_ms = None
        if weeks:
            start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(weeks=weeks)
            start_ms = int(start.timestamp() * 1000)
        src = get_source(source)
        print(f"[data] fetching {symbol} 30m from {source} ...")
        df = src.fetch_30m(symbol=symbol, start_ms=start_ms)
        print(f"[data] fetched {len(df)} bars")
        if csv:
            os.makedirs(os.path.dirname(csv) or ".", exist_ok=True)
            df.to_csv(csv)
            print(f"[data] cached -> {csv}")
    if weeks:
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(weeks=weeks)
        df = df[df.index >= cutoff]
    return df


def fmt_money(x: float) -> str:
    return f"${x:,.2f}"


def build_report(res, stats, meta: dict) -> str:
    L = []
    L.append("=" * 68)
    L.append("TSM 週末布林通道策略 — 回測報告")
    L.append("=" * 68)
    L.append(f"資料來源      : {meta['source']}  ({meta['symbol']})")
    L.append(f"K線週期       : 30 分鐘   |  時區: {meta['tz']}")
    L.append(f"布林通道      : {meta['period']} 期均線 ± {meta['mult']} 標準差")
    if res.data_start is not None:
        span_days = (res.data_end - res.data_start).total_seconds() / 86400
        L.append(f"資料範圍      : {res.data_start:%Y-%m-%d %H:%M} ~ "
                 f"{res.data_end:%Y-%m-%d %H:%M} UTC "
                 f"({span_days:.1f} 天 ≈ {span_days/7:.1f} 週)")
    L.append(f"K棒總數       : {res.bar_count:,}")
    L.append(f"手續費率      : {meta['fee_rate']*100:.3f}% / 邊")
    L.append("")
    L.append("── 整體績效 " + "─" * 55)
    L.append(f"起始資金      : {fmt_money(res.start_equity)}")
    L.append(f"最終淨值      : {fmt_money(res.end_equity)}")
    L.append(f"總報酬        : {res.total_return_pct:+.2f}%")
    if res.max_drawdown_date is not None:
        L.append(f"最大回撤      : {res.max_drawdown_pct:.2f}%  "
                 f"(發生於 {res.max_drawdown_date:%Y-%m-%d %H:%M} UTC)")
    else:
        L.append("最大回撤      : n/a")
    L.append("")
    L.append("── 交易統計 " + "─" * 55)
    if stats["n_trades"] == 0:
        L.append("本區間內未觸發任何交易。")
    else:
        L.append(f"總交易組數    : {stats['n_trades']}  (買賣配對)")
        L.append(f"  自然出場(碰上軌) : {stats['n_natural_exit']}")
        L.append(f"  強制平倉(週日收) : {stats['n_forced_exit']}")
        L.append(f"勝率          : {stats['win_rate_pct']:.1f}%")
        bt, wt = stats["best_trade"], stats["worst_trade"]
        L.append(f"單筆最大獲利  : {stats['best_trade_pct']:+.2f}%  "
                 f"({bt.entry_time:%Y-%m-%d %H:%M} → {bt.exit_time:%H:%M}, {bt.exit_reason})")
        L.append(f"單筆最大虧損  : {stats['worst_trade_pct']:+.2f}%  "
                 f"({wt.entry_time:%Y-%m-%d %H:%M} → {wt.exit_time:%H:%M}, {wt.exit_reason})")
        L.append(f"平均每筆損益  : {stats['avg_trade_pct']:+.2f}%")
    L.append("")
    L.append("── 逐週明細 " + "─" * 55)
    if res.weekly.empty:
        L.append("(無)")
    else:
        L.append(f"{'週末(六)':<12}{'組數':>5}{'該週損益%':>12}{'該週損益USD':>16}{'累計淨值':>16}")
        for _, r in res.weekly.iterrows():
            L.append(f"{r['weekend']:<12}{int(r['n_trades']):>5}"
                     f"{r['pnl_pct']:>11.2f}%{fmt_money(r['pnl_usd']):>16}"
                     f"{fmt_money(r['cum_equity']):>16}")
    L.append("=" * 68)
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="TSM weekend Bollinger backtest")
    ap.add_argument("--source", default="okx", choices=["okx", "bybit"])
    ap.add_argument("--symbol", default=None, help="override instrument symbol")
    ap.add_argument("--weeks", type=int, default=None, help="cap to last N weeks")
    ap.add_argument("--capital", type=float, default=10_000.0)
    ap.add_argument("--period", type=int, default=20)
    ap.add_argument("--mult", type=float, default=2.5)
    ap.add_argument("--tz", default="UTC")
    ap.add_argument("--fee-rate", type=float, default=0.0)
    ap.add_argument("--no-same-bar-exit", action="store_true",
                    help="conservative: forbid exiting on the same bar as entry")
    ap.add_argument("--csv", default=None, help="cache/read raw bars from this CSV")
    args = ap.parse_args()

    symbol = args.symbol or DEFAULT_SYMBOLS[args.source]
    df = load_data(args.source, symbol, args.weeks, args.csv)

    res = run_backtest(
        df, start_equity=args.capital, period=args.period, mult=args.mult,
        tz=args.tz, fee_rate=args.fee_rate,
        allow_same_bar_exit=not args.no_same_bar_exit,
    )
    stats = trade_stats(res)
    meta = {"source": args.source, "symbol": symbol, "tz": args.tz,
            "period": args.period, "mult": args.mult, "fee_rate": args.fee_rate}

    report = build_report(res, stats, meta)
    print("\n" + report)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "report.txt"), "w") as f:
        f.write(report + "\n")
    res.weekly.to_csv(os.path.join(RESULTS, "weekly.csv"), index=False)
    res.equity_curve.to_csv(os.path.join(RESULTS, "equity_curve.csv"))
    tr = pd.DataFrame([{
        "entry_time": t.entry_time, "entry_price": t.entry_price,
        "exit_time": t.exit_time, "exit_price": t.exit_price,
        "exit_reason": t.exit_reason, "weekend": t.weekend,
        "ret_pct": t.ret_pct, "pnl_usd": t.pnl_usd,
        "equity_after": t.equity_after,
    } for t in res.trades])
    tr.to_csv(os.path.join(RESULTS, "trades.csv"), index=False)
    print(f"\n[out] wrote report.txt / trades.csv / weekly.csv / equity_curve.csv to {RESULTS}")


if __name__ == "__main__":
    main()
