# MA-reversion backtest — MU-USDT-SWAP 15m

- Data: 2026-03-04 07:15 → 2026-08-07 05:45 UTC (14,971 bars)
- Session (Taipei): 00:00–08:00, Mon–Fri
- Sessions traded: 112 (3,584 of 14,971 bars, 23.9% of the clock)
- Execution: limit entry · 2.0bps maker / 5.0bps taker / 3.0bps slippage on taker fills
- Sizing: 0.75% equity risked per trade, max 3.0x notional

## Headline

| metric | value |
|---|---:|
| trades | 45 |
| trades_per_week | 2.03 |
| total_return_pct | -0.34 |
| cagr_pct | -0.80 |
| sharpe | -0.25 |
| sortino | -0.18 |
| max_dd_pct | -2.48 |
| calmar | -0.32 |
| win_rate_pct | 44.44 |
| profit_factor | 0.92 |
| expectancy | -0.75 |
| avg_win | 19.09 |
| avg_loss | -16.63 |
| max_consec_losses | 8 |
| avg_bars_held | 8.00 |
| total_costs | 62.66 |
| cost_pct_of_gross | 217.98 |
| final_equity | 9,966.08 |

## by_month

| month   |   trades |    pnl |   win_rate |    avg |
|:--------|---------:|-------:|-----------:|-------:|
| 2026-03 |        5 | -86.75 |       0    | -17.35 |
| 2026-04 |       12 | -55.89 |      41.67 |  -4.66 |
| 2026-05 |        7 | -21.01 |      42.86 |  -3    |
| 2026-06 |       13 |  53.8  |      53.85 |   4.14 |
| 2026-07 |        7 |  50.52 |      57.14 |   7.22 |
| 2026-08 |        1 |  25.42 |     100    |  25.42 |

## by_hour

|   tpe_hour |   trades |    pnl |   win_rate |   avg |
|-----------:|---------:|-------:|-----------:|------:|
|          0 |       12 | -13.8  |      41.67 | -1.15 |
|          1 |        9 | -68.63 |      33.33 | -7.63 |
|          2 |        6 |  -9.33 |      33.33 | -1.56 |
|          3 |        8 |  56.86 |      50    |  7.11 |
|          4 |       10 |   0.99 |      60    |  0.1  |

## by_dow

|   dow |   trades |    pnl |   win_rate |   avg |
|------:|---------:|-------:|-----------:|------:|
|     0 |       10 | -54.69 |      20    | -5.47 |
|     1 |        7 | -68.27 |      28.57 | -9.75 |
|     2 |       11 |  18.62 |      54.55 |  1.69 |
|     3 |        6 | 109.26 |      66.67 | 18.21 |
|     4 |       11 | -38.84 |      54.55 | -3.53 |

## by_side

| side   |   trades |    pnl |   win_rate |   avg |
|:-------|---------:|-------:|-----------:|------:|
| long   |       15 |  63.2  |      46.67 |  4.21 |
| short  |       30 | -97.12 |      43.33 | -3.24 |

## by_reason

| reason    |   trades |    pnl |   win_rate |   avg |
|:----------|---------:|-------:|-----------:|------:|
| time_stop |       45 | -33.92 |      44.44 | -0.75 |

## Parameters

```json
{
  "inst": "MU-USDT-SWAP",
  "bar": "15m",
  "tick_size": 0.01,
  "lot_size": 0.01,
  "session_start_hour": 0,
  "session_end_hour": 8,
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