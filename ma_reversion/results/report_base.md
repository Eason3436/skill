# MA-reversion backtest — MU-USDT-SWAP 5m

- Data: 2026-03-04 07:15 → 2026-08-07 04:25 UTC (44,895 bars)
- Session (Taipei): 08:00–16:00, Mon–Fri
- Sessions traded: 113 (10,719 of 44,895 bars, 23.9% of the clock)
- Execution: limit entry · 2.0bps maker / 5.0bps taker / 3.0bps slippage on taker fills
- Sizing: 0.75% equity risked per trade, max 3.0x notional

## Headline

| metric | value |
|---|---:|
| trades | 83 |
| trades_per_week | 3.75 |
| total_return_pct | 3.04 |
| cagr_pct | 7.30 |
| sharpe | 1.18 |
| sortino | 1.02 |
| max_dd_pct | -2.64 |
| calmar | 2.76 |
| win_rate_pct | 55.42 |
| profit_factor | 1.37 |
| expectancy | 3.66 |
| avg_win | 24.40 |
| avg_loss | -22.12 |
| max_consec_losses | 5 |
| avg_bars_held | 23.63 |
| total_costs | 135.77 |
| cost_pct_of_gross | 30.89 |
| final_equity | 10,303.75 |

## by_month

| month   |   trades |     pnl |   win_rate |   avg |
|:--------|---------:|--------:|-----------:|------:|
| 2026-03 |        9 |  -49.16 |      44.44 | -5.46 |
| 2026-04 |       13 |   95.94 |      46.15 |  7.38 |
| 2026-05 |       21 | -137.56 |      47.62 | -6.55 |
| 2026-06 |       16 |   40.77 |      56.25 |  2.55 |
| 2026-07 |       22 |  357.16 |      72.73 | 16.23 |
| 2026-08 |        2 |   -3.39 |      50    | -1.7  |

## by_hour

|   tpe_hour |   trades |    pnl |   win_rate |   avg |
|-----------:|---------:|-------:|-----------:|------:|
|          8 |       34 | 266.33 |      58.82 |  7.83 |
|          9 |       10 |  49.07 |      60    |  4.91 |
|         10 |        8 |  65.41 |      75    |  8.18 |
|         11 |       19 | -93.43 |      36.84 | -4.92 |
|         12 |       12 |  16.38 |      58.33 |  1.36 |

## by_dow

|   dow |   trades |    pnl |   win_rate |   avg |
|------:|---------:|-------:|-----------:|------:|
|     0 |       23 | 110.43 |      56.52 |  4.8  |
|     1 |       19 | 116.39 |      57.89 |  6.13 |
|     2 |       12 |  30.92 |      58.33 |  2.58 |
|     3 |       13 | 142.73 |      61.54 | 10.98 |
|     4 |       16 | -96.72 |      43.75 | -6.04 |

## by_side

| side   |   trades |    pnl |   win_rate |   avg |
|:-------|---------:|-------:|-----------:|------:|
| long   |       41 |  52.65 |      53.66 |  1.28 |
| short  |       42 | 251.1  |      57.14 |  5.98 |

## by_reason

| reason    |   trades |     pnl |   win_rate |    avg |
|:----------|---------:|--------:|-----------:|-------:|
| stop      |        4 | -317.59 |       0    | -79.4  |
| time_stop |       79 |  621.35 |      58.23 |   7.87 |

## Parameters

```json
{
  "inst": "MU-USDT-SWAP",
  "bar": "5m",
  "tick_size": 0.01,
  "lot_size": 0.01,
  "session_start_hour": 8,
  "session_end_hour": 16,
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