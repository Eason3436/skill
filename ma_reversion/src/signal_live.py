#!/usr/bin/env python3
"""Print the current live signal for the strategy — read-only, places no orders.

Pulls the most recent closed candles through the `okx market candles` CLI,
rebuilds the exact same features the backtest uses, and reports what the rules
say right now, including the order levels you would work.

    python src/signal_live.py --params config/params.json

Run it a few seconds after each 5-minute bar closes. It never trades; copy the
levels into `okx trade` (or the okx-cex-trade skill) yourself.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from features import TAIPEI, add_features
from fetch_data import COLUMNS, run_cli
from strategy import (DEFAULT_PARAMS, FLAT, LONG, compute_signals, position_size,
                      stop_price)

ROOT = Path(__file__).resolve().parents[1]


def recent_frame(inst: str, bar: str, need: int) -> pd.DataFrame:
    """Fetch at least `need` closed candles, newest last."""
    rows: dict[int, list[str]] = {}
    cursor = None
    while len(rows) < need:
        batch = run_cli(inst, bar, 300, cursor)
        if not batch:
            break
        for r in batch:
            rows[int(r[0])] = r
        nxt = min(int(r[0]) for r in batch)
        if cursor is not None and nxt >= cursor:
            break
        cursor = nxt
    df = pd.DataFrame([rows[t] for t in sorted(rows)], columns=COLUMNS)
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
    df = df.set_index("ts")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c])
    df = df[pd.to_numeric(df["confirm"]) == 1]  # closed bars only
    return df[["open", "high", "low", "close", "volume"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=str(ROOT / "config" / "params.json"))
    ap.add_argument("--equity", type=float, default=None, help="override sizing equity")
    args = ap.parse_args()

    p = dict(DEFAULT_PARAMS)
    p.update(json.loads(Path(args.params).read_text()))
    equity = args.equity if args.equity is not None else p["init_equity"]

    need = max(p["ma_len"], p["regime_win"]) + 50
    df = recent_frame(p["inst"], p["bar"], need)
    feat = add_features(df, p)
    sig = compute_signals(feat, p)
    row = sig.iloc[-1]

    now_tpe = row.name.tz_convert(TAIPEI)
    print(f"{p['inst']} {p['bar']}   last closed bar {now_tpe:%Y-%m-%d %H:%M} Taipei "
          f"({row.name:%H:%M} UTC)")
    print(f"  close    {row['close']:.2f}")
    print(f"  anchor   MA{p['ma_len']} = {row['ma']:.2f}   sigma = {row['sd']:.3f}")
    print(f"  z        {row['z']:+.2f}   (band +/-{p['z_entry']})")
    print(f"  slope_n  {row['slope_n']:+.2f} (max {p['max_slope']})   "
          f"vol rank {row['atr_pct_rank']:.2f} "
          f"(band {p['vol_rank_min']}-{p['vol_rank_max']})")
    print(f"  session  {'OPEN' if row['in_session'] else 'CLOSED'}   "
          f"bars left {int(row['bars_left'])} (need >= {p['min_bars_left']})")

    s = int(row["entry_sig"])
    if s == FLAT:
        print("\n  -> no entry signal")
        return 0

    side = "LONG" if s == LONG else "SHORT"
    limit = row["close"] - s * p["entry_limit_offset_ticks"] * p["tick_size"]
    stop = stop_price(limit, s, row["sd"], p)
    qty = position_size(equity, limit, stop, p)
    hold_until = now_tpe + pd.Timedelta(minutes=5 * p["max_hold_bars"])
    print(f"\n  -> {side} signal")
    print(f"     entry     limit {limit:.2f}  (maker, cancel after "
          f"{p['entry_limit_ttl']} bars)")
    print(f"     size      {qty:g} {p['inst'].split('-')[0]}  "
          f"(~{qty * limit:,.0f} USDT notional, {p['risk_pct']}% equity at risk)")
    print(f"     stop      {stop:.2f}  ({p['stop_sd']} sigma)")
    print(f"     time exit {hold_until:%H:%M} Taipei ({p['max_hold_bars']} bars), "
          f"or {p['session_end_hour']:02d}:00 session close, whichever comes first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
