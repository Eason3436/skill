# MA-reversion backtest — MU-USDT-SWAP 5m

- Data: 2026-03-04 07:15 → 2026-08-07 04:25 UTC (44,895 bars)
- Session (Taipei): 16:00–24:00, Mon–Fri
- Sessions traded: 112 (10,752 of 44,895 bars, 23.9% of the clock)
- Execution: limit entry · 2.0bps maker / 5.0bps taker / 3.0bps slippage on taker fills
- Sizing: 0.75% equity risked per trade, max 3.0x notional

## Headline

| metric | value |
|---|---:|
| trades | 109 |
| trades_per_week | 4.92 |
| total_return_pct | -1.84 |
| cagr_pct | -4.28 |
| sharpe | -0.54 |
| sortino | -0.71 |
| max_dd_pct | -5.35 |
| calmar | -0.80 |
| win_rate_pct | 48.62 |
| profit_factor | 0.89 |
| expectancy | -1.69 |
| avg_win | 26.86 |
| avg_loss | -28.70 |
| max_consec_losses | 7 |
| avg_bars_held | 23.25 |
| total_costs | 177.94 |
| cost_pct_of_gross | 2,992.46 |
| final_equity | 9,816.11 |

## by_month

| month   |   trades |     pnl |   win_rate |   avg |
|:--------|---------:|--------:|-----------:|------:|
| 2026-03 |       19 |   47.7  |      52.63 |  2.51 |
| 2026-04 |       21 |  -72.19 |      52.38 | -3.44 |
| 2026-05 |       20 |   56.86 |      45    |  2.84 |
| 2026-06 |       19 | -155.18 |      42.11 | -8.17 |
| 2026-07 |       25 |  -15.02 |      48    | -0.6  |
| 2026-08 |        5 |  -46.06 |      60    | -9.21 |

## by_hour

|   tpe_hour |   trades |     pnl |   win_rate |    avg |
|-----------:|---------:|--------:|-----------:|-------:|
|         16 |       41 | -151.76 |      53.66 |  -3.7  |
|         17 |       10 |  158.66 |      80    |  15.87 |
|         18 |       18 | -331.4  |      27.78 | -18.41 |
|         19 |       22 |  -87.35 |      36.36 |  -3.97 |
|         20 |       17 |  155.58 |      52.94 |   9.15 |
|         21 |        1 |   72.37 |     100    |  72.37 |

## by_dow

|   dow |   trades |     pnl |   win_rate |   avg |
|------:|---------:|--------:|-----------:|------:|
|     0 |       21 |   88.31 |      52.38 |  4.21 |
|     1 |       20 | -117.73 |      45    | -5.89 |
|     2 |       22 | -168.29 |      50    | -7.65 |
|     3 |       27 | -118.2  |      44.44 | -4.38 |
|     4 |       19 |  132.03 |      52.63 |  6.95 |

## by_side

| side   |   trades |     pnl |   win_rate |   avg |
|:-------|---------:|--------:|-----------:|------:|
| long   |       42 | -100.61 |      54.76 | -2.4  |
| short  |       67 |  -83.27 |      44.78 | -1.24 |

## by_reason

| reason    |   trades |     pnl |   win_rate |    avg |
|:----------|---------:|--------:|-----------:|-------:|
| stop      |        6 | -469.5  |       0    | -78.25 |
| time_stop |      102 |  357.65 |      51.96 |   3.51 |
| z_stop    |        1 |  -72.04 |       0    | -72.04 |

## Parameters

```json
{
  "inst": "MU-USDT-SWAP",
  "bar": "5m",
  "tick_size": 0.01,
  "lot_size": 0.01,
  "session_start_hour": 16,
  "session_end_hour": 24,
  "ma_type": "sma",
  "ma_len": 96,
  "atr_len": 14,
  "slope_len": 12,
  "regime_win": 2016,
  "entry_mode": "first_touch",
  "z_entry": 2.0,
  "require_turn": false,
  "max_slope": 1.5,
  "vol_rank_min": 0.1,
  "vol_rank_max": 0.95,
  "min_bars_left": 36,
  "allow_long": true,
  "allow_short": true,
  "exit_mode": "sd",
  "tp_sd": 0,
  "stop_sd": 6.0,
  "z_exit": 0.3,
  "z_stop": 6.0,
  "max_hold_bars": 24,
  "entry_exec": "limit",
  "entry_limit_ttl": 3,
  "entry_limit_offset_ticks": 1,
  "maker_bps": 2.0,
  "taker_bps": 5.0,
  "slip_bps": 3.0,
  "risk_pct": 0.75,
  "max_leverage": 3.0,
  "init_equity": 10000.0
}
```