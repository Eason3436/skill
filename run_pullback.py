#!/usr/bin/env python3
"""Effect of the '-7% below prior high' buy filter on 8h / 12h.

New rule: a buy (lower-band touch) is only taken when the entry price is at
least 7% below the prior swing high (running peak of highs before the bar).
Compares no-tranche all-in/all-out with the filter OFF vs ON, at 1x and 5x."""

import backtest_tsm as bt

TFS = {"8h": 2.0, "12h": 2.0}
PULLBACK = 0.07

cache_1h = [None]
print(f"Instrument: {bt.INST}  |  no-tranche all-in/all-out  |  BB={bt.BB_PERIOD}"
      f"  |  Capital: {bt.INITIAL_CAPITAL:,.0f}  |  Fee/side: {bt.FEE_RATE*100:.3f}%")
print(f"New rule: only buy when entry <= prior-high x (1 - {PULLBACK:.0%})")
print("=" * 100)
print(f"{'TF':>4} {'lev':>4} {'filter':>8} {'trades':>7} {'blocked':>8} {'liq':>4} "
      f"{'Return %':>11} {'MaxDD %':>9} {'FinalEq':>12}")
print("-" * 100)

for tf, k in TFS.items():
    candles = bt.get_timeframe_data(tf, cache_1h)
    for lev in (1, 5):
        for pb, tag in ((0.0, "off"), (PULLBACK, "-7%")):
            r = bt.backtest_leverage(candles, k, lev, min_pullback=pb)
            print(f"{tf:>4} {lev:>3}x {tag:>8} {r['trades']:>7} {r['blocked_buys']:>8} "
                  f"{r['liquidations']:>4} {r['total_return']*100:>11.2f} "
                  f"{r['max_drawdown']*100:>9.2f} {r['final_equity']:>12,.0f}")
    print("-" * 100)
print("blocked = buy signals skipped because price was < 7% off the prior high.")
