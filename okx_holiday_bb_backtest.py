#!/usr/bin/env python3
"""
OKX tokenized-stock backtest: Bollinger-Band mean reversion traded only while
the underlying US equity market is CLOSED (weekends, overnight, and holidays).

Idea
----
Tokenized stocks (xStocks) on OKX trade 24/7, but the real US equity market is
open only 09:30-16:00 ET on non-holiday weekdays. While the real market is
closed the token has no live price anchor, so it tends to over/undershoot and
mean-revert. This strategy:

  * trades XTSM / XQQQ / XMSFT / XAAPL (TSM, QQQ, MSFT, AAPL) individually,
  * on 30-minute bars with Bollinger Bands (period 20, +/-2 std),
  * ENTERS long only while the US market is closed, when close <= lower band,
  * EXITS when close >= upper band (take profit),
  * FORCE-EXITS any open position at the moment the US market re-opens
    (to avoid the re-anchoring gap), and
  * reports aggregate total return and max drawdown over the last 8 weeks.

Data comes from OKX public market-data endpoints (no API key required).
Pure standard library -- no numpy/pandas needed.
"""

import json
import time
import urllib.request
from datetime import datetime, timezone, date
from statistics import mean, pstdev
from zoneinfo import ZoneInfo

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
INSTRUMENTS = {
    "XTSM-USDT": "TSM",
    "XQQQ-USDT": "QQQ",
    "XMSFT-USDT": "MSFT",
    "XAAPL-USDT": "AAPL",
}
BAR = "30m"
BB_PERIOD = 20          # Bollinger moving-average / std window (bars)
BB_K = 2.0              # +/- 2 standard deviations  ("+-2")
WEEKS = 8               # backtest window length
FEE = 0.001            # taker fee per side (0.10%)
CAPITAL_PER_TICKER = 10_000.0    # equal allocation; total book = 40,000
BAR_MS = 30 * 60 * 1000

NY = ZoneInfo("America/New_York")

# NYSE full-day holidays (regular session closed). Covers the backtest window
# and the surrounding year so the filter is correct regardless of run date.
NYSE_HOLIDAYS_2026 = {
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # Martin Luther King Jr. Day
    date(2026, 2, 16),   # Washington's Birthday
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # Independence Day (observed, Jul 4 is Saturday)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving
    date(2026, 12, 25),  # Christmas
}
NYSE_HOLIDAYS_2025 = {
    date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17), date(2025, 4, 18),
    date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4), date(2025, 9, 1),
    date(2025, 11, 27), date(2025, 12, 25),
}
HOLIDAYS = NYSE_HOLIDAYS_2025 | NYSE_HOLIDAYS_2026


# --------------------------------------------------------------------------- #
# US market-hours filter
# --------------------------------------------------------------------------- #
def us_market_open(ts_ms: int) -> bool:
    """True if the regular US equity session is open at this UTC timestamp."""
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).astimezone(NY)
    if dt.weekday() >= 5:            # Sat/Sun
        return False
    if dt.date() in HOLIDAYS:        # full-day holiday
        return False
    minutes = dt.hour * 60 + dt.minute
    # Regular session 09:30 (570) inclusive to 16:00 (960) exclusive.
    return 570 <= minutes < 960


# --------------------------------------------------------------------------- #
# OKX data fetch
# --------------------------------------------------------------------------- #
def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "backtest/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def fetch_candles(inst_id: str, since_ms: int):
    """Fetch confirmed 30m candles from `since_ms` to now, ascending by time."""
    out = {}
    after = None  # OKX returns bars strictly older than `after`
    while True:
        url = (f"https://www.okx.com/api/v5/market/history-candles?"
               f"instId={inst_id}&bar={BAR}&limit=100")
        if after is not None:
            url += f"&after={after}"
        resp = _get(url)
        if resp.get("code") != "0":
            raise RuntimeError(f"OKX error for {inst_id}: {resp}")
        rows = resp.get("data", [])
        if not rows:
            break
        for c in rows:
            ts = int(c[0])
            # c = [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
            if c[8] == "1":                     # only confirmed (closed) bars
                out[ts] = (float(c[1]), float(c[2]), float(c[3]), float(c[4]))
        oldest = min(int(c[0]) for c in rows)
        if oldest <= since_ms:
            break
        after = oldest
        time.sleep(0.12)                        # be gentle with rate limits
    bars = [(ts, *out[ts]) for ts in sorted(out)]   # (ts,o,h,l,c) ascending
    return bars


