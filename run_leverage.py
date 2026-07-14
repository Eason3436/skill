#!/usr/bin/env python3
"""Leverage comparison for the no-tranche (all-in/all-out) strategy on the
higher timeframes the user cares about: 8h and 12h, 1x vs 5x.

Note: no stop loss + leverage => liquidation is modelled (long is wiped on a
~(1/lev - mmr) adverse move; ~19.5% for 5x)."""

import backtest_tsm as bt

TFS = {"8h": 2.0, "12h": 2.0}
LEVERAGES = [1, 5]

cache_1h = [None]
print(f"Instrument: {bt.INST}  |  no-tranche all-in/all-out  |  BB={bt.BB_PERIOD}"
      f"  |  Capital: {bt.INITIAL_CAPITAL:,.0f}  |  Fee/side: {bt.FEE_RATE*100:.3f}%")
print("=" * 92)
print(f"{'TF':>4} {'±std':>5} {'lev':>4} {'trades':>7} {'liq':>4} "
      f"{'Return %':>11} {'MaxDD %':>9} {'FinalEq':>12} {'worstMAE %':>11}")
print("-" * 92)

for tf, k in TFS.items():
    candles = bt.get_timeframe_data(tf, cache_1h)
    for lev in LEVERAGES:
        r = bt.backtest_leverage(candles, k, lev)
        print(f"{tf:>4} {k:>5.1f} {lev:>3}x {r['trades']:>7} {r['liquidations']:>4} "
              f"{r['total_return']*100:>11.2f} {r['max_drawdown']*100:>9.2f} "
              f"{r['final_equity']:>12,.0f} {r['worst_mae']*100:>11.2f}")
print("=" * 92)
print("5x liquidation threshold ≈ 19.5% adverse move from entry. "
      "'liq' = number of liquidations; 'worstMAE' = worst adverse excursion seen.")
