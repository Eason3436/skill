# MA-reversion backtest — MU-USDT-SWAP 15m

- Data: 2026-03-04 07:15 → 2026-08-07 05:45 UTC (14,971 bars)
- Session (Taipei): 08:00–16:00, Mon–Fri
- Sessions traded: 113 (3,579 of 14,971 bars, 23.9% of the clock)
- Execution: limit entry · 2.0bps maker / 5.0bps taker / 3.0bps slippage on taker fills
- Sizing: 0.75% equity risked per trade, max 3.0x notional

## Headline

| metric | value |
|---|---:|
| trades | 53 |
| trades_per_week | 2.39 |
| total_return_pct | 3.46 |
| cagr_pct | 8.35 |
| sharpe | 2.25 |
| sortino | 1.91 |
| max_dd_pct | -0.94 |
| calmar | 8.88 |
| win_rate_pct | 62.26 |
| profit_factor | 2.02 |
| expectancy | 6.53 |
| avg_win | 20.75 |
| avg_loss | -16.93 |
| max_consec_losses | 4 |
| avg_bars_held | 8.00 |
| total_costs | 63.48 |
| cost_pct_of_gross | 15.49 |
| final_equity | 10,346.32 |

## by_month

| month   |   trades |    pnl |   win_rate |   avg |
|:--------|---------:|-------:|-----------:|------:|
| 2026-03 |        6 |  24.69 |      66.67 |  4.11 |
| 2026-04 |       10 |  38.81 |      50    |  3.88 |
| 2026-05 |       12 |  -8.5  |      41.67 | -0.71 |
| 2026-06 |       10 |  20.86 |      70    |  2.09 |
| 2026-07 |       14 | 267.43 |      78.57 | 19.1  |
| 2026-08 |        1 |   3.02 |     100    |  3.02 |

## by_hour

|   tpe_hour |   trades |    pnl |   win_rate |   avg |
|-----------:|---------:|-------:|-----------:|------:|
|          8 |       24 | 327.61 |      66.67 | 13.65 |
|          9 |       11 | -18.15 |      54.55 | -1.65 |
|         10 |        4 |  37.66 |     100    |  9.42 |
|         11 |        6 | -15.5  |      50    | -2.58 |
|         12 |        8 |  14.7  |      50    |  1.84 |

## by_dow

|   dow |   trades |    pnl |   win_rate |   avg |
|------:|---------:|-------:|-----------:|------:|
|     0 |       19 | 185.88 |      68.42 |  9.78 |
|     1 |        8 |  50.85 |      62.5  |  6.36 |
|     2 |        5 |  23.97 |      60    |  4.79 |
|     3 |       11 |  66.82 |      54.55 |  6.07 |
|     4 |       10 |  18.8  |      60    |  1.88 |

## by_side

| side   |   trades |    pnl |   win_rate |   avg |
|:-------|---------:|-------:|-----------:|------:|
| long   |       22 |  39.46 |      63.64 |  1.79 |
| short  |       31 | 306.86 |      61.29 |  9.9  |

## by_reason

| reason    |   trades |    pnl |   win_rate |   avg |
|:----------|---------:|-------:|-----------:|------:|
| time_stop |       53 | 346.32 |      62.26 |  6.53 |

## Parameters

```json
{
  "inst": "MU-USDT-SWAP",
  "bar": "15m",
  "tick_size": 0.01,
  "lot_size": 0.01,
  "session_start_hour": 8,
  "session_end_hour": 16,
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
  "stop_sd": 8.0,
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