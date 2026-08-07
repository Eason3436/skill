#!/usr/bin/env python3
"""Fetch OHLCV candles from OKX via the `okx` CLI and store them as CSV.

Direct calls to www.okx.com are blocked by the sandbox egress policy, so all
market data goes through the `okx market candles` CLI, which returns the raw
OKX v5 payload with `--json`.

OKX returns candles newest-first.  `--after <ts>` asks for candles strictly
older than `ts`, which is how we page backwards through history.

Usage
-----
    python src/fetch_data.py --inst MU-USDT-SWAP --bar 5m --start 2026-03-04
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BAR_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1H": 3_600_000,
    "4H": 14_400_000,
    "1D": 86_400_000,
}

# OKX v5 candle row: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
COLUMNS = ["ts", "open", "high", "low", "close", "volume", "vol_ccy", "vol_quote", "confirm"]


def run_cli(inst: str, bar: str, limit: int, after: int | None) -> list[list[str]]:
    cmd = ["okx", "market", "candles", inst, "--bar", bar, "--limit", str(limit), "--json"]
    if after is not None:
        cmd += ["--after", str(after)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"okx CLI failed ({proc.returncode}): {proc.stderr.strip()[:400]}")
    payload = json.loads(proc.stdout)
    # The CLI unwraps `data` for us, but tolerate the full envelope too.
    if isinstance(payload, dict):
        if payload.get("code") not in (None, "0"):
            raise RuntimeError(f"OKX error {payload.get('code')}: {payload.get('msg')}")
        payload = payload.get("data", [])
    return payload


def fetch(inst: str, bar: str, start_ms: int, end_ms: int, page: int = 300,
          pause: float = 0.15, max_pages: int = 5000) -> list[list[str]]:
    """Page backwards from `end_ms` until we reach `start_ms`."""
    step = BAR_MS[bar]
    rows: dict[int, list[str]] = {}
    cursor = end_ms
    pages = 0
    while cursor > start_ms and pages < max_pages:
        batch = run_cli(inst, bar, page, cursor)
        pages += 1
        if not batch:
            break
        oldest = cursor
        for row in batch:
            ts = int(row[0])
            if ts < start_ms:
                continue
            rows[ts] = row
            oldest = min(oldest, ts)
        sys.stderr.write(
            f"\rpage {pages:>4}  rows {len(rows):>7}  oldest "
            f"{datetime.fromtimestamp(oldest / 1000, timezone.utc):%Y-%m-%d %H:%M}"
        )
        sys.stderr.flush()
        if oldest >= cursor:  # no forward progress -> exhausted history
            break
        cursor = oldest
        # Guard against the endpoint returning a short page mid-history.
        if len(batch) < page and cursor - step <= start_ms:
            break
        time.sleep(pause)
    sys.stderr.write("\n")
    return [rows[ts] for ts in sorted(rows)]


def parse_day(s: str) -> int:
    return int(datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst", default="MU-USDT-SWAP")
    ap.add_argument("--bar", default="5m", choices=sorted(BAR_MS))
    ap.add_argument("--start", required=True, help="UTC date, YYYY-MM-DD")
    ap.add_argument("--end", default=None, help="UTC date, YYYY-MM-DD (default: now)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    start_ms = parse_day(args.start)
    end_ms = parse_day(args.end) if args.end else int(time.time() * 1000)

    est = (end_ms - start_ms) // BAR_MS[args.bar]
    print(f"fetching {args.inst} {args.bar}  ~{est} candles", file=sys.stderr)

    rows = fetch(args.inst, args.bar, start_ms, end_ms)
    if not rows:
        print("no data returned", file=sys.stderr)
        return 1

    out = Path(args.out) if args.out else (
        Path(__file__).resolve().parents[1] / "data" / f"{args.inst}_{args.bar}.csv"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        w.writerows(rows)

    first = datetime.fromtimestamp(int(rows[0][0]) / 1000, timezone.utc)
    last = datetime.fromtimestamp(int(rows[-1][0]) / 1000, timezone.utc)
    print(f"wrote {len(rows)} rows to {out}\n  {first:%Y-%m-%d %H:%M} -> {last:%Y-%m-%d %H:%M} UTC",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
