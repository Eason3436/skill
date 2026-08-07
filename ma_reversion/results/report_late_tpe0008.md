# MA-reversion backtest — MU-USDT-SWAP 5m

- Data: 2026-03-04 07:15 → 2026-08-07 04:25 UTC (44,895 bars)
- Session (Taipei): 00:00–08:00, Mon–Fri
- Sessions traded: 112 (10,752 of 44,895 bars, 23.9% of the clock)
- Execution: limit entry · 2.0bps maker / 5.0bps taker / 3.0bps slippage on taker fills
- Sizing: 0.75% equity risked per trade, max 3.0x notional

## Headline

| metric | value |
|---|---:|
| trades | 53 |
| trades_per_week | 2.39 |
| total_return_pct | -4.16 |
| cagr_pct | -9.51 |
| sharpe | -2.37 |
| sortino | -1.50 |
| max_dd_pct | -6.49 |
| calmar | -1.47 |
| win_rate_pct | 47.17 |
| profit_factor | 0.46 |
| expectancy | -7.84 |
| avg_win | 14.03 |
| avg_loss | -27.37 |
| max_consec_losses | 4 |
| avg_bars_held | 23.28 |
| total_costs | 106.13 |
| cost_pct_of_gross | 34.28 |
| final_equity | 9,584.30 |

## by_month

| month   |   trades |     pnl |   win_rate |    avg |
|:--------|---------:|--------:|-----------:|-------:|
| 2026-03 |        8 |   -4.17 |      62.5  |  -0.52 |
| 2026-04 |       10 | -206.43 |      20    | -20.64 |
| 2026-05 |        6 | -143.99 |      50    | -24    |
| 2026-06 |       15 | -200.27 |      26.67 | -13.35 |
| 2026-07 |       12 |  140    |      83.33 |  11.67 |
| 2026-08 |        2 |   -0.84 |      50    |  -0.42 |

## by_hour

|   tpe_hour |   trades |     pnl |   win_rate |    avg |
|-----------:|---------:|--------:|-----------:|-------:|
|          0 |       18 | -167.84 |      44.44 |  -9.32 |
|          1 |       10 | -126.32 |      30    | -12.63 |
|          2 |        6 |  -68.63 |      50    | -11.44 |
|          3 |       10 |   85.76 |      60    |   8.58 |
|          4 |        9 | -138.68 |      55.56 | -15.41 |

## by_dow

|   dow |   trades |     pnl |   win_rate |    avg |
|------:|---------:|--------:|-----------:|-------:|
|     0 |       15 | -253.23 |      26.67 | -16.88 |
|     1 |       16 |  -10.1  |      62.5  |  -0.63 |
|     2 |        7 |  -44.69 |      42.86 |  -6.38 |
|     3 |        6 |    2.49 |      66.67 |   0.41 |
|     4 |        9 | -110.18 |      44.44 | -12.24 |

## by_side

| side   |   trades |     pnl |   win_rate |    avg |
|:-------|---------:|--------:|-----------:|-------:|
| long   |       21 |  -87.43 |      57.14 |  -4.16 |
| short  |       32 | -328.27 |      40.62 | -10.26 |

## by_reason

| reason    |   trades |     pnl |   win_rate |    avg |
|:----------|---------:|--------:|-----------:|-------:|
| stop      |        3 | -247.26 |          0 | -82.42 |
| time_stop |       50 | -168.45 |         50 |  -3.37 |

## Parameters

```json
{
  "inst": "MU-USDT-SWAP",
  "bar": "5m",
  "tick_size": 0.01,
  "lot_size": 0.01,
  "session_start_hour": 0,
  "session_end_hour": 8,
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