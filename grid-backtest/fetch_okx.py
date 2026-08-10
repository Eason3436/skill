#!/usr/bin/env python3
"""Fetch OKX public market data (candles + funding rate history) into local CSV cache.

Uses only public v5 endpoints, no API credentials required.
"""
import argparse
import csv
import json
import os
import time
import urllib.request

BASE = "https://www.okx.com"
BAR_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1H": 3_600_000,
    "2H": 7_200_000,
    "4H": 14_400_000,
    "1D": 86_400_000,
}


def _get(path, params, retries=5):
    qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    url = f"{BASE}{path}?{qs}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    )
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read().decode())
            if body.get("code") != "0":
                raise RuntimeError(f"OKX error {body.get('code')}: {body.get('msg')}")
            return body["data"]
        except Exception as e:  # noqa: BLE001 - network retry
            last = e
            time.sleep(2 ** i * 0.3)
    raise RuntimeError(f"request failed: {url}: {last}")


def fetch_candles(inst_id, bar, start_ms, end_ms):
    """Return candles ascending by ts within [start_ms, end_ms).

    Pages backwards with `after` (returns rows strictly older than the cursor).
    """
    rows = {}
    cursor = end_ms
    while cursor > start_ms:
        data = _get(
            "/api/v5/market/history-candles",
            {"instId": inst_id, "bar": bar, "after": cursor, "limit": 100},
        )
        if not data:
            break
        for c in data:
            ts = int(c[0])
            if ts >= start_ms:
                rows[ts] = [float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])]
        oldest = min(int(c[0]) for c in data)
        if oldest >= cursor:
            break
        cursor = oldest
        time.sleep(0.06)
    return [[ts] + rows[ts] for ts in sorted(rows)]


def fetch_funding(inst_id, start_ms, end_ms):
    rows = {}
    cursor = end_ms
    while cursor > start_ms:
        data = _get(
            "/api/v5/public/funding-rate-history",
            {"instId": inst_id, "after": cursor, "limit": 100},
        )
        if not data:
            break
        for f in data:
            ts = int(f["fundingTime"])
            if ts >= start_ms:
                rows[ts] = float(f.get("realizedRate") or f["fundingRate"])
        oldest = min(int(f["fundingTime"]) for f in data)
        if oldest >= cursor:
            break
        cursor = oldest
        time.sleep(0.06)
    return [[ts, rows[ts]] for ts in sorted(rows)]


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--insts", default="BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP,DOGE-USDT-SWAP")
    ap.add_argument("--bar", default="15m")
    ap.add_argument("--days", type=int, default=210)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    now = int(time.time() * 1000)
    end = now - now % BAR_MS[args.bar]
    start = end - args.days * 86_400_000

    for inst in args.insts.split(","):
        inst = inst.strip()
        candles = fetch_candles(inst, args.bar, start, end)
        write_csv(
            os.path.join(args.outdir, f"{inst}_{args.bar}.csv"),
            ["ts", "open", "high", "low", "close", "vol"],
            candles,
        )
        funding = fetch_funding(inst, start, end) if inst.endswith("SWAP") else []
        if funding:
            write_csv(
                os.path.join(args.outdir, f"{inst}_funding.csv"),
                ["ts", "rate"],
                funding,
            )
        print(f"{inst}: {len(candles)} candles, {len(funding)} funding points")


if __name__ == "__main__":
    main()