# --------------------------------------------------------------------------- #
# Indicators
# --------------------------------------------------------------------------- #
def bollinger(closes):
    """Return list of (mid, upper, lower) aligned to closes; None during warmup."""
    bands = [None] * len(closes)
    for i in range(BB_PERIOD - 1, len(closes)):
        window = closes[i - BB_PERIOD + 1:i + 1]
        m = mean(window)
        sd = pstdev(window)
        bands[i] = (m, m + BB_K * sd, m - BB_K * sd)
    return bands


# --------------------------------------------------------------------------- #
# Per-instrument backtest
# --------------------------------------------------------------------------- #
def backtest_instrument(bars, window_start_ms):
    """Run the strategy on one instrument. Returns (equity_by_ts, trades)."""
    closes = [b[4] for b in bars]
    bands = bollinger(closes)

    cash = CAPITAL_PER_TICKER
    shares = 0.0
    entry_price = None
    trades = []
    equity_by_ts = {}

    for i, (ts, o, h, l, c) in enumerate(bars):
        band = bands[i]
        if ts >= window_start_ms and band is not None:
            _, upper, lower = band
            is_open = us_market_open(ts)

            if shares == 0.0:
                # Entry: only while the US market is closed, price at/below lower band
                if (not is_open) and c <= lower:
                    shares = (cash * (1 - FEE)) / c
                    cash = 0.0
                    entry_price = c
                    trades.append({"entry_ts": ts, "entry": c,
                                   "exit_ts": None, "exit": None, "reason": None})
            else:
                exit_reason = None
                if c >= upper:
                    exit_reason = "upper_band"      # take profit
                elif is_open:
                    exit_reason = "market_reopen"   # avoid re-anchoring gap
                if exit_reason:
                    cash = shares * c * (1 - FEE)
                    shares = 0.0
                    trades[-1].update(exit_ts=ts, exit=c, reason=exit_reason)
                    entry_price = None

        # Mark-to-market equity sampled every bar in the window
        if ts >= window_start_ms and bands[i] is not None:
            equity_by_ts[ts] = cash + shares * c

    # Close any position still open at the end (mark at last close for reporting)
    if shares > 0.0 and bars:
        last_ts, *_rest, last_c = bars[-1]
        cash = shares * last_c * (1 - FEE)
        shares = 0.0
        trades[-1].update(exit_ts=last_ts, exit=last_c, reason="end_of_test")
        equity_by_ts[last_ts] = cash

    return equity_by_ts, trades


# --------------------------------------------------------------------------- #
# Portfolio metrics
# --------------------------------------------------------------------------- #
def max_drawdown(series):
    """Max peak-to-trough drawdown (fraction) over an equity series."""
    peak = series[0]
    mdd = 0.0
    for v in series:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    return mdd


