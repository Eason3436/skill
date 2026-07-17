# OKX Holiday Bollinger-Band Backtest

Backtests a mean-reversion strategy on OKX tokenized US stocks (xStocks),
traded **only while the underlying US equity market is closed**.

## Strategy

| Item | Value |
|------|-------|
| Instruments | `XTSM-USDT`, `XQQQ-USDT`, `XMSFT-USDT`, `XAAPL-USDT` (TSM, QQQ, MSFT, AAPL) |
| Timeframe | 30-minute bars |
| Signal | Bollinger Bands, period 20, **±2** standard deviations |
| Entry | Long **only while the US market is closed**, when `close ≤ lower band` |
| Exit | `close ≥ upper band` (take profit), or force-exit at market re-open |
| Sizing | Equal weight, 10,000 per ticker (40,000 book), one position per ticker |
| Fees | 0.10% per side |
| Window | Last 8 weeks |
| Metrics | Aggregate total return + max drawdown |

**Why "market closed"?** Tokenized stocks trade 24/7 on OKX, but the real US
session runs 09:30–16:00 ET on non-holiday weekdays. While the real market is
closed (nights, weekends, holidays) the token has no live price anchor and
tends to over/undershoot and revert — the edge this strategy tries to capture.
Market hours use `America/New_York` (DST-aware) plus the NYSE holiday calendar.

## Run

```bash
python3 okx_holiday_bb_backtest.py
```

Pure standard library — no numpy/pandas. Pulls public OKX market data (no API
key). Writes `backtest_results.json` (per-ticker stats + aggregate equity curve).

## ⚠️ Important data limitation

These xStocks tokens were **listed on OKX on 2026-07-16**, so as of this writing
OKX has only about **one day** of 30-minute history for them — an 8-week
backtest on OKX data is **not yet possible**. The script fetches all available
history, prints a **DATA COVERAGE** section, and warns when actual coverage is
far below the requested 8 weeks. The results it prints today therefore reflect
~1 day of data, not a full 8 weeks.

The logic is correct and future-proof: re-run it as history accumulates and it
will produce a genuine 8-week result. Because the strategy is defined by trading
*while the US market is closed*, it fundamentally requires the 24/7 tokenized
series — it cannot be reconstructed from ordinary (closed-when-closed) equity
feeds, so substituting another data source is not a valid workaround.
