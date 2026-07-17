#!/usr/bin/env python3
"""
OKX off-hours Bollinger-Band mean-reversion backtest.

Strategy (per the request "假日/美股非開盤時段 下軌買入 上軌賣出 30min +-2"):

  * Universe : 4 tokenised US stocks that trade 24/7 on OKX spot:
                 XTSM-USDT, XQQQ-USDT, XMSFT-USDT, XAAPL-USDT
                 (tokenised TSM, QQQ, MSFT, AAPL).
  * Signal   : 30-minute Bollinger Bands, moving-average period 20,
                 upper/lower band = MA +/- 2 * standard deviation.
  * Rules    : long-only mean reversion, each symbol traded independently.
                 - ENTER long when the candle CLOSE <= lower band AND the
                   candle falls in a window where the US stock market is
                   CLOSED (holidays / weekends / pre- & post-market).  This
                   is the whole point of using OKX: the token keeps trading
                   when Nasdaq/NYSE are shut.
                 - EXIT the long when the candle CLOSE >= upper band
                   (take profit at the top band), any time of day.
  * Sizing   : each symbol starts with 1.0 unit of normalised capital and is
                 fully invested on entry (no leverage, no pyramiding).  The
                 "portfolio" total is the equal-weight average of the 4
                 normalised equity curves.
  * Reporting: per-symbol return, combined total return and the maximum
                 drawdown of the combined equity curve, over an 8-week window.

Data source: OKX public REST API (no credentials required).

  IMPORTANT DATA CAVEAT
  ---------------------
  These tokenised-stock instruments were only *listed on OKX on 2026-07-16*,
  so at the time of writing OKX exposes barely one day of 30m candle history.
  A genuine "8 week" backtest therefore cannot be filled today -- the engine
  requests 8 weeks and simply uses whatever history OKX returns.  As days
  accumulate the same command will progressively produce the full 8-week
  result with no code change.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from zoneinfo import ZoneInfo

import requests

OKX_BASE = "https://www.okx.com"
ET = ZoneInfo("America/New_York")

# Default universe: tokenised TSM / QQQ / MSFT / AAPL on OKX spot.
DEFAULT_SYMBOLS = {
    "TSM": "XTSM-USDT",
    "QQQ": "XQQQ-USDT",
    "MSFT": "XMSFT-USDT",
    "AAPL": "XAAPL-USDT",
}

# US equity-market full-day holidays (NYSE/Nasdaq).  Extend as needed; only
# the dates inside the backtest window actually matter.
US_MARKET_HOLIDAYS = {
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # Martin Luther King Jr. Day
    date(2026, 2, 16),  # Washington's Birthday
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day (observed, Jul 4 is a Saturday)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
    # 2025 (in case an 8-week window reaches back into December 2025)
    date(2025, 11, 27),
    date(2025, 12, 25),
}

# US regular session in Eastern Time.
SESSION_OPEN = (9, 30)   # 09:30 ET
SESSION_CLOSE = (16, 0)  # 16:00 ET


# --------------------------------------------------------------------------- #
# Market-hours logic
# --------------------------------------------------------------------------- #
def is_us_market_open(ts_ms: int) -> bool:
    """True if the US regular cash session is open at the given UTC ms time."""
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).astimezone(ET)
    if dt.weekday() >= 5:            # Saturday / Sunday
        return False
    if dt.date() in US_MARKET_HOLIDAYS:
        return False
    minutes = dt.hour * 60 + dt.minute
    open_m = SESSION_OPEN[0] * 60 + SESSION_OPEN[1]
    close_m = SESSION_CLOSE[0] * 60 + SESSION_CLOSE[1]
    return open_m <= minutes < close_m


def is_offhours(ts_ms: int) -> bool:
    """Off-hours = the US market is closed (weekend / holiday / pre-post market)."""
    return not is_us_market_open(ts_ms)


# --------------------------------------------------------------------------- #
# Data fetching
# --------------------------------------------------------------------------- #
def fetch_candles(inst_id: str, bar: str = "30m", weeks: int = 8,
                  session: requests.Session | None = None) -> list[dict]:
    """Fetch up to `weeks` of candles for an instrument, oldest-first.

    Combines the live-candle endpoint with the paginated history endpoint so
    the freshest bar is always included.  Returns dicts sorted ascending by ts.
    """
    sess = session or requests.Session()
    cutoff_ms = int(time.time() * 1000) - weeks * 7 * 24 * 60 * 60 * 1000
    rows: dict[int, dict] = {}

    def ingest(data):
        for c in data:
            ts = int(c[0])
            rows[ts] = {
                "ts": ts,
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "vol": float(c[5]),
            }

    # Most-recent candles (includes the current, not-yet-closed bar).
    r = sess.get(f"{OKX_BASE}/api/v5/market/candles",
                 params={"instId": inst_id, "bar": bar, "limit": "300"},
                 timeout=30)
    r.raise_for_status()
    ingest(r.json().get("data", []))

    # Paginate older history until we pass the cutoff or run out of data.
    after = min(rows) if rows else None
    for _ in range(200):  # hard safety cap
        params = {"instId": inst_id, "bar": bar, "limit": "100"}
        if after is not None:
            params["after"] = str(after)
        r = sess.get(f"{OKX_BASE}/api/v5/market/history-candles",
                     params=params, timeout=30)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            break
        ingest(data)
        after = int(data[-1][0])
        if after <= cutoff_ms:
            break
        time.sleep(0.12)  # be gentle with the public endpoint

    out = [rows[ts] for ts in sorted(rows) if rows[ts]["ts"] >= cutoff_ms]
    return out


# --------------------------------------------------------------------------- #
# Bollinger Bands
# --------------------------------------------------------------------------- #
def add_bollinger(candles: list[dict], period: int, num_std: float) -> None:
    """Attach mid/upper/lower band to each candle in-place (None until warm)."""
    closes = [c["close"] for c in candles]
    for i, c in enumerate(candles):
        if i + 1 < period:
            c["mid"] = c["upper"] = c["lower"] = None
            continue
        window = closes[i + 1 - period: i + 1]
        n = len(window)
        mean = sum(window) / n
        # population standard deviation (matches the classic Bollinger def.)
        var = sum((x - mean) ** 2 for x in window) / n
        sd = var ** 0.5
        c["mid"] = mean
        c["upper"] = mean + num_std * sd
        c["lower"] = mean - num_std * sd


# --------------------------------------------------------------------------- #
# Backtest
# --------------------------------------------------------------------------- #
@dataclass
class Trade:
    entry_ts: int
    entry_px: float
    exit_ts: int | None = None
    exit_px: float | None = None
    ret: float | None = None  # net return incl. fees


@dataclass
class SymbolResult:
    label: str
    inst_id: str
    candles: int
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[int, float]] = field(default_factory=list)
    open_position: bool = False

    @property
    def final_equity(self) -> float:
        return self.equity_curve[-1][1] if self.equity_curve else 1.0

    @property
    def total_return(self) -> float:
        return self.final_equity - 1.0

    @property
    def closed_trades(self) -> list[Trade]:
        return [t for t in self.trades if t.exit_px is not None]

    @property
    def win_rate(self) -> float | None:
        ct = self.closed_trades
        if not ct:
            return None
        wins = sum(1 for t in ct if (t.ret or 0) > 0)
        return wins / len(ct)


def max_drawdown(curve: list[float]) -> float:
    """Maximum drawdown of an equity curve, as a positive fraction."""
    peak = -float("inf")
    mdd = 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, (peak - v) / peak)
    return mdd


def backtest_symbol(label: str, inst_id: str, candles: list[dict],
                    fee_rate: float) -> SymbolResult:
    """Long-only Bollinger mean reversion with off-hours-only entries."""
    res = SymbolResult(label=label, inst_id=inst_id, candles=len(candles))
    equity = 1.0            # normalised, mark-to-market
    in_pos = False
    entry_px = 0.0
    cur_trade: Trade | None = None

    for c in candles:
        px = c["close"]
        upper, lower = c["upper"], c["lower"]

        if not in_pos:
            # Entry: close at/below lower band, only while US market is closed.
            if lower is not None and px <= lower and is_offhours(c["ts"]):
                in_pos = True
                entry_px = px
                cur_trade = Trade(entry_ts=c["ts"], entry_px=px)
                equity *= (1.0 - fee_rate)  # entry fee
        else:
            # Exit: close at/above upper band (take profit), any time.
            if upper is not None and px >= upper:
                gross = px / entry_px
                equity *= gross * (1.0 - fee_rate)  # apply exit fee
                cur_trade.exit_ts = c["ts"]
                cur_trade.exit_px = px
                cur_trade.ret = gross * (1.0 - fee_rate) - 1.0
                res.trades.append(cur_trade)
                cur_trade = None
                in_pos = False

        # Mark-to-market equity for the curve.
        mtm = equity * (px / entry_px) if in_pos else equity
        res.equity_curve.append((c["ts"], mtm))

    if in_pos and cur_trade is not None:
        res.trades.append(cur_trade)   # still-open trade (no exit)
        res.open_position = True
    return res


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def fmt_pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:+.2f}%"


def et_str(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)\
        .astimezone(ET).strftime("%Y-%m-%d %H:%M ET")


def run(symbols: dict[str, str], weeks: int, period: int, num_std: float,
        fee_rate: float) -> dict:
    sess = requests.Session()
    results: list[SymbolResult] = []
    print(f"Fetching OKX 30m candles (target window: {weeks} weeks)...\n")
    for label, inst in symbols.items():
        candles = fetch_candles(inst, bar="30m", weeks=weeks, session=sess)
        add_bollinger(candles, period=period, num_std=num_std)
        res = backtest_symbol(label, inst, candles, fee_rate)
        results.append(res)
        span = ""
        if candles:
            span = f"{et_str(candles[0]['ts'])}  ->  {et_str(candles[-1]['ts'])}"
        print(f"  {label:<5} ({inst:<11}) {len(candles):>4} candles   {span}")

    # Combined equal-weight portfolio equity curve (union of timestamps).
    all_ts = sorted({ts for r in results for ts, _ in r.equity_curve})
    per_sym_map = {r.label: dict(r.equity_curve) for r in results}
    combined = []
    last = {r.label: 1.0 for r in results}
    for ts in all_ts:
        for r in results:
            if ts in per_sym_map[r.label]:
                last[r.label] = per_sym_map[r.label][ts]
        combined.append(sum(last.values()) / len(results))

    combined_final = combined[-1] if combined else 1.0
    combined_return = combined_final - 1.0
    combined_mdd = max_drawdown(combined) if combined else 0.0

    # ------- print report -------
    print("\n" + "=" * 68)
    print("  OKX off-hours Bollinger backtest  |  30m candles, "
          f"MA{period} +/- {num_std}sigma")
    print("  Entry: close <= lower band during US-market-CLOSED hours")
    print("  Exit : close >= upper band | long-only | fee "
          f"{fee_rate*100:.2f}%/side")
    print("=" * 68)
    print(f"  {'SYMBOL':<7}{'TRADES':>7}{'WIN%':>8}{'RETURN':>11}{'MAXDD':>9}"
          f"{'OPEN':>7}")
    print("  " + "-" * 62)
    for r in results:
        curve = [v for _, v in r.equity_curve]
        mdd = max_drawdown(curve) if curve else 0.0
        wr = r.win_rate
        print(f"  {r.label:<7}{len(r.closed_trades):>7}"
              f"{('n/a' if wr is None else f'{wr*100:.0f}%'):>8}"
              f"{fmt_pct(r.total_return):>11}{fmt_pct(mdd):>9}"
              f"{('yes' if r.open_position else 'no'):>7}")
    print("  " + "-" * 62)
    print(f"  {'TOTAL':<7}{'':>7}{'':>8}{fmt_pct(combined_return):>11}"
          f"{fmt_pct(combined_mdd):>9}")
    print("=" * 68)
    print("  TOTAL = equal-weight (25% each) combined equity curve.")
    print("  MAXDD = maximum drawdown of the respective equity curve.")

    total_candles = sum(r.candles for r in results)
    if total_candles and combined:
        span_days = (all_ts[-1] - all_ts[0]) / 1000 / 86400
        print(f"\n  Data span actually available: ~{span_days:.2f} days "
              f"across the universe.")
        if span_days < weeks * 7 * 0.5:
            print("  NOTE: OKX only lists these tokenised stocks since "
                  "2026-07-16, so the")
            print("        available history is far short of "
                  f"{weeks} weeks. Re-run later as")
            print("        data accumulates -- the window fills in "
                  "automatically.")

    # ------- machine-readable result -------
    return {
        "params": {
            "weeks": weeks, "bar": "30m", "ma_period": period,
            "num_std": num_std, "fee_rate": fee_rate,
            "symbols": symbols,
        },
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "symbols": [
            {
                "label": r.label,
                "inst_id": r.inst_id,
                "candles": r.candles,
                "closed_trades": len(r.closed_trades),
                "win_rate": r.win_rate,
                "total_return": r.total_return,
                "max_drawdown": max_drawdown([v for _, v in r.equity_curve])
                if r.equity_curve else 0.0,
                "open_position": r.open_position,
                "trades": [
                    {
                        "entry": et_str(t.entry_ts), "entry_px": t.entry_px,
                        "exit": et_str(t.exit_ts) if t.exit_ts else None,
                        "exit_px": t.exit_px, "return": t.ret,
                    } for t in r.trades
                ],
            } for r in results
        ],
        "portfolio": {
            "total_return": combined_return,
            "max_drawdown": combined_mdd,
            "final_equity": combined_final,
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--weeks", type=int, default=8,
                    help="look-back window in weeks (default 8)")
    ap.add_argument("--period", type=int, default=20,
                    help="Bollinger moving-average period (default 20)")
    ap.add_argument("--std", type=float, default=2.0,
                    help="Bollinger band width in std-devs (default 2)")
    ap.add_argument("--fee", type=float, default=0.001,
                    help="taker fee per side as a fraction (default 0.001 = 0.1%%)")
    ap.add_argument("--json-out", type=str, default=None,
                    help="write full machine-readable result to this path")
    args = ap.parse_args(argv)

    try:
        result = run(DEFAULT_SYMBOLS, weeks=args.weeks, period=args.period,
                     num_std=args.std, fee_rate=args.fee)
    except requests.RequestException as e:
        print(f"Network error talking to OKX: {e}", file=sys.stderr)
        return 2

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nFull result written to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
