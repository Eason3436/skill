"""Signal layer for the MA-reversion (均線回歸) strategy.

Trading idea
------------
During the Taipei 08:00-16:00 window (US 20:00-04:00 ET) MU's tokenised perp has
no cash-session order flow behind it.  Moves are dominated by thin-book noise
rather than information, so price that has stretched away from its short-term
mean tends to come back to it.  We fade the stretch and target the mean.

The filters exist because that edge disappears in exactly two regimes: when a
genuine trend is running (earnings, macro prints, US futures gapping) and when
volatility is so low that the spread eats the whole move.

Every rule is written once, vectorised over a DataFrame.  `signal_now()` runs
the same code on the tail of a live candle feed, so a live bot and the
backtester cannot drift apart.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LONG, SHORT, FLAT = 1, -1, 0

# Exit reason codes (ints so the backtest loop can stay in numpy land)
EXIT_NONE, EXIT_TARGET, EXIT_ZSTOP, EXIT_SESSION = 0, 1, 2, 3
EXIT_STOP, EXIT_TIME = 4, 5
EXIT_NAMES = {
    EXIT_TARGET: "target",
    EXIT_ZSTOP: "z_stop",
    EXIT_SESSION: "session_close",
    EXIT_STOP: "stop",
    EXIT_TIME: "time_stop",
}

DEFAULT_PARAMS: dict = {
    # ---- data -------------------------------------------------------------
    "inst": "MU-USDT-SWAP",
    "bar": "5m",
    "tick_size": 0.01,
    "lot_size": 0.01,

    # ---- session (Taipei local time, UTC+8, no DST) -----------------------
    "session_start_hour": 8,
    "session_end_hour": 16,

    # ---- features ---------------------------------------------------------
    "ma_type": "sma",
    "ma_len": 48,          # 48 x 5m = 4h anchor
    "atr_len": 14,
    "slope_len": 12,
    "regime_win": 2016,    # ~1 week of 5m bars for the volatility percentile

    # ---- entry ------------------------------------------------------------
    # "first_touch" takes the bar where z *crosses* the band, one trade per
    # stretch. That is the event the edge was measured on, and it also stops the
    # strategy re-entering over and over inside a single move.
    "entry_mode": "first_touch",   # "first_touch" | "level"
    "z_entry": 2.5,        # fade once price is 2.5 sigma from the anchor
    "require_turn": False,  # "level" mode only: wait for z to stop getting worse
    "max_slope": 1.5,      # |MA drift over slope_len| in ATR; above this, stand aside
    "vol_rank_min": 0.10,  # skip dead tape (spread dominates)
    "vol_rank_max": 0.95,  # skip news-driven blowouts
    "min_bars_left": 6,    # don't open a trade with <30m of session left
    "allow_long": True,
    "allow_short": True,

    # ---- exit -------------------------------------------------------------
    # Distances are measured in sigma (the same rolling sd that defines z), not
    # in ATR: at this instrument sd ~ 1.8x ATR, so an ATR-scaled stop is far
    # tighter than the deviation being faded and gets swept as a matter of
    # course.
    "exit_mode": "sd",     # "sd" = fixed price targets | "z" = revert-to-anchor
    "tp_sd": 1.0,          # take profit at entry +/- tp_sd * sigma
    "stop_sd": 1.5,        # hard stop at entry -/+ stop_sd * sigma
    "z_exit": 0.3,         # exit_mode="z": close once price is within 0.3 sigma of the MA
    "z_stop": 4.5,         # structural stop: the stretch just kept stretching
    "max_hold_bars": 36,   # 3h time stop
    # the session close always flattens

    # ---- execution --------------------------------------------------------
    # Fading a stretch is a liquidity-providing trade, so the entry and the
    # profit target rest as limit orders and pay the maker fee; only the stop
    # and the forced session-close exit cross the spread. At 5bps taker + 3bps
    # slippage a round trip costs ~0.39 sigma on this instrument, which alone
    # makes a 1-sigma target unwinnable.
    "entry_exec": "limit",     # "limit" (maker) | "market" (taker, next open)
    "entry_limit_ttl": 3,      # bars the resting entry order stays live
    "entry_limit_offset_ticks": 1,  # rest one tick on the passive side of the close
    "maker_bps": 2.0,          # OKX perp maker, per side
    "taker_bps": 5.0,          # OKX perp taker, per side
    "slip_bps": 3.0,           # spread + impact, taker fills only
    "risk_pct": 0.75,      # equity risked per trade, in %
    "max_leverage": 3.0,
    "init_equity": 10_000.0,
}


def compute_signals(df: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Add `entry_sig` and the close-of-bar exit flags.

    All columns are causal: bar *t* uses data up to bar *t*'s close only.
    """
    out = df.copy()
    z = out["z"]
    z_prev = z.shift(1)

    regime = (
        out["in_session"]
        & (out["bars_left"] >= p["min_bars_left"])
        & out[["z", "atr", "atr_pct_rank", "slope_n"]].notna().all(axis=1)
        & (out["slope_n"].abs() <= p["max_slope"])
        & (out["atr_pct_rank"] >= p["vol_rank_min"])
        & (out["atr_pct_rank"] <= p["vol_rank_max"])
    )

    ze = p["z_entry"]
    if p["entry_mode"] == "first_touch":
        # The band crossing itself. `require_turn` is meaningless here — at the
        # moment of the cross z is by construction still moving away.
        cross_l = (z <= -ze) & (z_prev > -ze)
        cross_s = (z >= ze) & (z_prev < ze)
    else:
        turn_up = (z > z_prev) if p["require_turn"] else pd.Series(True, index=out.index)
        turn_dn = (z < z_prev) if p["require_turn"] else pd.Series(True, index=out.index)
        cross_l = (z <= -ze) & turn_up.fillna(False)
        cross_s = (z >= ze) & turn_dn.fillna(False)

    long_in = regime & cross_l.fillna(False) & (z > -p["z_stop"])
    short_in = regime & cross_s.fillna(False) & (z < p["z_stop"])
    if not p["allow_long"]:
        long_in &= False
    if not p["allow_short"]:
        short_in &= False

    out["entry_sig"] = np.select([long_in, short_in], [LONG, SHORT], default=FLAT)

    # Close-of-bar exits, per side. Priority: session close > target > z_stop.
    # In "sd" mode the profit target is a price level handled intrabar by the
    # backtester, so only the structural z_stop survives here.
    leaving = (~out["in_session"]) | out["session_last_bar"]
    tgt_l = (z >= -p["z_exit"]) if p["exit_mode"] == "z" else pd.Series(False, index=out.index)
    tgt_s = (z <= p["z_exit"]) if p["exit_mode"] == "z" else pd.Series(False, index=out.index)
    out["exit_long"] = np.select(
        [leaving, tgt_l, z <= -p["z_stop"]],
        [EXIT_SESSION, EXIT_TARGET, EXIT_ZSTOP],
        default=EXIT_NONE,
    )
    out["exit_short"] = np.select(
        [leaving, tgt_s, z >= p["z_stop"]],
        [EXIT_SESSION, EXIT_TARGET, EXIT_ZSTOP],
        default=EXIT_NONE,
    )
    # A NaN z must never be read as "reverted to the mean".
    nan_z = z.isna() & ~leaving
    out.loc[nan_z, ["exit_long", "exit_short"]] = EXIT_NONE
    return out


