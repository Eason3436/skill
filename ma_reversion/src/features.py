"""Indicator / feature construction for the MA-reversion strategy.

Everything here is causal: every column at bar *t* is computable from data up to
and including bar *t*'s close.  The backtester never acts on bar *t* before bar
*t+1*'s open, so there is no lookahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TAIPEI = "Asia/Taipei"


def load_candles(path: str) -> pd.DataFrame:
    """Read a CSV written by fetch_data.py into a UTC-indexed OHLCV frame."""
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("ts").sort_index()
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Drop the still-forming last bar (confirm == 0) so the backtest only ever
    # sees closed candles.
    if "confirm" in df.columns:
        df = df[pd.to_numeric(df["confirm"], errors="coerce").fillna(1) == 1]
    df = df[~df.index.duplicated(keep="last")]
    return df[["open", "high", "low", "close", "volume"]].dropna()


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    # Wilder smoothing
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def mark_session(df: pd.DataFrame, start_hour: int, end_hour: int,
                 weekdays: tuple[int, ...] = (0, 1, 2, 3, 4)) -> pd.DataFrame:
    """Tag the Taipei-time trading window.

    Taipei 08:00-16:00 (UTC+8, no DST) == US 20:00-04:00 ET, i.e. the overnight
    session that runs from the US after-hours close through to the European
    morning.  Taipei Mon-Fri maps to ET Sun 20:00 - Fri 04:00, so Taipei
    weekends are excluded: Taipei Sat 08:00 is Fri 20:00 ET, after the US week
    has closed.
    """
    out = df.copy()
    local = out.index.tz_convert(TAIPEI)
    out["tpe_hour"] = local.hour
    out["tpe_dow"] = local.dayofweek

    hours = np.asarray(local.hour)
    in_win = (hours >= start_hour) & (hours < end_hour) if start_hour < end_hour \
        else (hours >= start_hour) | (hours < end_hour)  # window wrapping midnight
    out["in_session"] = in_win & np.isin(np.asarray(local.dayofweek), weekdays)

    # Session id groups the bars of one Taipei window. A wrapped window is
    # anchored to the date its *start* hour belongs to, so the pre- and
    # post-midnight halves stay in one group.
    naive = local.tz_localize(None)
    anchor = naive - pd.Timedelta(days=1) if start_hour >= end_hour else naive
    day = np.where(
        (start_hour >= end_hour) & (hours < end_hour),
        np.asarray(anchor.normalize().astype(str), dtype=object),
        np.asarray(naive.normalize().astype(str), dtype=object),
    )
    out["session_id"] = np.where(out["in_session"], day, "")

    # Bars remaining in the current session, used both for "don't open a trade
    # we cannot manage" and for the forced flat at the window close.
    #
    # Derived from the clock rather than by counting rows to the end of the
    # frame: live, the newest bar is always the last row, and a row count would
    # report zero bars left and veto every entry.
    step = pd.Timedelta(np.median(np.diff(out.index.values)))
    end_of_day = naive.normalize() + pd.Timedelta(hours=end_hour)
    if start_hour >= end_hour:
        end_of_day = np.where(hours >= start_hour,
                              end_of_day + pd.Timedelta(days=1), end_of_day)
        end_of_day = pd.DatetimeIndex(end_of_day)
    remaining = (end_of_day - (naive + step)) // step
    out["bars_left"] = np.where(out["in_session"], np.asarray(remaining), -1).astype(int)
    out["session_last_bar"] = out["in_session"] & (out["bars_left"] == 0)
    return out


def add_features(df: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Attach the reversion features.

    ma      - the anchor the price is expected to revert to
    z       - standardised distance from that anchor (the actual signal)
    atr_pct - volatility regime, used to skip dead and berserk nights
    slope_n - normalised MA slope, used to stand aside in a strong trend
    """
    out = df.copy()
    n = p["ma_len"]

    out["ma"] = out["close"].rolling(n, min_periods=n).mean() if p.get("ma_type", "sma") == "sma" \
        else out["close"].ewm(span=n, adjust=False, min_periods=n).mean()

    dev = out["close"] - out["ma"]
    out["dev"] = dev
    out["sd"] = dev.rolling(n, min_periods=n).std(ddof=0)
    out["z"] = (dev / out["sd"]).replace([np.inf, -np.inf], np.nan)

    out["atr"] = atr(out, p["atr_len"])
    out["atr_pct"] = out["atr"] / out["close"] * 100.0

    s = p["slope_len"]
    # MA drift over `slope_len` bars, expressed in ATR so it is comparable
    # across price levels and volatility regimes.
    out["slope_n"] = (out["ma"] - out["ma"].shift(s)) / out["atr"]

    # Rolling volatility percentile gives a self-calibrating regime filter that
    # does not need re-tuning when MU's absolute volatility drifts.
    win = p.get("regime_win", 2016)  # ~1 week of 5m bars
    out["atr_pct_rank"] = out["atr_pct"].rolling(win, min_periods=win // 4).rank(pct=True)

    out = mark_session(out, p["session_start_hour"], p["session_end_hour"])
    return out
