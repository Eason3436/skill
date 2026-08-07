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
| total_return_pct | -0.68 |
| cagr_pct | -1.60 |
| sharpe | -0.25 |
| sortino | -0.20 |
| max_dd_pct | -4.80 |
| calmar | -0.33 |
| win_rate_pct | 44.44 |
| profit_factor | 0.92 |
| expectancy | -1.52 |
| avg_win | 37.49 |
| avg_loss | -32.72 |
| max_consec_losses | 8 |
| avg_bars_held | 7.38 |
| total_costs | 124.01 |
| cost_pct_of_gross | 222.55 |
| final_equity | 9,931.71 |

## by_month

| month   |   trades |     pnl |   win_rate |    avg |
|:--------|---------:|--------:|-----------:|-------:|
| 2026-03 |        5 | -146.66 |       0    | -29.33 |
| 2026-04 |       12 |  -86.54 |      41.67 |  -7.21 |
| 2026-05 |        7 | -108.15 |      42.86 | -15.45 |
| 2026-06 |       13 |  122.16 |      53.85 |   9.4  |
| 2026-07 |        7 |  100.34 |      57.14 |  14.33 |
| 2026-08 |        1 |   50.56 |     100    |  50.56 |

## by_hour

|   tpe_hour |   trades |     pnl |   win_rate |    avg |
|-----------:|---------:|--------:|-----------:|-------:|
|          0 |       12 |  -19.12 |      41.67 |  -1.59 |
|          1 |        9 | -119.14 |      33.33 | -13.24 |
|          2 |        6 |  -19.82 |      33.33 |  -3.3  |
|          3 |        8 |  146.07 |      50    |  18.26 |
|          4 |       10 |  -56.28 |      60    |  -5.63 |

## by_dow

|   dow |   trades |     pnl |   win_rate |    avg |
|------:|---------:|--------:|-----------:|-------:|
|     0 |       10 | -174.22 |      20    | -17.42 |
|     1 |        7 | -107.59 |      28.57 | -15.37 |
|     2 |       11 |   35.96 |      54.55 |   3.27 |
|     3 |        6 |  211.94 |      66.67 |  35.32 |
|     4 |       11 |  -34.38 |      54.55 |  -3.13 |

## by_side

| side   |   trades |     pnl |   win_rate |   avg |
|:-------|---------:|--------:|-----------:|------:|
| long   |       15 |   96.66 |      46.67 |  6.44 |
| short  |       30 | -164.94 |      43.33 | -5.5  |

## by_reason

| reason    |   trades |     pnl |   win_rate |    avg |
|:----------|---------:|--------:|-----------:|-------:|
| stop      |        7 | -556.73 |       0    | -79.53 |
| time_stop |       38 |  488.44 |      52.63 |  12.85 |

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