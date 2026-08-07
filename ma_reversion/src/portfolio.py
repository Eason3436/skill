#!/usr/bin/env python3
"""Trade the night-session reversion signal across many instruments at once.

The cross-instrument test said two things: the signal is real everywhere
(session-clustered t of +4.92 over 14 unseen names) but a single name is a thin,
lumpy way to harvest it. A portfolio is the natural response - the same 59% win
rate spread over several independent-ish bets instead of one.

Three things make this more than "run the backtest N times and add up":

1. **Shared capital.** Risk per trade is a fraction of *total* equity, and the
   book is capped on concurrent positions and gross notional. Summing N
   single-instrument backtests silently assumes N times the capital.

2. **A causal universe screen.** An instrument is eligible only while its
   trailing sigma clears a threshold, measured over a lagged window so the
   screen never uses information the strategy did not have. The threshold can be
   set directly (`min_sigma_pct`) or derived from the fee (`max_cost_sd`).
   Holding the two apart matters: tying the threshold to the fee makes a fee cut
   silently widen the universe, and the measured effects are nothing alike -
   cutting the maker fee 4x is worth about +0.13 Sharpe, while moving the
   threshold from 0.25% to 0.45% is worth more than 3. The screen earns its
   keep by selecting instruments, not by saving fees.

3. **Correlation honesty.** These names move together, so k simultaneous longs
   are not k independent bets. `max_same_side` caps directional pile-up, and the
   report prints realised concurrency and the share of bars where the book was
   one-way, so the diversification claim can be checked rather than assumed.

    python src/portfolio.py --params config/params_15m.json \
        --instruments MU NVDA AAPL ... --max-concurrent 4
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from features import add_features
from features import load_candles
from metrics import breakdowns, summarize
from strategy import (DEFAULT_PARAMS, EXIT_NAMES, EXIT_NONE, EXIT_STOP, EXIT_TARGET,
                      EXIT_TIME, FLAT, LONG, compute_signals, stop_price, target_price)

ROOT = Path(__file__).resolve().parents[1]

PORTFOLIO_DEFAULTS = {
    "max_concurrent": 4,        # positions open at once, across all names
    "max_same_side": 3,         # of those, how many may point the same way
    "max_gross_leverage": 3.0,  # total notional / equity
    "max_cost_sd": 0.08,        # eligibility: maker round trip, in sigma
    "screen_sessions": 20,      # trailing window for the sigma estimate
    "min_sigma_pct": None,      # absolute override for the eligibility threshold
}


def min_sigma_pct(p: dict, pf: dict) -> float:
    """Eligibility threshold on trailing sigma, as a percentage of price.

    By default it is derived from the fee: cost_sd = 2*maker_bps/1e4*100/sigma,
    so budgeting `max_cost_sd` sigma for a round trip pins the threshold with no
    fitted constant. `min_sigma_pct` overrides it with an absolute level, which
    is what lets the fee effect and the selection effect be varied separately -
    tying them together makes a fee cut silently loosen the screen.
    """
    if pf.get("min_sigma_pct"):
        return float(pf["min_sigma_pct"])
    return (2 * p["maker_bps"] / 10_000.0 * 100) / pf["max_cost_sd"]


def sigma_screen(feat: pd.DataFrame, p: dict, pf: dict) -> pd.Series:
    """Causal eligibility mask, using only lagged information."""
    sigma_pct = feat["sd"] / feat["close"] * 100.0
    bars = max(int(pf["screen_sessions"]) * _session_bars(feat), 50)
    trailing = sigma_pct.rolling(bars, min_periods=bars // 4).median().shift(1)
    return (trailing >= min_sigma_pct(p, pf)).fillna(False)


def _session_bars(feat: pd.DataFrame) -> int:
    if not feat["in_session"].any():
        return 32
    counts = feat[feat["in_session"]].groupby("session_id").size()
    return int(counts.median())


def prepare(symbols: list[str], p: dict, pf: dict, datadir: Path) -> dict[str, pd.DataFrame]:
    """Featured, signalled frame per instrument, plus the eligibility column."""
    out = {}
    for sym in symbols:
        path = datadir / f"{sym}-USDT-SWAP_{p['bar']}.csv"
        if not path.exists():
            path = path.with_suffix(".csv.gz")
        if not path.exists():
            print(f"  {sym}: no data, skipped")
            continue
        feat = add_features(load_candles(str(path)), p)
        sig = compute_signals(feat, p)
        sig["eligible"] = sigma_screen(sig, p, pf)
        out[sym] = sig
    return out


def run_portfolio(books: dict[str, pd.DataFrame], p: dict, pf: dict) -> dict:
    """One shared-equity walk over the union of all instrument timestamps."""
    index = sorted(set().union(*(b.index for b in books.values())))
    index = pd.DatetimeIndex(index)

    cols = ["open", "high", "low", "close", "sd", "z", "in_session",
            "session_last_bar", "entry_sig", "exit_long", "exit_short", "eligible"]
    arr = {sym: {c: b[c].reindex(index).to_numpy() for c in cols} for sym, b in books.items()}
    present = {sym: pd.Series(True, index=b.index).reindex(index, fill_value=False).to_numpy()
               for sym, b in books.items()}

    maker = p["maker_bps"] / 10_000.0
    taker = p["taker_bps"] / 10_000.0
    slip = p["slip_bps"] / 10_000.0
    lot = p["lot_size"]

    equity = float(p["init_equity"])
    eq_curve = np.empty(len(index), dtype=float)
    concurrency = np.zeros(len(index), dtype=int)
    one_way = np.zeros(len(index), dtype=bool)
    trades: list[dict] = []

    pos: dict[str, dict] = {}        # open positions, keyed by symbol
    pending: dict[str, dict] = {}    # resting entry orders

    def open_notional() -> float:
        return sum(abs(v["qty"]) * v["last"] for v in pos.values())

    for i, ts in enumerate(index):
        # ---- 1. resting entries ------------------------------------------
        for sym in list(pending):
            if sym in pos:
                pending.pop(sym, None)
                continue
            a = arr[sym]
            if not present[sym][i]:
                continue
            o = pending[sym]
            if not a["in_session"][i] or i > o["expiry"]:
                pending.pop(sym)
                continue
            side = o["side"]
            touched = (a["low"][i] <= o["px"]) if side == LONG else (a["high"][i] >= o["px"])
            if not touched:
                continue

            # Book-level admission, re-checked at fill time rather than at
            # signal time: the book may have filled up while the order rested.
            same_side = sum(1 for v in pos.values() if v["side"] == side)
            if len(pos) >= pf["max_concurrent"] or same_side >= pf["max_same_side"]:
                pending.pop(sym)
                continue

            fill = o["px"]
            sp = stop_price(fill, side, o["sigma"], p)
            risk_amount = equity * p["risk_pct"] / 100.0
            per_unit = abs(fill - sp)
            if per_unit <= 0:
                pending.pop(sym)
                continue
            qty = risk_amount / per_unit
            room = max(0.0, equity * pf["max_gross_leverage"] - open_notional())
            qty = min(qty, room / fill, equity * p["max_leverage"] / fill)
            qty = round(int(qty / lot) * lot, 8)
            if qty <= 0:
                pending.pop(sym)
                continue

            pos[sym] = {"side": side, "qty": qty, "entry_px": fill, "stop_px": sp,
                        "tp_px": target_price(fill, side, o["sigma"], p),
                        "entry_i": i, "entry_ts": ts, "entry_z": o["z"],
                        "entry_fee": maker, "last": fill}
            pending.pop(sym)

        # ---- 2. manage open positions --------------------------------------
        for sym in list(pos):
            a = arr[sym]
            if not present[sym][i]:
                continue
            v = pos[sym]
            side = v["side"]
            v["last"] = a["close"][i]
            reason, raw = EXIT_NONE, np.nan

            hit_stop = (a["low"][i] <= v["stop_px"]) if side == LONG else (a["high"][i] >= v["stop_px"])
            hit_tp = (not np.isnan(v["tp_px"])) and (
                (a["high"][i] >= v["tp_px"]) if side == LONG else (a["low"][i] <= v["tp_px"]))
            if hit_stop:
                reason = EXIT_STOP
                raw = min(v["stop_px"], a["open"][i]) if side == LONG else max(v["stop_px"], a["open"][i])
            elif hit_tp:
                reason = EXIT_TARGET
                raw = max(v["tp_px"], a["open"][i]) if side == LONG else min(v["tp_px"], a["open"][i])
            else:
                code = a["exit_long"][i] if side == LONG else a["exit_short"][i]
                if code != EXIT_NONE:
                    reason, raw = int(code), a["close"][i]
                elif i - v["entry_i"] >= p["max_hold_bars"]:
                    reason, raw = EXIT_TIME, a["close"][i]

            if reason != EXIT_NONE:
                if reason == EXIT_TARGET:
                    fill, exit_fee = raw, maker
                else:
                    fill, exit_fee = raw * (1.0 - side * slip), taker
                gross = (fill - v["entry_px"]) * side * v["qty"]
                cost = (v["entry_px"] * v["entry_fee"] + fill * exit_fee) * v["qty"]
                pnl = gross - cost
                prev_equity = equity
                equity += pnl
                trades.append({
                    "symbol": sym, "entry_ts": v["entry_ts"], "exit_ts": ts,
                    "side": "long" if side == LONG else "short",
                    "entry_px": v["entry_px"], "exit_px": fill, "qty": v["qty"],
                    "bars_held": i - v["entry_i"], "entry_z": v["entry_z"],
                    "reason": EXIT_NAMES[reason], "gross": gross, "cost": cost,
                    "pnl": pnl, "ret_pct": pnl / prev_equity * 100.0, "equity": equity,
                })
                pos.pop(sym)

        # ---- 3. new signals -------------------------------------------------
        for sym, a in arr.items():
            if sym in pos or sym in pending or not present[sym][i]:
                continue
            if not (a["in_session"][i] and not a["session_last_bar"][i] and a["eligible"][i]):
                continue
            s = int(a["entry_sig"][i])
            if s == FLAT or np.isnan(a["sd"][i]) or a["sd"][i] <= 0:
                continue
            same_side = sum(1 for v in pos.values() if v["side"] == s)
            if len(pos) >= pf["max_concurrent"] or same_side >= pf["max_same_side"]:
                continue
            pending[sym] = {
                "side": s, "sigma": a["sd"][i], "z": a["z"][i],
                "px": a["close"][i] - s * p["entry_limit_offset_ticks"] * p["tick_size"],
                "expiry": i + p["entry_limit_ttl"],
            }

        # ---- 4. mark to market ----------------------------------------------
        unreal = sum((v["last"] - v["entry_px"]) * v["side"] * v["qty"] for v in pos.values())
        eq_curve[i] = equity + unreal
        concurrency[i] = len(pos)
        if pos:
            sides = {v["side"] for v in pos.values()}
            one_way[i] = len(sides) == 1 and len(pos) > 1

    tr = pd.DataFrame(trades)
    return {
        "trades": tr,
        "equity": pd.Series(eq_curve, index=index, name="equity"),
        "params": {**p, **pf},
        "final_equity": equity,
        "concurrency": pd.Series(concurrency, index=index),
        "one_way": pd.Series(one_way, index=index),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=str(ROOT / "config" / "params_15m.json"))
    ap.add_argument("--instruments", nargs="+", required=True)
    ap.add_argument("--datadir", default=str(ROOT / "data"))
    ap.add_argument("--outdir", default=str(ROOT / "results"))
    ap.add_argument("--tag", default="portfolio")
    ap.add_argument("--max-concurrent", type=int, default=None)
    ap.add_argument("--max-same-side", type=int, default=None)
    ap.add_argument("--max-cost-sd", type=float, default=None)
    ap.add_argument("--min-sigma-pct", type=float, default=None,
                    help="absolute eligibility threshold; overrides --max-cost-sd")
    ap.add_argument("--risk-pct", type=float, default=None)
    ap.add_argument("--session-hours", nargs=2, type=int, default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    p = dict(DEFAULT_PARAMS)
    p.update(json.loads(Path(args.params).read_text()))
    if args.session_hours:
        p["session_start_hour"], p["session_end_hour"] = args.session_hours
    if args.risk_pct is not None:
        p["risk_pct"] = args.risk_pct

    pf = dict(PORTFOLIO_DEFAULTS)
    for key, val in (("max_concurrent", args.max_concurrent),
                     ("max_same_side", args.max_same_side),
                     ("max_cost_sd", args.max_cost_sd),
                     ("min_sigma_pct", args.min_sigma_pct)):
        if val is not None:
            pf[key] = val

    books = prepare(args.instruments, p, pf, Path(args.datadir))
    if not books:
        print("no data")
        return 1

    res = run_portfolio(books, p, pf)
    summ = summarize(res)
    tr = res["trades"]

    min_sigma = min_sigma_pct(p, pf)
    print(f"\n=== portfolio: {len(books)} instruments, Taipei "
          f"{p['session_start_hour']:02d}-{p['session_end_hour']:02d}, {p['bar']} ===")
    print(f"  book limits      max {pf['max_concurrent']} open / "
          f"{pf['max_same_side']} same side / {pf['max_gross_leverage']}x gross")
    src = "explicit" if pf.get("min_sigma_pct") else \
        f"cost <= {pf['max_cost_sd']} sigma at {p['maker_bps']}bps maker"
    print(f"  eligibility      trailing sigma >= {min_sigma:.3f}% of price ({src})")
    print(f"  risk per trade   {p['risk_pct']}% of total equity\n")
    for k in ("trades", "trades_per_week", "total_return_pct", "cagr_pct", "sharpe",
              "sortino", "max_dd_pct", "calmar", "win_rate_pct", "profit_factor",
              "expectancy", "max_consec_losses", "cost_pct_of_gross", "final_equity"):
        if k in summ:
            v = summ[k]
            print(f"  {k:<20} {v:,.2f}" if isinstance(v, float) else f"  {k:<20} {v}")

    conc = res["concurrency"]
    busy = conc[conc > 0]
    print(f"\n  bars with a position  {len(busy) / len(conc) * 100:.1f}%")
    if len(busy):
        print(f"  mean open positions   {busy.mean():.2f} (max {int(conc.max())})")
        print(f"  one-way book          {res['one_way'].sum() / max(len(busy), 1) * 100:.1f}% "
              f"of active bars (correlation check)")
    if not tr.empty:
        per_sym = tr.groupby("symbol").agg(n=("pnl", "size"), pnl=("pnl", "sum"),
                                           win=("pnl", lambda s: (s > 0).mean() * 100)).round(2)
        print("\n  per instrument:")
        print(per_sym.sort_values("pnl", ascending=False).to_string())
        r = tr["ret_pct"].to_numpy()
        print(f"\n  per-trade t      {r.mean() / r.std() * np.sqrt(len(r)):+.2f}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if not tr.empty:
        tr.to_csv(outdir / f"{args.tag}_trades.csv", index=False)
    (outdir / f"{args.tag}_summary.json").write_text(json.dumps(summ, indent=2, default=str))
    for name, frame in breakdowns(res).items():
        frame.to_csv(outdir / f"{args.tag}_{name}.csv")
    print(f"\nwrote {outdir}/{args.tag}_*")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
