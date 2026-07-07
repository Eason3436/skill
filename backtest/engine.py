"""Bollinger-band mean-reversion backtest ("TSM" = buy lower band, sell upper).

Strategy (long-only, no stop loss, per user spec):
  * Middle band = SMA(period) of close; std = population stddev of close.
  * Lower band = middle - k*std ; Upper band = middle + k*std.
  * ENTER long when a bar closes at/below the lower band and we are flat.
  * EXIT (sell) when a bar closes at/above the upper band and we are long.
  * No stop loss -> we ride every drawdown until the upper band is tagged.

Execution: signal and fill on the same closed bar's close (standard simple fill).
Sizing: 100% of equity per trade, 1x, no leverage. Fees configurable (default 0).
Equity is marked-to-market every bar so max drawdown reflects open-trade pain.
"""
import json
import numpy as np
import pandas as pd

BASE_BAR_MS = 3600_000  # 1H base data


def load_1h(path):
    rows = json.load(open(path))
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "vol"])
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df.set_index("dt")[["open", "high", "low", "close", "vol"]]


def resample(df1h, hours):
    """Resample 1H OHLCV to `hours`-hour bars, anchored to UTC midnight."""
    rule = f"{hours}h"
    agg = {"open": "first", "high": "max", "low": "min",
           "close": "last", "vol": "sum"}
    out = df1h.resample(rule, label="left", closed="left", origin="epoch").agg(agg)
    return out.dropna(subset=["open"])


def backtest(df, k, period=20, fee=0.0, initial=10_000.0):
    c = df["close"].to_numpy(dtype=float)
    mid = pd.Series(c).rolling(period).mean().to_numpy()
    std = pd.Series(c).rolling(period).std(ddof=0).to_numpy()
    lower = mid - k * std
    upper = mid + k * std

    cash = initial
    qty = 0.0              # units held (long only)
    entry_px = np.nan
    equity = np.full(len(c), initial, dtype=float)
    trades = []            # (entry_px, exit_px, ret)

    for i in range(len(c)):
        px = c[i]
        # mark to market before any action this bar
        if qty > 0:
            equity[i] = qty * px
        else:
            equity[i] = cash

        if np.isnan(lower[i]):
            continue

        if qty == 0 and px <= lower[i]:
            # enter long with all cash
            qty = (cash * (1 - fee)) / px
            entry_px = px
            cash = 0.0
            equity[i] = qty * px
        elif qty > 0 and px >= upper[i]:
            # exit long
            cash = qty * px * (1 - fee)
            trades.append((entry_px, px, px / entry_px - 1))
            qty = 0.0
            equity[i] = cash

    final_equity = equity[-1]
    total_return = final_equity / initial - 1
    run_max = np.maximum.accumulate(equity)
    dd = equity / run_max - 1
    max_dd = dd.min()

    wins = [t for t in trades if t[2] > 0]
    return {
        "bars": len(c),
        "start": df.index[0], "end": df.index[-1],
        "n_trades": len(trades),
        "win_rate": (len(wins) / len(trades)) if trades else float("nan"),
        "total_return": total_return,
        "max_drawdown": max_dd,
        "final_equity": final_equity,
        "open_at_end": qty > 0,
        "trades": trades,
    }


CONFIG = [
    (2, 2.5),
    (3, 2.0),
    (4, 2.0),
    (6, 2.0),
    (8, 2.0),
    (12, 2.0),
]


def main():
    df1h = load_1h("backtest/data_TSM-USDT-SWAP_1H.json")
    rows = []
    for hours, k in CONFIG:
        df = resample(df1h, hours)
        r = backtest(df, k)
        rows.append((hours, k, r))
        print(f"[{hours}H  band ±{k}]  bars={r['bars']:>4}  "
              f"trades={r['n_trades']:>3}  win={r['win_rate']*100:5.1f}%  "
              f"return={r['total_return']*100:8.2f}%  "
              f"maxDD={r['max_drawdown']*100:8.2f}%  "
              f"{'(open at end)' if r['open_at_end'] else ''}")
    return df1h, rows


if __name__ == "__main__":
    main()
