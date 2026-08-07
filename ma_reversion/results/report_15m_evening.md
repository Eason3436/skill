# MA-reversion backtest — MU-USDT-SWAP 15m

- Data: 2026-03-04 07:15 → 2026-08-07 05:45 UTC (14,971 bars)
- Session (Taipei): 16:00–24:00, Mon–Fri
- Sessions traded: 112 (3,584 of 14,971 bars, 23.9% of the clock)
- Execution: limit entry · 2.0bps maker / 5.0bps taker / 3.0bps slippage on taker fills
- Sizing: 0.75% equity risked per trade, max 3.0x notional

## Headline

| metric | value |
|---|---:|
| trades | 71 |
| trades_per_week | 3.21 |
| total_return_pct | -1.05 |
| cagr_pct | -2.45 |
| sharpe | -0.25 |
| sortino | -0.25 |
| max_dd_pct | -7.58 |
| calmar | -0.32 |
| win_rate_pct | 53.52 |
| profit_factor | 0.94 |
| expectancy | -1.47 |
| avg_win | 40.23 |
| avg_loss | -49.50 |
| max_consec_losses | 10 |
| avg_bars_held | 7.15 |
| total_costs | 175.32 |
| cost_pct_of_gross | 248.27 |
| final_equity | 9,895.30 |

## by_month

| month   |   trades |     pnl |   win_rate |    avg |
|:--------|---------:|--------:|-----------:|-------:|
| 2026-03 |        8 |  167.87 |      62.5  |  20.98 |
| 2026-04 |       12 |  -53.29 |      66.67 |  -4.44 |
| 2026-05 |       15 | -231.34 |      40    | -15.42 |
| 2026-06 |       12 | -316.55 |      16.67 | -26.38 |
| 2026-07 |       20 |  186.04 |      70    |   9.3  |
| 2026-08 |        4 |  142.58 |      75    |  35.65 |

## by_hour

|   tpe_hour |   trades |     pnl |   win_rate |    avg |
|-----------:|---------:|--------:|-----------:|-------:|
|         16 |       19 | -167.38 |      47.37 |  -8.81 |
|         17 |       10 | -115.11 |      50    | -11.51 |
|         18 |       13 |  -10.71 |      53.85 |  -0.82 |
|         19 |       13 |  323.35 |      76.92 |  24.87 |
|         20 |       14 | -326.31 |      35.71 | -23.31 |
|         21 |        2 |  191.46 |     100    |  95.73 |

## by_dow

|   dow |   trades |     pnl |   win_rate |    avg |
|------:|---------:|--------:|-----------:|-------:|
|     0 |       15 |  340.15 |      66.67 |  22.68 |
|     1 |       16 |  -21.94 |      56.25 |  -1.37 |
|     2 |       14 | -198.99 |      50    | -14.21 |
|     3 |       17 |  -84.53 |      47.06 |  -4.97 |
|     4 |        9 | -139.39 |      44.44 | -15.49 |

## by_side

| side   |   trades |     pnl |   win_rate |   avg |
|:-------|---------:|--------:|-----------:|------:|
| long   |       27 |   54.26 |      59.26 |  2.01 |
| short  |       44 | -158.96 |      50    | -3.61 |

## by_reason

| reason    |   trades |      pnl |   win_rate |    avg |
|:----------|---------:|---------:|-----------:|-------:|
| stop      |       16 | -1269.97 |       0    | -79.37 |
| time_stop |       55 |  1165.27 |      69.09 |  21.19 |

## Parameters

```json
{
  "inst": "MU-USDT-SWAP",
  "bar": "15m",
  "tick_size": 0.01,
  "lot_size": 0.01,
  "session_start_hour": 16,
  "session_end_hour": 24,
  "ma_type": "sma",
  "ma_len": 32,
  "atr_len": 5,
  "slope_len": 4,
  "regime_win": 672,
  "entry_mode": "first_touch",
  "z_entry": 2.5,
  "require_turn": false,
  "max_slope": 1.5,
  "vol_rank_min": 0.1,
  "vol_rank_max": 1.0,
  "min_bars_left": 12,
  "allow_long": true,
  "allow_short": true,
  "exit_mode": "sd",
  "tp_sd": 0,
  "stop_sd": 4.0,
  "z_exit": 0.3,
  "z_stop": 6.0,
  "max_hold_bars": 8,
  "entry_exec": "limit",
  "entry_limit_ttl": 1,
  "entry_limit_offset_ticks": 1,
  "maker_bps": 2.0,
  "taker_bps": 5.0,
  "slip_bps": 3.0,
  "risk_pct": 0.75,
  "max_leverage": 3.0,
  "init_equity": 10000.0
}
```