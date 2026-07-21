#!/usr/bin/env python3
"""
Bollinger-Band scale-in / scale-out backtest for OKX US stock tokens.

STRATEGY (as specified by the user)
-----------------------------------
Timeframes tested: 8H (aggregated from 2 x native 4H) and 12H (native).
Bollinger Bands: middle = SMA(close, LENGTH); std = population stdev(close, LENGTH).
  LENGTH default 20 (classic Bollinger setting).

  Lower entry bands:  L1 = mid - 1.5*std   L2 = mid - 2.0*std   L3 = mid - 2.5*std
  Upper exit  bands:  U1 = mid + 1.5*std   U2 = mid + 2.0*std

Scale-IN (per cycle, starting flat):
  - price (candle LOW) reaches L1  -> buy tranche 1 = 30% of the position
  - price (candle LOW) reaches L2  -> buy tranche 2 = 30%
  - price (candle LOW) reaches L3  -> buy tranche 3 = 40%
  (a single deep candle can fill several tranches at once)

Scale-OUT:
  - If ALL three tranches filled (100% position):
        sell 60% when price (candle HIGH) reaches U1,
        sell the remaining 40% when price reaches U2.
  - If only 1 or 2 tranches filled (30% or 60% position):
        sell the WHOLE position at the "partial exit" band.
        Two variants are tested: partial exit at U1 (+1.5) and at U2 (+2).

Fills are assumed to occur exactly at the band price (resting limit orders).
Entry detection uses the candle LOW, exit detection uses the candle HIGH.
A cycle ends when the position returns to flat; a new cycle may then start.

OUTPUT
------
For each timeframe x partial-exit-variant, aggregated over all tokens:
  - number of cycles (every cycle fills at least tranche 1 = 30%)
  - occurrence count + rate that the position reached the 30% / 60% / 100% level
  - distribution of the FINAL position size (30% only / 60% only / 100%)
  - simple PnL summary for context
"""
import json
import os
import statistics
import sys

SCRATCH = "/tmp/claude-0/-home-user-skill/df70a287-5d81-5333-8362-86cd698b484f/scratchpad/cache"
LENGTH = int(os.environ.get("BB_LENGTH", "20"))

# tranche weights
W1, W2, W3 = 0.30, 0.30, 0.40


def _floats(env, default):
    v = os.environ.get(env)
    return [float(x) for x in v.split(",")] if v else list(default)


# sigma multipliers (configurable). "Add 0.5 to all" -> ENTRY=2,2.5,3 etc.
ENTRY_MULTS = _floats("ENTRY", [1.5, 2.0, 2.5])       # 3 entry tranches
EXIT_FULL = _floats("EXIT_FULL", [1.5, 2.0])          # full-position 60%/40% exits
PARTIAL_VARIANTS = _floats("PARTIAL", [1.5, 2.0])     # partial-position exit targets tested
E1, E2, E3 = ENTRY_MULTS
XF1, XF2 = EXIT_FULL


def load_bars(inst_id, bar):
    fp = os.path.join(SCRATCH, f"{inst_id}_{bar}.json")
    if not os.path.exists(fp):
        return []
    with open(fp) as f:
        rows = json.load(f)
    out = []
    for r in rows:
        # [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        try:
            out.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])))
        except (ValueError, IndexError):
            continue
    out.sort(key=lambda x: x[0])  # ascending time
    return out


def build_8h_from_4h(bars4h):
    """Aggregate aligned pairs of 4H candles into 8H candles.

    8H buckets are anchored to 0/8/16 UTC; each complete bucket holds two 4H
    candles. Incomplete buckets (only one 4H candle) are dropped.
    """
    bucket_ms = 8 * 3600 * 1000
    buckets = {}
    for ts, o, h, l, c in bars4h:
        key = ts // bucket_ms
        buckets.setdefault(key, []).append((ts, o, h, l, c))
    out = []
    for key, items in buckets.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda x: x[0])
        o = items[0][1]
        c = items[-1][4]
        h = max(x[2] for x in items)
        l = min(x[3] for x in items)
        out.append((key * bucket_ms, o, h, l, c))
    out.sort(key=lambda x: x[0])
    return out


def bollinger(bars, length):
    closes = [b[4] for b in bars]
    n = len(bars)
    mid = [None] * n
    sd = [None] * n
    for i in range(length - 1, n):
        window = closes[i - length + 1:i + 1]
        m = sum(window) / length
        var = sum((x - m) ** 2 for x in window) / length  # population (ddof=0)
        mid[i] = m
        sd[i] = var ** 0.5
    return mid, sd


