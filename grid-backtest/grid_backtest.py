#!/usr/bin/env python3
"""Grid-bot backtester driven by real OKX candles.

Simulates the actual OKX grid order state machine:
  * buy order fills at level i  -> a sell order is placed at level i+1
  * sell order fills at level j -> a buy order is placed at level j-1

Long grid  (多頭網格): starts by buying the inventory needed to cover every
                       sell order above the entry price; position stays >= 0.
Short grid (空頭網格): mirror image; starts short enough to cover every buy
                       order below the entry price; position stays <= 0.
Neutral    (中性網格): no initial position, long below entry / short above.

Intrabar path assumption: bars with close >= open are walked
open -> low -> high -> close, otherwise open -> high -> low -> close.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
from dataclasses import dataclass, field

MS_DAY = 86_400_000


# --------------------------------------------------------------------------- data


def load_candles(path):
    out = []
    with open(path) as fh:
        for row in csv.DictReader(fh):
            out.append(
                (
                    int(row["ts"]),
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                )
            )
    return out


def load_funding(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [(int(r["ts"]), float(r["rate"])) for r in csv.DictReader(fh)]


def slice_range(candles, start_ms, end_ms):
    return [c for c in candles if start_ms <= c[0] < end_ms]


# --------------------------------------------------------------------------- grid


def build_levels(lower, upper, n_grids, spacing):
    """n_grids intervals -> n_grids + 1 price lines."""
    if spacing == "geometric":
        r = (upper / lower) ** (1.0 / n_grids)
        return [lower * r ** i for i in range(n_grids + 1)]
    step = (upper - lower) / n_grids
    return [lower + step * i for i in range(n_grids + 1)]


@dataclass
class Result:
    mode: str
    inst: str
    start: str
    end: str
    days: float
    lower: float
    upper: float
    n_grids: int
    entry: float
    exit: float
    qty_per_grid: float
    investment: float
    leverage: float
    trades: int
    matched: int
    grid_profit: float = 0.0
    float_pnl: float = 0.0
    fees: float = 0.0
    funding: float = 0.0
    total_pnl: float = 0.0
    ret_pct: float = 0.0
    apr_pct: float = 0.0
    grid_ret_pct: float = 0.0
    max_dd_pct: float = 0.0
    time_in_range_pct: float = 0.0
    final_pos: float = 0.0
    bh_ret_pct: float = 0.0
    equity: list = field(default_factory=list)


def run_grid(
    candles,
    funding,
    mode,
    lower,
    upper,
    n_grids,
    investment,
    leverage=1.0,
    fee_rate=0.0002,
    spacing="arithmetic",
    inst="",
):
    levels = build_levels(lower, upper, n_grids, spacing)
    n = len(levels)
    entry = candles[0][1]

    # ---- position sizing: same formula for both directions, so long vs short
    # commit the same margin and only the direction differs.
    below = [p for p in levels if p < entry]
    above = [p for p in levels if p > entry]
    if mode == "long":
        need = sum(below) + entry * len(above)
    elif mode == "short":
        need = sum(above) + entry * len(below)
    else:  # neutral: no initial inventory, capital reserved for both sides
        need = sum(below) + sum(above)
    if need <= 0:
        raise ValueError("price outside grid range, cannot size position")
    qty = investment * leverage / need

    # ---- initial position
    cash = 0.0
    pos = 0.0
    fees = 0.0
    trades = 0
    matched = 0
    grid_profit = 0.0
    if mode == "long" and above:
        pos = qty * len(above)
        cash -= pos * entry
        fees += pos * entry * fee_rate
        trades += 1
    elif mode == "short" and below:
        pos = -qty * len(below)
        cash += -pos * entry
        fees += -pos * entry * fee_rate
        trades += 1

    # ---- initial resting orders (index -> side)
    # orders[i] = side; pair[i] = price of the trade this order closes (None = opener)
    orders = {}
    pair = {}
    for i, p in enumerate(levels):
        if p < entry:
            orders[i] = "buy"
            pair[i] = entry if mode == "short" else None
        elif p > entry:
            orders[i] = "sell"
            pair[i] = entry if mode == "long" else None
    # In a long grid every buy opens and every sell closes; in a short grid every
    # sell opens and every buy closes. Direction is enforced by the position caps
    # in fill(), which mirror how OKX one-directional bots behave.

    max_pos = qty * n
    equity_curve = []
    peak = -1e18
    max_dd = 0.0
    in_range = 0

    fund_i = 0
    funding_paid = 0.0
    funding = funding or []

    def fill(i, side):
        """Execute a resting order. Returns False if a direction cap blocks it."""
        nonlocal cash, pos, fees, trades, matched, grid_profit
        px = levels[i]
        if side == "buy":
            if mode == "long" and pos + qty > max_pos + 1e-12:
                return False
            if mode == "short" and pos + qty > 1e-12:
                return False  # a short grid never flips long
            pos += qty
            cash -= qty * px
            if pair.get(i) is not None:  # this buy closes a short opened higher
                grid_profit += qty * (pair[i] - px)
                matched += 1
        else:
            if mode == "short" and pos - qty < -max_pos - 1e-12:
                return False
            if mode == "long" and pos - qty < -1e-12:
                return False  # a long grid never flips short
            pos -= qty
            cash += qty * px
            if pair.get(i) is not None:  # this sell closes a long opened lower
                grid_profit += qty * (px - pair[i])
                matched += 1
        fees += qty * px * fee_rate
        trades += 1
        # Replace the filled order one grid away, mirroring OKX behaviour. An
        # opener's replacement is the closer that books the grid profit; a
        # closer's replacement re-opens and carries no pair.
        was_opener = pair.get(i) is None
        del orders[i]
        pair.pop(i, None)
        nxt = i + 1 if side == "buy" else i - 1
        if 0 <= nxt < n:
            orders[nxt] = "sell" if side == "buy" else "buy"
            pair[nxt] = px if was_opener else None
        return True

    def best_buy():
        cand = [i for i, s in orders.items() if s == "buy"]
        return max(cand) if cand else None

    def best_sell():
        cand = [i for i, s in orders.items() if s == "sell"]
        return min(cand) if cand else None

    def leg_down(target):
        while True:
            i = best_buy()
            if i is None or levels[i] < target:
                return
            if not fill(i, "buy"):
                return  # capped out; nothing further can fill in this direction

    def leg_up(target):
        while True:
            i = best_sell()
            if i is None or levels[i] > target:
                return
            if not fill(i, "sell"):
                return

    for ts, o, h, l, c in candles:
        if lower <= c <= upper:
            in_range += 1
        if c >= o:
            leg_down(l)
            leg_up(h)
        else:
            leg_up(h)
            leg_down(l)

        # funding settlements that fall inside this bar
        while fund_i < len(funding) and funding[fund_i][0] <= ts:
            funding_paid -= pos * c * funding[fund_i][1]
            fund_i += 1

        eq = investment + cash + pos * c - fees + funding_paid
        equity_curve.append((ts, eq))
        peak = max(peak, eq)
        if peak > 0:
            max_dd = max(max_dd, (peak - eq) / peak)

    exit_px = candles[-1][4]
    total = cash + pos * exit_px - fees + funding_paid
    float_pnl = total - grid_profit + fees - funding_paid
    days = (candles[-1][0] - candles[0][0]) / MS_DAY
    ret = total / investment * 100
    apr = ret * 365 / days if days > 0 else 0.0

    return Result(
        mode=mode,
        inst=inst,
        start=dt.datetime.utcfromtimestamp(candles[0][0] / 1000).strftime("%Y-%m-%d"),
        end=dt.datetime.utcfromtimestamp(candles[-1][0] / 1000).strftime("%Y-%m-%d"),
        days=days,
        lower=lower,
        upper=upper,
        n_grids=n_grids,
        entry=entry,
        exit=exit_px,
        qty_per_grid=qty,
        investment=investment,
        leverage=leverage,
        trades=trades,
        matched=matched,
        grid_profit=grid_profit,
        float_pnl=float_pnl,
        fees=fees,
        funding=funding_paid,
        total_pnl=total,
        ret_pct=ret,
        apr_pct=apr,
        grid_ret_pct=grid_profit / investment * 100,
        max_dd_pct=max_dd * 100,
        time_in_range_pct=in_range / len(candles) * 100,
        final_pos=pos,
        bh_ret_pct=(exit_px / entry - 1) * 100,
        equity=equity_curve,
    )


# --------------------------------------------------------------------------- cli


def auto_range(candles_all, start_ms, lookback_days, pad=0.0):
    """Range taken from the trailing window BEFORE the test starts (no lookahead)."""
    w = [c for c in candles_all if start_ms - lookback_days * MS_DAY <= c[0] < start_ms]
    if not w:
        raise ValueError("not enough history for the lookback window")
    lo = min(c[3] for c in w)
    hi = max(c[2] for c in w)
    return lo * (1 - pad), hi * (1 + pad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datadir", required=True)
    ap.add_argument("--insts", default="BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP,DOGE-USDT-SWAP")
    ap.add_argument("--bar", default="15m")
    ap.add_argument("--days", type=int, default=90, help="test window length")
    ap.add_argument("--lookback", type=int, default=30, help="days used to set the grid range")
    ap.add_argument("--grids", type=int, default=50)
    ap.add_argument("--investment", type=float, default=10000)
    ap.add_argument("--leverage", type=float, default=1.0)
    ap.add_argument("--fee", type=float, default=0.0002, help="maker fee, 0.0002 = 0.02%%")
    ap.add_argument("--spacing", default="arithmetic", choices=["arithmetic", "geometric"])
    ap.add_argument("--no-funding", action="store_true")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    rows = []
    for inst in args.insts.split(","):
        inst = inst.strip()
        candles = load_candles(os.path.join(args.datadir, f"{inst}_{args.bar}.csv"))
        funding = [] if args.no_funding else load_funding(
            os.path.join(args.datadir, f"{inst}_funding.csv")
        )
        end_ms = candles[-1][0] + 1
        start_ms = end_ms - args.days * MS_DAY
        lo, hi = auto_range(candles, start_ms, args.lookback)
        window = slice_range(candles, start_ms, end_ms)
        fw = [f for f in funding if start_ms <= f[0] < end_ms]
        for mode in ("long", "short", "neutral"):
            r = run_grid(
                window, fw, mode, lo, hi, args.grids, args.investment,
                args.leverage, args.fee, args.spacing, inst,
            )
            rows.append(r)

    hdr = f"{'inst':<16}{'mode':<9}{'ret%':>9}{'APR%':>9}{'grid%':>8}{'float%':>9}{'fee':>9}{'fund':>9}{'DD%':>8}{'fills':>7}{'inRange%':>10}{'B&H%':>9}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(
            f"{r.inst:<16}{r.mode:<9}{r.ret_pct:>9.2f}{r.apr_pct:>9.1f}"
            f"{r.grid_ret_pct:>8.2f}{r.float_pnl / r.investment * 100:>9.2f}"
            f"{-r.fees:>9.1f}{r.funding:>9.1f}{r.max_dd_pct:>8.2f}"
            f"{r.trades:>7}{r.time_in_range_pct:>10.1f}{r.bh_ret_pct:>9.2f}"
        )

    if args.json_out:
        with open(args.json_out, "w") as fh:
            json.dump(
                [{k: v for k, v in r.__dict__.items() if k != "equity"} for r in rows],
                fh,
                indent=1,
            )


if __name__ == "__main__":
    main()
