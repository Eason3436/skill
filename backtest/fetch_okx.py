"""Fetch full available 1H candle history for an OKX instrument.

OKX only serves ~100 rows per history request, so we page backwards using the
`after` cursor (returns candles strictly older than the given timestamp) until
the exchange stops returning data.
"""
import sys
import time
import json
import subprocess

BASE = "https://www.okx.com"


def _get(url):
    for attempt in range(5):
        try:
            out = subprocess.run(
                ["curl", "-s", "--fail", url],
                capture_output=True, text=True, timeout=40,
            )
            if out.returncode == 0 and out.stdout:
                return json.loads(out.stdout)
        except Exception:  # noqa: BLE001
            pass
        if attempt == 4:
            raise RuntimeError(f"request failed: {url}")
        time.sleep(2 ** attempt)
    return None


def fetch_all(inst_id, bar="1H"):
    """Return candles oldest->newest as list of [ts_ms, o, h, l, c, vol]."""
    rows = {}
    after = ""  # empty = start from most recent
    while True:
        url = (f"{BASE}/api/v5/market/history-candles?instId={inst_id}"
               f"&bar={bar}&limit=100")
        if after:
            url += f"&after={after}"
        d = _get(url)
        if d.get("code") != "0":
            raise RuntimeError(f"OKX error: {d}")
        data = d.get("data", [])
        if not data:
            break
        for r in data:
            ts = int(r[0])
            rows[ts] = [ts, float(r[1]), float(r[2]), float(r[3]),
                        float(r[4]), float(r[5])]
        # data is newest->oldest; oldest ts becomes next `after` cursor
        oldest = min(int(r[0]) for r in data)
        if after and str(oldest) == str(after):
            break
        after = oldest
        time.sleep(0.15)
    return [rows[k] for k in sorted(rows)]


if __name__ == "__main__":
    inst = sys.argv[1] if len(sys.argv) > 1 else "TSM-USDT-SWAP"
    bar = sys.argv[2] if len(sys.argv) > 2 else "1H"
    candles = fetch_all(inst, bar)
    out = f"backtest/data_{inst}_{bar}.json"
    with open(out, "w") as f:
        json.dump(candles, f)
    import datetime as dt
    print(f"{inst} {bar}: {len(candles)} candles")
    if candles:
        print("  from", dt.datetime.utcfromtimestamp(candles[0][0] / 1000),
              "to", dt.datetime.utcfromtimestamp(candles[-1][0] / 1000))
