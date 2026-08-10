#!/usr/bin/env python3
"""Sanity checks for the grid engine on synthetic price paths."""
import sys

from grid_backtest import build_levels, run_grid

MS = 900_000


def path_to_candles(prices):
    """One candle per price step, open=prev close=cur, high/low bracket them."""
    out = []
    for k in range(1, len(prices)):
        o, c = prices[k - 1], prices[k]
        out.append((k * MS, o, max(o, c), min(o, c), c))
    return out


def approx(a, b, tol):
    return abs(a - b) <= tol


def main():
    fails = []
    lower, upper, ngrids, inv = 100.0, 200.0, 10, 10000.0
    levels = build_levels(lower, upper, ngrids, "arithmetic")
    step = levels[1] - levels[0]  # 10.0

    # 1) Round trip 150 -> 160 -> 150: long grid books exactly one grid of profit.
    c = path_to_candles([150, 160, 150])
    r = run_grid(c, [], "long", lower, upper, ngrids, inv, fee_rate=0.0)
    expect = r.qty_per_grid * step
    if not approx(r.grid_profit, expect, 1e-6):
        fails.append(f"long round trip grid_profit {r.grid_profit} != {expect}")
    if r.matched != 1:
        fails.append(f"long round trip matched {r.matched} != 1")
    if not approx(r.total_pnl, expect, 1e-6):
        fails.append(f"long round trip total {r.total_pnl} != {expect} (price returned to start)")

    # 2) Mirror: 150 -> 140 -> 150 short grid books exactly one grid.
    c = path_to_candles([150, 140, 150])
    r = run_grid(c, [], "short", lower, upper, ngrids, inv, fee_rate=0.0)
    expect = r.qty_per_grid * step
    if not approx(r.grid_profit, expect, 1e-6):
        fails.append(f"short round trip grid_profit {r.grid_profit} != {expect}")
    if not approx(r.total_pnl, expect, 1e-6):
        fails.append(f"short round trip total {r.total_pnl} != {expect}")

    # 3) Ten oscillations pay ten grids, and a long grid must never go short.
    prices = [150]
    for _ in range(10):
        prices += [160, 150]
    c = path_to_candles(prices)
    r = run_grid(c, [], "long", lower, upper, ngrids, inv, fee_rate=0.0)
    if not approx(r.grid_profit, r.qty_per_grid * step * 10, 1e-6):
        fails.append(f"10 oscillations grid_profit {r.grid_profit}")
    if r.final_pos < -1e-9:
        fails.append(f"long grid went short: {r.final_pos}")

    # 4) Monotonic rise to the top: long grid ends flat, short grid ends max short.
    c = path_to_candles([150, 210])
    rl = run_grid(c, [], "long", lower, upper, ngrids, inv, fee_rate=0.0)
    rs = run_grid(c, [], "short", lower, upper, ngrids, inv, fee_rate=0.0)
    if not approx(rl.final_pos, 0.0, 1e-9):
        fails.append(f"long grid not flat at top: {rl.final_pos}")
    if rs.final_pos >= 0:
        fails.append(f"short grid should be short at top: {rs.final_pos}")
    if rl.total_pnl <= 0:
        fails.append(f"long grid should profit on a rise: {rl.total_pnl}")
    if rs.total_pnl >= 0:
        fails.append(f"short grid should lose on a rise: {rs.total_pnl}")

    # 5) Long/short symmetry: mirrored price paths fill the same grids. Absolute
    # profit still differs because a short grid's inventory sits at higher prices
    # and therefore costs more margin per unit, so compare per traded unit.
    up = path_to_candles([150, 170, 155, 180, 150])
    dn = path_to_candles([150, 130, 145, 120, 150])
    a = run_grid(up, [], "long", lower, upper, ngrids, inv, fee_rate=0.0)
    b = run_grid(dn, [], "short", lower, upper, ngrids, inv, fee_rate=0.0)
    if a.matched != b.matched or a.trades != b.trades:
        fails.append(f"symmetry broken: long {a.matched}/{a.trades} vs short {b.matched}/{b.trades}")
    if not approx(a.grid_profit / a.qty_per_grid, b.grid_profit / b.qty_per_grid, 1e-6):
        fails.append(
            f"per-unit symmetry broken: {a.grid_profit / a.qty_per_grid}"
            f" vs {b.grid_profit / b.qty_per_grid}"
        )

    # 6) Fees scale with fill count.
    r0 = run_grid(up, [], "long", lower, upper, ngrids, inv, fee_rate=0.0)
    r1 = run_grid(up, [], "long", lower, upper, ngrids, inv, fee_rate=0.001)
    if not r1.total_pnl < r0.total_pnl:
        fails.append("fees did not reduce PnL")
    if r1.trades != r0.trades:
        fails.append("fee rate changed the fill count")

    # 7) Funding: a long position pays a positive funding rate.
    c = path_to_candles([150, 150, 150])
    f = [(2 * MS, 0.0001)]
    rl = run_grid(c, f, "long", lower, upper, ngrids, inv, fee_rate=0.0)
    rs = run_grid(c, f, "short", lower, upper, ngrids, inv, fee_rate=0.0)
    if rl.funding >= 0:
        fails.append(f"long should pay funding: {rl.funding}")
    if rs.funding <= 0:
        fails.append(f"short should receive funding: {rs.funding}")

    # 8) PnL decomposition adds up to the reported total.
    r = run_grid(up, [(3 * MS, 0.0002)], "long", lower, upper, ngrids, inv, fee_rate=0.0002)
    recon = r.grid_profit + r.float_pnl - r.fees + r.funding
    if not approx(recon, r.total_pnl, 1e-6):
        fails.append(f"decomposition {recon} != total {r.total_pnl}")

    # 9) Price leaving the range stops trading (no fills beyond the boundary).
    c = path_to_candles([150, 260, 150])
    r = run_grid(c, [], "long", lower, upper, ngrids, inv, fee_rate=0.0)
    if r.trades > ngrids + 2:
        fails.append(f"traded beyond the grid boundary: {r.trades} fills")

    if fails:
        print("FAIL")
        for f_ in fails:
            print("  -", f_)
        sys.exit(1)
    print("all engine checks passed")


if __name__ == "__main__":
    main()
