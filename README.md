# OKX Off-Hours Bollinger-Band Backtest

Backtest of a **Bollinger-Band mean-reversion strategy** on four tokenised US
stocks that trade **24/7 on OKX** — so the strategy can trade precisely when the
US stock market is **closed** (holidays, weekends, pre-/post-market).

This implements the request:
> 回測在假日 / 美股非開盤時段，下軌（個別）買入 TSM QQQ MSFT AAPL、上軌賣出，
> 30min ±2，這 4 檔的收益總、回測 8 週、最大回撤，用 OKX。

## Strategy

| Item | Value |
|------|-------|
| Universe | `XTSM-USDT`, `XQQQ-USDT`, `XMSFT-USDT`, `XAAPL-USDT` (tokenised TSM / QQQ / MSFT / AAPL) |
| Candle | 30-minute |
| Indicator | Bollinger Bands — MA period **20**, bands at **±2σ** (`30min ±2`) |
| Entry | Close **≤ lower band** *and* the candle falls in **US-market-closed** hours |
| Exit | Close **≥ upper band** (take profit), any time |
| Direction | Long-only, each symbol traded independently, no leverage, no pyramiding |
| Sizing | Each symbol = 1.0 normalised unit; portfolio total = equal-weight (25% each) |
| Fees | 0.1% taker per side (configurable) |
| Reporting | Per-symbol return, combined **total return**, and **max drawdown** |

"US-market-closed hours" = outside 09:30–16:00 America/New_York on weekdays,
plus all weekends and NYSE/Nasdaq holidays (holiday calendar built in).

## ⚠️ Data limitation (read this)

These tokenised-stock instruments were **only listed on OKX on 2026-07-16**, so
OKX currently exposes **~1 day** of 30-minute candle history — not 8 weeks. The
engine still *requests* an 8-week window; it simply uses whatever history OKX
returns. **Re-run the same command later and the window fills in automatically**
as candles accumulate. No true multi-week result exists on OKX yet — no data
source can provide off-hours prices for these tokens before they were listed.

## Usage

```bash
pip install requests
python3 okx_offhours_bollinger_backtest.py            # default: 8 weeks, MA20, ±2σ
python3 okx_offhours_bollinger_backtest.py --json-out backtest_result.json
python3 okx_offhours_bollinger_backtest.py --weeks 8 --period 20 --std 2 --fee 0.001
```

Flags: `--weeks`, `--period`, `--std`, `--fee`, `--json-out`. No API key needed
(uses only OKX public market-data endpoints).

## Example run (2026-07-17, ~1 day of data available)

```
  SYMBOL  TRADES    WIN%     RETURN    MAXDD   OPEN
  --------------------------------------------------------------
  TSM          0     n/a     -0.64%   +0.64%    yes
  QQQ          0     n/a     -0.67%   +0.73%    yes
  MSFT         0     n/a     -0.35%   +0.39%    yes
  AAPL         0     n/a     +0.00%   +0.00%     no
  --------------------------------------------------------------
  TOTAL                      -0.41%   +0.41%
```

`RETURN` for a symbol with `OPEN=yes` is the mark-to-market of a still-open
position (entered at the lower band, not yet reached the upper band). With only
~1 day of history most positions are still open, so these numbers are a
mechanics demonstration, **not** a meaningful 8-week performance figure — see the
data limitation above.

## Notes & assumptions

- Signals act on **candle close** (no intrabar fills), which is conservative and
  avoids look-ahead bias.
- Standard deviation is the population σ over the MA window (classic Bollinger).
- Entries are restricted to off-hours; exits are allowed any time so a position
  opened overnight can be taken profit even after the US open.
- Combined total return is the equal-weight average of the four normalised
  equity curves; max drawdown is computed on that combined curve.
