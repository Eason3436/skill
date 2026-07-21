#!/usr/bin/env python3
"""
Fetch OHLCV history for all OKX US stock tokens (instCategory=3).

Pulls native 4H and 12H candles from the OKX public history-candles endpoint
(no API key required) and caches raw candles to disk as JSON so the backtest
can be re-run without re-downloading.

- 12H series is used directly.
- 8H series is built by aggregating pairs of 4H candles (2 x 4H = 8H),
  because OKX does not offer a native 8H bar.
"""
import json
import os
import time
import urllib.request
import urllib.error

BASE = "https://www.okx.com"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..",
                         # cache lives in scratchpad to keep the repo small
                         )
# Cache in scratchpad (not committed): large raw data.
SCRATCH = "/tmp/claude-0/-home-user-skill/df70a287-5d81-5333-8362-86cd698b484f/scratchpad/cache"
os.makedirs(SCRATCH, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}


def http_get(path):
    url = BASE + path
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError) as e:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed GET {url}")


def list_stock_tokens():
    d = http_get("/api/v5/public/instruments?instType=SWAP")
    # instCategory not returned by public/instruments; use instruments endpoint
    # Instead pull the category listing via the same field used by the CLI.
    out = []
    for it in d.get("data", []):
        pass
    # Fall back: the CLI already gave us the list; hardcode fetch via market.
    return out


def fetch_candles(inst_id, bar, max_bars=4000):
    """Paginate history-candles backward in time until exhausted."""
    all_rows = []
    after = None
    while len(all_rows) < max_bars:
        path = f"/api/v5/market/history-candles?instId={inst_id}&bar={bar}&limit=100"
        if after is not None:
            path += f"&after={after}"
        d = http_get(path)
        rows = d.get("data", [])
        if not rows:
            break
        all_rows.extend(rows)
        # data is newest-first; oldest ts is last row -> paginate with after=oldest ts
        after = rows[-1][0]
        time.sleep(0.12)  # stay well under 20 req / 2s
        if len(rows) < 100:
            break
    return all_rows


def main():
    tokens = os.environ.get("TOKENS", "").split()
    if not tokens:
        raise SystemExit("set TOKENS env var (space separated instIds)")
    bars = ["4H", "12H"]
    for i, tok in enumerate(tokens):
        for bar in bars:
            fp = os.path.join(SCRATCH, f"{tok}_{bar}.json")
            if os.path.exists(fp) and os.path.getsize(fp) > 2:
                continue
            rows = fetch_candles(tok, bar)
            with open(fp, "w") as f:
                json.dump(rows, f)
            print(f"[{i+1}/{len(tokens)}] {tok} {bar}: {len(rows)} bars", flush=True)


if __name__ == "__main__":
    main()
