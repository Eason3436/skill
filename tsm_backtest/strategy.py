"""TSM weekend Bollinger-band backtest engine.

Strategy (fixed rules from the spec)
------------------------------------
* Instrument : TSM tokenized-stock product (spot token or perpetual)
* Timeframe  : 30-minute candles
* Bands      : Bollinger, 20-period SMA of close +/- 2.5 * std(close)
* Sessions   : trade Saturday & Sunday only
* Entry      : if bar.low  <= lower band  -> buy at the lower band price
* Exit       : if bar.high >= upper band  -> sell at the upper band price
* Force close: at the weekend's last bar (Sunday 23:30 in the chosen tz) close
               any open position at that bar's close, so nothing is held across
               the week.
* Stop loss  : none
* Sizing     : full position each trade, no pyramiding (compounded equity)

Modelling choices (documented, all configurable)
------------------------------------------------
* Bollinger bands are computed over the *continuous* 30m series (weekday bars
  included) so the 20-period window is always well formed; trades are only
  taken on weekend bars.
* Population standard deviation (ddof=0) — matches TradingView's default.
* If a weekend bar's low touches the lower band *and* its high reaches the
  upper band, entry is evaluated first and the same bar may also exit
  (a full-band winning round-trip).  Intrabar touch order is unknown; this is
  the conventional optimistic fill for band mean-reversion tests.
* After a natural exit inside a weekend, a fresh entry is allowed if price
  touches the lower band again.
* USDT-perp price is treated as USD; a trade buys ``equity / entry`` units with
  no leverage, so trade return == (exit - entry) / entry.  Fees default to 0
  (spec lists none) but are configurable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class Trade:
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    exit_reason: str          # "band" (natural, hit upper) | "forced" (Sun close)
    weekend: str              # ISO date of the Saturday that opens the weekend
    equity_before: float
    equity_after: float
    fee_paid: float

    @property
    def ret_pct(self) -> float:
        return (self.exit_price - self.entry_price) / self.entry_price * 100.0

    @property
    def pnl_usd(self) -> float:
        return self.equity_after - self.equity_before


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity_curve: pd.DataFrame          # index=bar ts, column 'equity'
    weekly: pd.DataFrame                # per-weekend breakdown
    start_equity: float
    end_equity: float
    max_drawdown_pct: float
    max_drawdown_date: Optional[pd.Timestamp]
    bar_count: int
    data_start: Optional[pd.Timestamp]
    data_end: Optional[pd.Timestamp]

    @property
    def total_return_pct(self) -> float:
        return (self.end_equity / self.start_equity - 1.0) * 100.0


def add_bollinger(df: pd.DataFrame, period: int = 20, mult: float = 2.5) -> pd.DataFrame:
    out = df.copy()
    ma = out["close"].rolling(period).mean()
    sd = out["close"].rolling(period).std(ddof=0)
    out["bb_mid"] = ma
    out["bb_upper"] = ma + mult * sd
    out["bb_lower"] = ma - mult * sd
    return out


def _weekend_key(ts: pd.Timestamp) -> Optional[str]:
    """Return the Saturday-date label of the weekend a bar belongs to.

    Saturday keeps its own date; Sunday maps back to the preceding Saturday so
    both weekend days share one key.  Weekdays return ``None``.
    """
    wd = ts.weekday()  # Mon=0 .. Sat=5, Sun=6
    if wd == 5:
        return ts.date().isoformat()
    if wd == 6:
        return (ts - pd.Timedelta(days=1)).date().isoformat()
    return None


def run_backtest(
    df: pd.DataFrame,
    *,
    start_equity: float = 10_000.0,
    period: int = 20,
    mult: float = 2.5,
    tz: str = "UTC",
    fee_rate: float = 0.0,
    forced_close_hm: tuple[int, int] = (23, 30),
    allow_same_bar_exit: bool = True,
) -> BacktestResult:
    """Run the weekend Bollinger backtest over a 30m OHLCV frame."""
    if df.empty:
        raise ValueError("no data to backtest")

    df = add_bollinger(df, period, mult)
    local = df.tz_convert(tz)

    # Weekend label per bar (None on weekdays).  Kept as a plain positional
    # list — assigning None into a DataFrame column coerces it to NaN, which
    # would defeat the ``is not None`` weekend guard below.
    keys = [_weekend_key(t) for t in local.index]
    fc_h, fc_m = forced_close_hm

    # For each weekend, find the timestamp of its last bar (the forced-close bar).
    last_bar_of_weekend: dict[str, pd.Timestamp] = {}
    for t, k in zip(local.index, keys):
        if k is None:
            continue
        # Prefer an exact Sunday HH:MM bar; otherwise the chronologically last.
        if k not in last_bar_of_weekend or t > last_bar_of_weekend[k]:
            last_bar_of_weekend[k] = t
    # If a Sunday 23:30 bar exists, use it explicitly as the forced-close bar.
    for t, k in zip(local.index, keys):
        if k is not None and t.weekday() == 6 and t.hour == fc_h and t.minute == fc_m:
            last_bar_of_weekend[k] = t

    equity = start_equity
    position: Optional[dict] = None      # {'qty', 'entry_price', 'entry_time', 'equity_before'}
    trades: list[Trade] = []
    equity_curve: list[tuple[pd.Timestamp, float]] = []

    for i, t in enumerate(local.index):
        row = local.iloc[i]
        wkey = keys[i]
        upper, lower = row["bb_upper"], row["bb_lower"]
        bands_ready = not (np.isnan(upper) or np.isnan(lower))

        if wkey is not None and bands_ready:
            # 1) Entry: flat and low pierces the lower band.
            entered_this_bar = False
            if position is None and row["low"] <= lower:
                entry_price = float(lower)
                fee_in = equity * fee_rate
                invest = equity - fee_in
                qty = invest / entry_price
                position = {
                    "qty": qty,
                    "entry_price": entry_price,
                    "entry_time": t,
                    "equity_before": equity,
                    "fee_in": fee_in,
                    "weekend": wkey,
                }
                entered_this_bar = True

            # 2) Natural exit: in position and high reaches the upper band.
            #    May be the same bar we just entered on unless disallowed.
            if (position is not None and row["high"] >= upper
                    and (allow_same_bar_exit or not entered_this_bar)):
                exit_price = float(upper)
                gross = position["qty"] * exit_price
                fee_out = gross * fee_rate
                new_equity = gross - fee_out
                trades.append(Trade(
                    entry_time=position["entry_time"], entry_price=position["entry_price"],
                    exit_time=t, exit_price=exit_price, exit_reason="band",
                    weekend=position["weekend"], equity_before=position["equity_before"],
                    equity_after=new_equity, fee_paid=position["fee_in"] + fee_out,
                ))
                equity = new_equity
                position = None

            # 3) Forced close on the weekend's last bar, at that bar's close.
            if position is not None and last_bar_of_weekend.get(wkey) == t:
                exit_price = float(row["close"])
                gross = position["qty"] * exit_price
                fee_out = gross * fee_rate
                new_equity = gross - fee_out
                trades.append(Trade(
                    entry_time=position["entry_time"], entry_price=position["entry_price"],
                    exit_time=t, exit_price=exit_price, exit_reason="forced",
                    weekend=position["weekend"], equity_before=position["equity_before"],
                    equity_after=new_equity, fee_paid=position["fee_in"] + fee_out,
                ))
                equity = new_equity
                position = None

        # Mark-to-market equity for the curve (unrealized at this bar's close).
        if position is not None:
            mtm = position["qty"] * float(row["close"])
        else:
            mtm = equity
        equity_curve.append((t, mtm))

    curve = pd.DataFrame(equity_curve, columns=["timestamp", "equity"]).set_index("timestamp")

    # Max drawdown on the mark-to-market curve.
    running_max = curve["equity"].cummax()
    dd = curve["equity"] / running_max - 1.0
    max_dd_pct = float(dd.min() * 100.0) if len(dd) else 0.0
    max_dd_date = dd.idxmin() if len(dd) else None

    weekly = _weekly_breakdown(trades, start_equity)

    return BacktestResult(
        trades=trades,
        equity_curve=curve,
        weekly=weekly,
        start_equity=start_equity,
        end_equity=equity,
        max_drawdown_pct=max_dd_pct,
        max_drawdown_date=max_dd_date,
        bar_count=len(df),
        data_start=df.index.min() if len(df) else None,
        data_end=df.index.max() if len(df) else None,
    )


def _weekly_breakdown(trades: list[Trade], start_equity: float) -> pd.DataFrame:
    """Aggregate realized trades per weekend into the required weekly table."""
    if not trades:
        return pd.DataFrame(
            columns=["weekend", "n_trades", "pnl_usd", "pnl_pct", "cum_equity"]
        )
    order: list[str] = []
    agg: dict[str, dict] = {}
    for tr in trades:
        wk = tr.weekend
        if wk not in agg:
            agg[wk] = {"n": 0, "pnl": 0.0}
            order.append(wk)
        agg[wk]["n"] += 1
        agg[wk]["pnl"] += tr.pnl_usd

    rows = []
    cum = start_equity
    for wk in order:
        equity_before_week = cum
        pnl = agg[wk]["pnl"]
        cum += pnl
        rows.append({
            "weekend": wk,
            "n_trades": agg[wk]["n"],
            "pnl_usd": pnl,
            "pnl_pct": pnl / equity_before_week * 100.0,
            "cum_equity": cum,
        })
    return pd.DataFrame(rows)


def trade_stats(res: BacktestResult) -> dict:
    trades = res.trades
    n = len(trades)
    if n == 0:
        return {"n_trades": 0}
    rets = [t.ret_pct for t in trades]
    wins = [r for r in rets if r > 0]
    natural = sum(1 for t in trades if t.exit_reason == "band")
    forced = sum(1 for t in trades if t.exit_reason == "forced")
    best = max(trades, key=lambda t: t.ret_pct)
    worst = min(trades, key=lambda t: t.ret_pct)
    return {
        "n_trades": n,
        "n_natural_exit": natural,
        "n_forced_exit": forced,
        "win_rate_pct": len(wins) / n * 100.0,
        "best_trade_pct": best.ret_pct,
        "best_trade": best,
        "worst_trade_pct": worst.ret_pct,
        "worst_trade": worst,
        "avg_trade_pct": float(np.mean(rets)),
    }
