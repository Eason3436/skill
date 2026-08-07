"""Convert a parameter set between candle timeframes.

Every window in `params.json` is expressed in **bars**, so a config tuned on 5m
candles means something completely different on 15m ones. Comparing timeframes
honestly means holding the *wall-clock* meaning of each window fixed and only
changing its bar count — otherwise a 15m run is not the same strategy, it is a
strategy with a 3x longer anchor and a 3x longer hold.

Thresholds that are already unit-free (z bands, sigma multiples, fees) carry
over untouched.
"""

from __future__ import annotations

BAR_MINUTES = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
               "1H": 60, "4H": 240, "1D": 1440}

# Windows measured in bars. `min` keeps a window from collapsing to nothing when
# scaling up to a coarse timeframe.
BAR_COUNT_PARAMS = {
    "ma_len": 4,
    "atr_len": 5,
    "slope_len": 2,
    "regime_win": 40,
    "max_hold_bars": 2,
    "min_bars_left": 2,
    "entry_limit_ttl": 1,
}


def scale_params(p: dict, to_bar: str) -> dict:
    """Return a copy of `p` retimed from `p["bar"]` to `to_bar`.

    Bar counts are rescaled by the ratio of bar durations and rounded to the
    nearest whole bar, so each window keeps the same duration in minutes.
    """
    from_bar = p["bar"]
    if from_bar == to_bar:
        return dict(p)
    if to_bar not in BAR_MINUTES or from_bar not in BAR_MINUTES:
        raise ValueError(f"unsupported timeframe: {from_bar} -> {to_bar}")

    ratio = BAR_MINUTES[from_bar] / BAR_MINUTES[to_bar]
    out = dict(p)
    out["bar"] = to_bar
    for key, floor in BAR_COUNT_PARAMS.items():
        if key in out:
            out[key] = max(floor, int(round(out[key] * ratio)))
    return out


def describe(p: dict) -> str:
    """Render the bar-count windows as durations, for sanity-checking a config."""
    m = BAR_MINUTES[p["bar"]]

    def hhmm(bars: int) -> str:
        mins = bars * m
        return f"{mins // 60}h{mins % 60:02d}m" if mins >= 60 else f"{mins}m"

    parts = [f"bar={p['bar']}"]
    parts += [f"{k}={p[k]}({hhmm(p[k])})" for k in BAR_COUNT_PARAMS if k in p]
    return "  ".join(parts)