def simulate(bars, length, partial_exit_mult):
    """Run the strategy on one series. Returns list of completed/open cycles.

    partial_exit_mult: 1.5 or 2.0 -> which upper band closes a partial position.
    """
    mid, sd = bollinger(bars, length)
    cycles = []
    # cycle state
    in_cycle = False
    f1 = f2 = f3 = False
    buy_cost = 0.0            # sum(weight_i * fill_price_i)
    sold60 = False           # for full-position management
    proceeds = 0.0
    start_ts = None

    def reset():
        nonlocal in_cycle, f1, f2, f3, buy_cost, sold60, proceeds, start_ts
        in_cycle = f1 = f2 = f3 = sold60 = False
        buy_cost = 0.0
        proceeds = 0.0
        start_ts = None

    for i in range(length - 1, len(bars)):
        m, s = mid[i], sd[i]
        if m is None:
            continue
        _, o, hi, lo, c = bars[i]
        L1, L2, L3 = m - E1 * s, m - E2 * s, m - E3 * s
        U1, U2 = m + XF1 * s, m + XF2 * s

        if not in_cycle:
            if lo <= L1:
                in_cycle = True
                start_ts = bars[i][0]
                f1 = True
                buy_cost += W1 * L1
                if lo <= L2:
                    f2 = True
                    buy_cost += W2 * L2
                if lo <= L3:
                    f3 = True
                    buy_cost += W3 * L3
            # after opening, fall through to allow exit on same bar? A bar that
            # dips to open the position and also rallies to the exit is extreme;
            # we let it be handled next bar. continue.
            continue

        # ---- already holding: first add-on tranches on further dips ----
        if not f2 and lo <= L2:
            f2 = True
            buy_cost += W2 * L2
        if not f3 and lo <= L3:
            f3 = True
            buy_cost += W3 * L3

        # ---- exits on rallies ----
        full = f1 and f2 and f3
        if full:
            if not sold60 and hi >= U1:
                sold60 = True
                proceeds += 0.60 * U1
            if sold60 and hi >= U2:
                proceeds += 0.40 * U2
                cycles.append(_close(start_ts, f1, f2, f3, buy_cost, proceeds, "full", True))
                reset()
        else:
            target = m + partial_exit_mult * s
            if hi >= target:
                # sell whole partial position at target
                filled_w = (W1 if f1 else 0) + (W2 if f2 else 0) + (W3 if f3 else 0)
                proceeds += filled_w * target
                cycles.append(_close(start_ts, f1, f2, f3, buy_cost, proceeds, "partial", True))
                reset()

    # unresolved position at end of data
    if in_cycle:
        cycles.append(_close(start_ts, f1, f2, f3, buy_cost, proceeds, "open", False))

    return cycles


def _close(start_ts, f1, f2, f3, buy_cost, proceeds, kind, resolved):
    max_level = 3 if f3 else (2 if f2 else 1)
    filled_w = (W1 if f1 else 0) + (W2 if f2 else 0) + (W3 if f3 else 0)
    return {
        "start_ts": start_ts,
        "max_level": max_level,       # 1=30%, 2=60%, 3=100%
        "filled_weight": filled_w,
        "buy_cost": buy_cost,
        "proceeds": proceeds,
        "kind": kind,                 # full / partial / open
        "resolved": resolved,
        "pnl": (proceeds - buy_cost) if resolved else None,
    }


