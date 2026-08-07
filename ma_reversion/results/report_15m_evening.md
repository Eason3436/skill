# MA-reversion backtest — MU-USDT-SWAP 15m

- Data: 2026-03-04 07:15 → 2026-08-07 05:45 UTC (14,971 bars)
- Session (Taipei): 16:00–24:00, Mon–Fri
- Sessions traded: 112 (3,584 of 14,971 bars, 23.9% of the clock)
- Execution: limit entry · 2.0bps maker / 5.0bps taker / 3.0bps slippage on taker fills
- Sizing: 0.75% equity risked per trade, max 3.0x notional

## Headline

| metric | value |
|---|---:|
| trades | 69 |
| trades_per_week | 3.12 |
| total_return_pct | -1.72 |
| cagr_pct | -4.01 |
| sharpe | -0.81 |
| sortino | -0.62 |
| max_dd_pct | -4.90 |
| calmar | -0.82 |
| win_rate_pct | 55.07 |
| profit_factor | 0.80 |
| expectancy | -2.49 |
| avg_win | 18.18 |
| avg_loss | -27.84 |
| max_consec_losses | 10 |
| avg_bars_held | 7.80 |
| total_costs | 86.27 |
| cost_pct_of_gross | 100.45 |
| final_equity | 9,827.85 |

## by_month

| month   |   trades |     pnl |   win_rate |    avg |
|:--------|---------:|--------:|-----------:|-------:|
| 2026-03 |        8 |   92.42 |      62.5  |  11.55 |
| 2026-04 |       12 |  -40.22 |      66.67 |  -3.35 |
| 2026-05 |       15 | -103.82 |      46.67 |  -6.92 |
| 2026-06 |       12 | -227.87 |      16.67 | -18.99 |
| 2026-07 |       19 |   85.57 |      73.68 |   4.5  |
| 2026-08 |        3 |   21.76 |      66.67 |   7.25 |

## by_hour

|   tpe_hour |   trades |     pnl |   win_rate |    avg |
|-----------:|---------:|--------:|-----------:|-------:|
|         16 |       19 | -141.67 |      47.37 |  -7.46 |
|         17 |       10 |  -13.6  |      60    |  -1.36 |
|         18 |       13 |   19.55 |      53.85 |   1.5  |
|         19 |       13 |  158.29 |      76.92 |  12.18 |
|         20 |       12 | -290.2  |      33.33 | -24.18 |
|         21 |        2 |   95.49 |     100    |  47.74 |

## by_dow

|   dow |   trades |     pnl |   win_rate |   avg |
|------:|---------:|--------:|-----------:|------:|
|     0 |       15 |  165.29 |      66.67 | 11.02 |
|     1 |       16 |  -47.87 |      56.25 | -2.99 |
|     2 |       14 | -105.38 |      50    | -7.53 |
|     3 |       15 | -138.17 |      46.67 | -9.21 |
|     4 |        9 |  -46.03 |      55.56 | -5.11 |

## by_side

| side   |   trades |     pnl |   win_rate |   avg |
|:-------|---------:|--------:|-----------:|------:|
| long   |       26 |   -9.2  |      61.54 | -0.35 |
| short  |       43 | -162.95 |      51.16 | -3.79 |

## by_reason

| reason    |   trades |     pnl |   win_rate |    avg |
|:----------|---------:|--------:|-----------:|-------:|
| stop      |        5 | -382.6  |       0    | -76.52 |
| time_stop |       64 |  210.45 |      59.38 |   3.29 |

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