def signal_now(tail: pd.DataFrame, p: dict) -> int:
    """LONG / SHORT / FLAT for the most recent *closed* bar of a live feed.

    `tail` must be a featured frame (see features.add_features) with enough
    history for the rolling windows. Act on the next bar's open.
    """
    return int(compute_signals(tail, p)["entry_sig"].iloc[-1])


def stop_price(entry_px: float, side: int, sigma: float, p: dict) -> float:
    """Hard stop, `stop_sd` sigma against the position."""
    return entry_px - side * p["stop_sd"] * sigma


def target_price(entry_px: float, side: int, sigma: float, p: dict) -> float:
    """Profit target in "sd" exit mode; NaN means "no price target"."""
    if p["exit_mode"] != "sd" or not p.get("tp_sd"):
        return float("nan")
    return entry_px + side * p["tp_sd"] * sigma


def position_size(equity: float, entry_px: float, stop_px: float, p: dict) -> float:
    """Risk-based sizing: a stop-out costs `risk_pct` of equity, leverage-capped."""
    risk_amount = equity * p["risk_pct"] / 100.0
    per_unit = abs(entry_px - stop_px)
    if per_unit <= 0:
        return 0.0
    qty = min(risk_amount / per_unit, equity * p["max_leverage"] / entry_px)
    lot = p["lot_size"]
    return round(int(qty / lot) * lot, 8)