def fmt_ts(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def main():
    now_ms = int(time.time() * 1000)
    window_start_ms = now_ms - WEEKS * 7 * 24 * 60 * 60 * 1000
    fetch_start_ms = window_start_ms - (BB_PERIOD + 2) * BAR_MS  # warmup for BB

    print(f"OKX holiday Bollinger-Band backtest")
    print(f"Window: {fmt_ts(window_start_ms)}  ->  {fmt_ts(now_ms)}  ({WEEKS} weeks)")
    print(f"Bars: {BAR} | BB: period {BB_PERIOD}, k {BB_K} | fee {FEE*100:.2f}%/side")
    print(f"Capital: {CAPITAL_PER_TICKER:,.0f} per ticker x {len(INSTRUMENTS)} "
          f"= {CAPITAL_PER_TICKER*len(INSTRUMENTS):,.0f}\n")

    per_ticker_equity = {}
    per_ticker_summary = {}
    all_ts = set()
    earliest_bar = None

    for inst_id, name in INSTRUMENTS.items():
        bars = fetch_candles(inst_id, fetch_start_ms)
        if bars:
            first = bars[0][0]
            earliest_bar = first if earliest_bar is None else min(earliest_bar, first)
        eq, trades = backtest_instrument(bars, window_start_ms)
        per_ticker_equity[inst_id] = eq
        all_ts.update(eq.keys())

        closed = [t for t in trades if t["exit"] is not None]
        final_eq = eq[max(eq)] if eq else CAPITAL_PER_TICKER
        ret = final_eq / CAPITAL_PER_TICKER - 1
        wins = sum(1 for t in closed if t["exit"] > t["entry"])
        per_ticker_summary[name] = {
            "inst": inst_id, "bars": len(bars), "trades": len(closed),
            "wins": wins, "return": ret, "final": final_eq, "series": eq,
        }
        wr = (wins / len(closed) * 100) if closed else 0.0
        print(f"{name:5s} ({inst_id:10s})  bars={len(bars):4d}  trades={len(closed):3d}"
              f"  win%={wr:5.1f}  return={ret*100:+7.2f}%  final={final_eq:,.0f}")

    # Aggregate portfolio: sum forward-filled per-ticker equity on a common grid
    timeline = sorted(all_ts)
    last_val = {k: CAPITAL_PER_TICKER for k in INSTRUMENTS}
    agg = []
    for ts in timeline:
        for inst_id in INSTRUMENTS:
            if ts in per_ticker_equity[inst_id]:
                last_val[inst_id] = per_ticker_equity[inst_id][ts]
        agg.append(sum(last_val.values()))

    start_book = CAPITAL_PER_TICKER * len(INSTRUMENTS)
    final_book = agg[-1] if agg else start_book
    total_ret = final_book / start_book - 1
    mdd = max_drawdown(agg) if agg else 0.0

    print("\n" + "=" * 60)
    print("PORTFOLIO (4 tickers, equal weight)")
    print("=" * 60)
    print(f"Starting book : {start_book:,.2f}")
    print(f"Ending book   : {final_book:,.2f}")
    print(f"Total return  : {total_ret*100:+.2f}%")
    print(f"Max drawdown  : {mdd*100:.2f}%")

    # --- Data-coverage honesty check ------------------------------------- #
    requested_days = WEEKS * 7
    actual_days = (now_ms - earliest_bar) / 86_400_000 if earliest_bar else 0
    print("\n" + "-" * 60)
    print("DATA COVERAGE")
    print("-" * 60)
    print(f"Requested window : {requested_days} days ({WEEKS} weeks)")
    if earliest_bar:
        print(f"Actual data from : {fmt_ts(earliest_bar)}")
        print(f"Actual coverage  : {actual_days:.2f} days")
    if actual_days < requested_days * 0.9:
        print("\n*** WARNING: OKX history for these tokenized stocks is far shorter")
        print("*** than the requested 8-week window. These xStocks were listed")
        print("*** only recently, so the numbers above cover the available data")
        print("*** only -- NOT a full 8 weeks. Re-run later as history accrues.")

    # Persist results for the visualization
    result = {
        "generated": fmt_ts(now_ms),
        "window_start": fmt_ts(window_start_ms),
        "window_end": fmt_ts(now_ms),
        "params": {"bar": BAR, "bb_period": BB_PERIOD, "bb_k": BB_K,
                   "fee": FEE, "weeks": WEEKS,
                   "capital_per_ticker": CAPITAL_PER_TICKER},
        "per_ticker": {n: {"inst": s["inst"], "trades": s["trades"],
                           "wins": s["wins"], "return": s["return"],
                           "final": s["final"]}
                       for n, s in per_ticker_summary.items()},
        "portfolio": {"start": start_book, "final": final_book,
                      "total_return": total_ret, "max_drawdown": mdd},
        "equity_curve": [{"ts": ts, "equity": agg[i]}
                         for i, ts in enumerate(timeline)],
    }
    with open("backtest_results.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nResults written to backtest_results.json")


if __name__ == "__main__":
    main()
