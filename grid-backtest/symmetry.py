#!/usr/bin/env python3
"""Is long-vs-short asymmetry structural, or an artefact of a down-biased sample?

Compares a long grid in falling markets against a short grid in rising markets
at *matched* absolute move sizes, so the comparison is not contaminated by the
sample having larger drops than rallies.
"""
import argparse
import json
import statistics as st

BUCKETS = [(5, 10), (10, 15), (15, 20), (20, 25), (25, 100)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rolling", required=True)
    args = ap.parse_args()
    s = json.load(open(args.rolling))["samples"]

    print("=== matched-magnitude: aligned grid vs opposed grid ===")
    print("(long grid in a rally and short grid in a selloff are the ALIGNED cases;")
    print(" long grid in a selloff and short grid in a rally are the OPPOSED cases)")
    print()
    hdr = f"{'|move|':<12}{'n(up)':>7}{'n(dn)':>7}{'OPP long/dn':>13}{'OPP short/up':>14}{'ALI long/up':>13}{'ALI short/dn':>14}"
    print(hdr)
    print("-" * len(hdr))
    for lo, hi in BUCKETS:
        up = [r for r in s if lo <= r["bh"] < hi]
        dn = [r for r in s if lo <= -r["bh"] < hi]
        if not up and not dn:
            continue
        opp_l = st.mean([r["long"]["ret"] for r in dn]) if dn else float("nan")
        opp_s = st.mean([r["short"]["ret"] for r in up]) if up else float("nan")
        ali_l = st.mean([r["long"]["ret"] for r in up]) if up else float("nan")
        ali_s = st.mean([r["short"]["ret"] for r in dn]) if dn else float("nan")
        print(
            f"{f'{lo}-{hi}%':<12}{len(up):>7}{len(dn):>7}"
            f"{opp_l:>13.2f}{opp_s:>14.2f}{ali_l:>13.2f}{ali_s:>14.2f}"
        )
    print()

    # Position sizing: with the same USDT margin, a short grid's inventory sits at
    # higher prices, so it carries fewer base units. Quantify the leftover gap.
    print("=== opposed-case slope (return per 1% adverse move), matched buckets ===")
    for lo, hi in BUCKETS:
        up = [r for r in s if lo <= r["bh"] < hi]
        dn = [r for r in s if lo <= -r["bh"] < hi]
        if len(up) < 3 or len(dn) < 3:
            continue
        sl = st.mean([r["long"]["ret"] / -r["bh"] for r in dn])
        ss = st.mean([r["short"]["ret"] / r["bh"] for r in up])
        print(f"{f'{lo}-{hi}%':<12} long-in-selloff {sl:+6.3f}   short-in-rally {ss:+6.3f}   ratio {sl / ss if ss else float('nan'):.2f}x")
    print()

    print("=== where the P&L comes from, by alignment ===")
    up = [r for r in s if r["bh"] > 5]
    dn = [r for r in s if r["bh"] < -5]
    rows = [
        ("long grid,  rally  (aligned)", [r["long"] for r in up]),
        ("short grid, selloff (aligned)", [r["short"] for r in dn]),
        ("long grid,  selloff (opposed)", [r["long"] for r in dn]),
        ("short grid, rally   (opposed)", [r["short"] for r in up]),
    ]
    print(f"{'case':<32}{'total%':>9}{'grid%':>9}{'float%':>9}{'fills':>8}{'inRange%':>10}")
    print("-" * 77)
    for label, rs in rows:
        print(
            f"{label:<32}{st.mean([x['ret'] for x in rs]):>9.2f}"
            f"{st.mean([x['grid'] for x in rs]):>9.2f}"
            f"{st.mean([x['float'] for x in rs]):>9.2f}"
            f"{st.mean([x['fills'] for x in rs]):>8.0f}"
            f"{st.mean([x['in_range'] for x in rs]):>10.1f}"
        )


if __name__ == "__main__":
    main()