def main():
    tokens = os.environ.get("TOKENS", "").split()
    if not tokens:
        # derive from cached files: <TOK>_4H.json / <TOK>_12H.json
        seen = set()
        for fn in sorted(os.listdir(SCRATCH)):
            if fn.endswith("_4H.json"):
                seen.add(fn[:-len("_4H.json")])
        tokens = sorted(seen)
    if not tokens:
        raise SystemExit("no tokens found in cache")

    results = {}  # (bar, variant) -> aggregate
    per_token = {}

    for bar_label in ["8H", "12H"]:
        for variant in PARTIAL_VARIANTS:
            results[(bar_label, variant)] = {
                "cycles": 0, "r30": 0, "r60": 0, "r100": 0,
                "final30": 0, "final60": 0, "final100": 0,
                "open": 0, "pnl_sum": 0.0, "wins": 0, "resolved": 0,
                "tokens_with_data": 0,
            }

    for tok in tokens:
        bars12 = load_bars(tok, "12H")
        bars4 = load_bars(tok, "4H")
        bars8 = build_8h_from_4h(bars4)
        series = {"8H": bars8, "12H": bars12}
        per_token[tok] = {}
        for bar_label, bars in series.items():
            if len(bars) < LENGTH + 5:
                continue
            for variant in PARTIAL_VARIANTS:
                cycles = simulate(bars, LENGTH, variant)
                agg = results[(bar_label, variant)]
                if cycles:
                    agg["tokens_with_data"] += 1
                for cy in cycles:
                    agg["cycles"] += 1
                    agg["r30"] += 1
                    if cy["max_level"] >= 2:
                        agg["r60"] += 1
                    if cy["max_level"] >= 3:
                        agg["r100"] += 1
                    if cy["max_level"] == 1:
                        agg["final30"] += 1
                    elif cy["max_level"] == 2:
                        agg["final60"] += 1
                    else:
                        agg["final100"] += 1
                    if not cy["resolved"]:
                        agg["open"] += 1
                    else:
                        agg["resolved"] += 1
                        agg["pnl_sum"] += cy["pnl"]
                        if cy["pnl"] > 0:
                            agg["wins"] += 1
                per_token[tok][(bar_label, variant)] = cycles

    # ---- print report ----
    print(f"\nBollinger scale-in/out backtest  |  BB length={LENGTH}, ddof=0")
    print(f"Tranches: 30% @ mid-1.5σ, 30% @ mid-2σ, 40% @ mid-2.5σ")
    print(f"Full-position exit: 60% @ +1.5σ, 40% @ +2σ   |   Partial exit variant shown per block")
    print("=" * 78)

    for bar_label in ["8H", "12H"]:
        for variant in PARTIAL_VARIANTS:
            a = results[(bar_label, variant)]
            n = a["cycles"]
            print(f"\n### Timeframe {bar_label}  |  partial-position exit @ +{variant}σ")
            print(f"  tokens with tradable data : {a['tokens_with_data']}")
            print(f"  total cycles (each fills ≥30%) : {n}")
            if n == 0:
                continue
            def pct(x):
                return f"{100.0*x/n:5.1f}%"
            print(f"  reached  30% (tranche1) : {a['r30']:5d}  ({pct(a['r30'])})")
            print(f"  reached  60% (tranche2) : {a['r60']:5d}  ({pct(a['r60'])})")
            print(f"  reached 100% (tranche3) : {a['r100']:5d}  ({pct(a['r100'])})")
            print(f"  -- final position size distribution --")
            print(f"    ended at  30% only    : {a['final30']:5d}  ({pct(a['final30'])})")
            print(f"    ended at  60% only    : {a['final60']:5d}  ({pct(a['final60'])})")
            print(f"    ended at 100%         : {a['final100']:5d}  ({pct(a['final100'])})")
            print(f"  unresolved (open at data end): {a['open']}")
            if a["resolved"]:
                wr = 100.0 * a["wins"] / a["resolved"]
                print(f"  resolved cycles: {a['resolved']}  win-rate: {wr:4.1f}%  "
                      f"sum PnL (per 1-unit notional/cycle): {a['pnl_sum']:.2f}")

    # machine-readable dump
    out = {f"{b}|{v}": results[(b, v)] for (b, v) in results}
    with open(os.path.join(os.path.dirname(__file__), "results.json"), "w") as f:
        json.dump(out, f, indent=2)

    # ---- per-token CSV (8H and 12H, partial-exit @ +1.5 variant) ----
    rows_csv = ["token,tf,bars,cycles,reach30,reach60,reach100,final30,final60,final100,open,resolved,wins,pnl"]
    for tok in tokens:
        for bar_label in ["8H", "12H"]:
            cyc = per_token.get(tok, {}).get((bar_label, PARTIAL_VARIANTS[0]))
            if not cyc:
                continue
            nb = len(load_bars(tok, "12H")) if bar_label == "12H" else len(build_8h_from_4h(load_bars(tok, "4H")))
            n = len(cyc)
            r60 = sum(1 for c in cyc if c["max_level"] >= 2)
            r100 = sum(1 for c in cyc if c["max_level"] >= 3)
            f30 = sum(1 for c in cyc if c["max_level"] == 1)
            f60 = sum(1 for c in cyc if c["max_level"] == 2)
            f100 = sum(1 for c in cyc if c["max_level"] == 3)
            op = sum(1 for c in cyc if not c["resolved"])
            res = sum(1 for c in cyc if c["resolved"])
            wins = sum(1 for c in cyc if c["resolved"] and c["pnl"] > 0)
            pnl = sum(c["pnl"] for c in cyc if c["resolved"])
            rows_csv.append(f"{tok.replace('-USDT-SWAP','')},{bar_label},{nb},{n},{n},{r60},{r100},{f30},{f60},{f100},{op},{res},{wins},{pnl:.2f}")
    with open(os.path.join(os.path.dirname(__file__), "per_token.csv"), "w") as f:
        f.write("\n".join(rows_csv) + "\n")
    print("\n(results.json + per_token.csv written)")


if __name__ == "__main__":
    main()
