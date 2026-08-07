# MA-reversion backtest — MU-USDT-SWAP 15m

- Data: 2026-03-04 07:15 → 2026-08-07 05:45 UTC (14,971 bars)
- Session (Taipei): 08:00–16:00, Mon–Fri
- Sessions traded: 113 (3,579 of 14,971 bars, 23.9% of the clock)
- Execution: limit entry · 2.0bps maker / 5.0bps taker / 3.0bps slippage on taker fills
- Sizing: 0.75% equity risked per trade, max 3.0x notional

## Headline

| metric | value |
|---|---:|
| trades | 54 |
| trades_per_week | 2.44 |
| total_return_pct | 6.82 |
| cagr_pct | 16.81 |
| sharpe | 2.23 |
| sortino | 2.28 |
| max_dd_pct | -2.27 |
| calmar | 7.42 |
| win_rate_pct | 61.11 |
| profit_factor | 1.98 |
| expectancy | 12.63 |
| avg_win | 41.79 |
| avg_loss | -33.18 |
| max_consec_losses | 4 |
| avg_bars_held | 7.50 |
| total_costs | 128.22 |
| cost_pct_of_gross | 15.82 |
| final_equity | 10,682.26 |

## by_month

| month   |   trades |    pnl |   win_rate |   avg |
|:--------|---------:|-------:|-----------:|------:|
| 2026-03 |        6 |   4.33 |      66.67 |  0.72 |
| 2026-04 |       10 |  26.24 |      50    |  2.62 |
| 2026-05 |       12 | -29.85 |      41.67 | -2.49 |
| 2026-06 |       10 |  70    |      70    |  7    |
| 2026-07 |       15 | 605.3  |      73.33 | 40.35 |
| 2026-08 |        1 |   6.25 |     100    |  6.25 |

## by_hour

|   tpe_hour |   trades |    pnl |   win_rate |   avg |
|-----------:|---------:|-------:|-----------:|------:|
|          8 |       24 | 564.81 |      66.67 | 23.53 |
|          9 |       11 |  16.98 |      54.55 |  1.54 |
|         10 |        4 |  75.47 |     100    | 18.87 |
|         11 |        7 |  -4.42 |      42.86 | -0.63 |
|         12 |        8 |  29.43 |      50    |  3.68 |

## by_dow

|   dow |   trades |    pnl |   win_rate |   avg |
|------:|---------:|-------:|-----------:|------:|
|     0 |       20 | 389.7  |      65    | 19.49 |
|     1 |        8 | 131.8  |      62.5  | 16.47 |
|     2 |        5 |  49.09 |      60    |  9.82 |
|     3 |       11 |  85.97 |      54.55 |  7.82 |
|     4 |       10 |  25.7  |      60    |  2.57 |

## by_side

| side   |   trades |    pnl |   win_rate |   avg |
|:-------|---------:|-------:|-----------:|------:|
| long   |       23 |  30.49 |      60.87 |  1.33 |
| short  |       31 | 651.77 |      61.29 | 21.02 |

## by_reason

| reason    |   trades |     pnl |   win_rate |    avg |
|:----------|---------:|--------:|-----------:|-------:|
| stop      |        5 | -403.57 |       0    | -80.71 |
| time_stop |       49 | 1085.83 |      67.35 |  22.16 |

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