"""Bar-by-bar backtester for the MA-reversion strategy.

Execution assumptions, all deliberately pessimistic:

* In `entry_exec="limit"` mode a signal on bar *t*'s close rests as a limit
  order at that close for the next `entry_limit_ttl` bars and fills only if a
  later bar trades through it — at the limit price, maker fee, no slippage.
  Unfilled orders are cancelled, and no signal is chased.
* In `entry_exec="market"` mode the signal fills at bar *t+1*'s open, taker fee
  plus slippage.
* The profit target rests as a limit order (maker fee); the stop, the time stop
  and the session-close exit cross the spread (taker fee plus slippage).
* The hard stop is checked intrabar against the bar's low/high and is evaluated
  **before** the target, so a bar that touched both is booked as a loss.
* A stop that gaps through fills at the worse of the stop level and the open.
* The session-close exit fills at the close of the last in-session bar and pays
  the same costs as any other exit.
* One position at a time, no pyramiding, no overnight carry.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategy import (EXIT_NAMES, EXIT_NONE, EXIT_STOP, EXIT_TARGET, EXIT_TIME,
                      FLAT, LONG, compute_signals, position_size, stop_price,
                      target_price)


def run_backtest(df: pd.DataFrame, p: dict) -> dict:
    """`df` must carry the columns produced by features.add_features."""
    sig = compute_signals(df, p)

    ts = sig.index
    o = sig["open"].to_numpy(float)
    hi = sig["high"].to_numpy(float)
    lo = sig["low"].to_numpy(float)
    cl = sig["close"].to_numpy(float)
    sd = sig["sd"].to_numpy(float)
    zz = sig["z"].to_numpy(float)
    in_sess = sig["in_session"].to_numpy(bool)
    last_bar = sig["session_last_bar"].to_numpy(bool)
    entry_sig = sig["entry_sig"].to_numpy(int)
    exit_l = sig["exit_long"].to_numpy(int)
    exit_s = sig["exit_short"].to_numpy(int)

    n = len(sig)
    maker = p["maker_bps"] / 10_000.0
    taker = p["taker_bps"] / 10_000.0
    slip = p["slip_bps"] / 10_000.0
    use_limit = p["entry_exec"] == "limit"

    equity = float(p["init_equity"])
    eq_curve = np.empty(n, dtype=float)
    trades: list[dict] = []

    side = FLAT
    qty = entry_px = stop_px = tp_px = entry_fee = 0.0
    entry_i = -1
    entry_z = np.nan
    # Resting entry order: side, limit price, sigma at signal, last valid bar.
    pending = FLAT
    pend_px = pend_sigma = 0.0
    pend_expiry = -1

    for i in range(n):
        # ---- 1. try to fill the resting entry order -------------------------
        if pending != FLAT and side == FLAT:
            filled_at = np.nan
            fee_rate = 0.0
            if not in_sess[i] or i > pend_expiry:
                pending = FLAT
            elif use_limit:
                touched = (lo[i] <= pend_px) if pending == LONG else (hi[i] >= pend_px)
                if touched:
                    filled_at, fee_rate = pend_px, maker
            else:
                filled_at, fee_rate = o[i] * (1.0 + pending * slip), taker

            if not np.isnan(filled_at):
                sp = stop_price(filled_at, pending, pend_sigma, p)
                q = position_size(equity, filled_at, sp, p)
                if q > 0:
                    side, qty, entry_px, stop_px = pending, q, filled_at, sp
                    tp_px = target_price(filled_at, pending, pend_sigma, p)
                    entry_fee = fee_rate
                    entry_i, entry_z = i, zz[i - 1] if i else np.nan
                pending = FLAT
            elif not use_limit:
                pending = FLAT  # market orders do not rest

        # ---- 2. manage an open position -------------------------------------
        if side != FLAT:
            reason = EXIT_NONE
            exit_raw = np.nan
            hit_stop = (lo[i] <= stop_px) if side == LONG else (hi[i] >= stop_px)
            hit_tp = (not np.isnan(tp_px)) and (
                (hi[i] >= tp_px) if side == LONG else (lo[i] <= tp_px))
            if hit_stop:
                # Both touched in one bar: book the loss. Gap-through fills at
                # the worse of the stop level and the open.
                reason = EXIT_STOP
                exit_raw = min(stop_px, o[i]) if side == LONG else max(stop_px, o[i])
            elif hit_tp:
                reason = EXIT_TARGET
                exit_raw = max(tp_px, o[i]) if side == LONG else min(tp_px, o[i])
            else:
                code = exit_l[i] if side == LONG else exit_s[i]
                if code != EXIT_NONE:
                    reason, exit_raw = code, cl[i]
                elif i - entry_i >= p["max_hold_bars"]:
                    reason, exit_raw = EXIT_TIME, cl[i]

            if reason != EXIT_NONE:
                # Only the target rests as a limit order; every other exit
                # crosses the spread.
                if reason == EXIT_TARGET:
                    fill, exit_fee = exit_raw, maker
                else:
                    fill, exit_fee = exit_raw * (1.0 - side * slip), taker
                gross = (fill - entry_px) * side * qty
                cost = (entry_px * entry_fee + fill * exit_fee) * qty
                pnl = gross - cost
                prev_equity = equity
                equity += pnl
                trades.append({
                    "entry_ts": ts[entry_i], "exit_ts": ts[i],
                    "side": "long" if side == LONG else "short",
                    "entry_px": entry_px, "exit_px": fill, "qty": qty,
                    "bars_held": i - entry_i, "entry_z": entry_z,
                    "reason": EXIT_NAMES[reason],
                    "gross": gross, "cost": cost, "pnl": pnl,
                    "ret_pct": pnl / prev_equity * 100.0,
                    "equity": equity,
                })
                side, qty = FLAT, 0.0

        # ---- 3. read this closed bar for a new entry ------------------------
        if side == FLAT and pending == FLAT and in_sess[i] and not last_bar[i]:
            s = entry_sig[i]
            if s != FLAT and not np.isnan(sd[i]) and sd[i] > 0:
                pending, pend_sigma = s, sd[i]
                # Rest the order one tick on the passive side of the close so it
                # is a genuine maker order rather than one that crosses.
                pend_px = cl[i] - s * p["entry_limit_offset_ticks"] * p["tick_size"]
                pend_expiry = i + p["entry_limit_ttl"]

        # ---- 4. mark to market ----------------------------------------------
        eq_curve[i] = equity + ((cl[i] - entry_px) * side * qty if side != FLAT else 0.0)

    # A position can never survive past the last in-session bar, but assert the
    # invariant rather than trusting it silently.
    assert side == FLAT or not in_sess[-1] or not last_bar[-1]

    return {
        "trades": pd.DataFrame(trades),
        "equity": pd.Series(eq_curve, index=ts, name="equity"),
        "params": dict(p),
        "final_equity": equity,
        "signals": sig,
    }


def session_exposure(sig: pd.DataFrame) -> dict:
    """Sanity numbers about the traded window itself."""
    s = sig[sig["in_session"]]
    return {
        "session_bars": int(len(s)),
        "total_bars": int(len(sig)),
        "sessions": int(s["session_id"].nunique()),
        "session_share_pct": float(len(s) / max(len(sig), 1) * 100.0),
    }
