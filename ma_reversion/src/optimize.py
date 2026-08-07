#!/usr/bin/env python3
"""Parameter search and walk-forward validation.

Two modes:

  grid  - score every combination on the whole sample. Useful for *sensitivity*:
          a real edge shows a broad plateau, an overfit one shows a lone spike.

  wf    - anchored walk-forward. Optimise on a training window, trade the next
          window untouched, roll forward. The concatenated out-of-sample
          equity is the only number worth trusting.

    python src/optimize.py grid --data data/MU-USDT-SWAP_5m.csv
    python src/optimize.py wf   --data data/MU-USDT-SWAP_5m.csv --train-days 60 --test-days 20
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import pandas as pd

from backtest import run_backtest
from features import add_features, load_candles
from metrics import summarize
from strategy import DEFAULT_PARAMS

ROOT = Path(__file__).resolve().parents[1]

# Kept deliberately small and on axes that mean different things, so the grid
# probes the idea rather than curve-fitting decimals.
# `ma_len` is deliberately NOT in the grid: 96 bars = 8h = exactly one session,
# a structural choice rather than a fitted one. Letting the optimiser pick the
# anchor length per fold was actively harmful - the folds that switched to a
# shorter anchor were the folds that lost.
GRID = {
    "z_entry": [2.0, 2.5, 3.0],
    "max_hold_bars": [24, 36],
    "min_bars_left": [24, 36, 48],
    "stop_sd": [4.0, 6.0],
    "z_stop": [4.5, 6.0],
}


# A 60-day training fold only produces ~35 trades, so the sample floor has to
# be low enough to leave any candidate at all - but high enough that a 5-trade
# fluke cannot win a fold.
MIN_TRADES = 15


def score(summ: dict) -> float:
    """Objective: risk-adjusted, penalised for thin samples.

    Sharpe alone happily crowns a 4-trade fluke, so require a trade count and
    haircut the score when drawdown is severe.
    """
    n = summ.get("trades", 0)
    if n < MIN_TRADES:
        return -99.0
    sharpe = summ.get("sharpe", float("nan"))
    if sharpe != sharpe:  # NaN
        return -99.0
    dd = abs(summ.get("max_dd_pct", 0.0))
    penalty = 1.0 if dd < 20 else 20.0 / dd
    confidence = min(1.0, n / (MIN_TRADES * 2.5))
    return sharpe * penalty * confidence


def evaluate(feat_cache: dict, df: pd.DataFrame, p: dict) -> dict:
    """Backtest with a cache on the feature-defining parameters."""
    key = (p["ma_len"], p["ma_type"], p["atr_len"], p["slope_len"], p["regime_win"],
           p["session_start_hour"], p["session_end_hour"], id(df))
    if key not in feat_cache:
        feat_cache[key] = add_features(df, p)
    return summarize(run_backtest(feat_cache[key], p))


def iter_grid(base: dict, grid: dict):
    keys = list(grid)
    for combo in itertools.product(*(grid[k] for k in keys)):
        p = dict(base)
        p.update(dict(zip(keys, combo)))
        yield p


def run_grid(df: pd.DataFrame, base: dict, grid: dict, cache: dict | None = None) -> pd.DataFrame:
    cache = {} if cache is None else cache
    rows = []
    combos = list(iter_grid(base, grid))
    for i, p in enumerate(combos, 1):
        summ = evaluate(cache, df, p)
        rows.append({**{k: p[k] for k in grid}, **summ, "score": score(summ)})
        print(f"\r  grid {i}/{len(combos)}", end="", flush=True)
    print()
    return pd.DataFrame(rows).sort_values("score", ascending=False)


def walk_forward(df: pd.DataFrame, base: dict, grid: dict,
                 train_days: int, test_days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    start, end = df.index[0], df.index[-1]
    folds = []
    oos_trades = []
    t0 = start
    fold = 0
    while True:
        train_end = t0 + pd.Timedelta(days=train_days)
        test_end = train_end + pd.Timedelta(days=test_days)
        if train_end >= end:
            break
        train = df[(df.index >= t0) & (df.index < train_end)]
        test = df[(df.index >= train_end) & (df.index < min(test_end, end))]
        if len(test) < 200:
            break
        fold += 1
        print(f"fold {fold}: train {t0:%Y-%m-%d}..{train_end:%Y-%m-%d}  "
              f"test {train_end:%Y-%m-%d}..{min(test_end, end):%Y-%m-%d}")

        tbl = run_grid(train, base, grid)
        best = tbl.iloc[0]
        p = dict(base)
        p.update({k: (int(best[k]) if isinstance(grid[k][0], int) else float(best[k])) for k in grid})

        # Trade the test window with the parameters frozen, but let the
        # indicators warm up on the tail of the training data.
        warmup = max(p["ma_len"], p["regime_win"]) + 5
        ctx = df[df.index < min(test_end, end)].iloc[-(len(test) + warmup):]
        feat = add_features(ctx, p)
        feat = feat[feat.index >= train_end]
        res = run_backtest(feat, p)
        summ = summarize(res)
        if not res["trades"].empty:
            t = res["trades"].copy()
            t["fold"] = fold
            oos_trades.append(t)

        folds.append({
            "fold": fold,
            "train_start": t0, "train_end": train_end, "test_end": min(test_end, end),
            **{f"p_{k}": p[k] for k in grid},
            "is_sharpe": float(best.get("sharpe", float("nan"))),
            "is_trades": int(best.get("trades", 0)),
            **{f"oos_{k}": v for k, v in summ.items()
               if k in ("trades", "total_return_pct", "sharpe", "max_dd_pct",
                        "win_rate_pct", "profit_factor")},
        })
        t0 = t0 + pd.Timedelta(days=test_days)  # anchored roll

    fold_tbl = pd.DataFrame(folds)
    all_oos = pd.concat(oos_trades, ignore_index=True) if oos_trades else pd.DataFrame()
    return fold_tbl, all_oos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["grid", "wf"])
    ap.add_argument("--data", required=True)
    ap.add_argument("--params", default=None)
    ap.add_argument("--train-days", type=int, default=60)
    ap.add_argument("--test-days", type=int, default=20)
    ap.add_argument("--outdir", default=str(ROOT / "results"))
    args = ap.parse_args()

    base = dict(DEFAULT_PARAMS)
    if args.params:
        base.update(json.loads(Path(args.params).read_text()))

    df = load_candles(args.data)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if args.mode == "grid":
        tbl = run_grid(df, base, GRID)
        tbl.to_csv(outdir / "grid.csv", index=False)
        cols = list(GRID) + ["trades", "total_return_pct", "sharpe", "max_dd_pct",
                             "win_rate_pct", "profit_factor", "score"]
        print(tbl[cols].head(15).to_string(index=False))
        print(f"\nwrote {outdir / 'grid.csv'}  ({len(tbl)} combos)")
    else:
        folds, oos = walk_forward(df, base, GRID, args.train_days, args.test_days)
        folds.to_csv(outdir / "walkforward_folds.csv", index=False)
        if not oos.empty:
            oos.to_csv(outdir / "walkforward_oos_trades.csv", index=False)
            eq = base["init_equity"] + oos["pnl"].cumsum()
            total = eq.iloc[-1] / base["init_equity"] - 1.0
            peak = eq.cummax()
            print("\n=== stitched out-of-sample ===")
            print(f"  trades          {len(oos)}")
            print(f"  total return    {total * 100:,.2f}%  (constant-risk, non-compounded)")
            print(f"  win rate        {(oos['pnl'] > 0).mean() * 100:,.2f}%")
            gl = -oos.loc[oos['pnl'] <= 0, 'pnl'].sum()
            print(f"  profit factor   {oos.loc[oos['pnl'] > 0, 'pnl'].sum() / gl:,.2f}"
                  if gl > 0 else "  profit factor   inf")
            print(f"  max drawdown    {((eq / peak - 1).min()) * 100:,.2f}%")
        print()
        print(folds.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
