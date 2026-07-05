"""Data sources for the TSM weekend Bollinger-band backtest.

Two venues are supported, both returning an identical, timezone-aware
30-minute OHLCV frame:

  * ``BybitSource``  -> Bybit v5 ``/v5/market/kline`` (linear perpetuals).
                       This is the venue the strategy spec targets.  Note that
                       Bybit's API is fronted by CloudFront and is geo-blocked
                       from some regions; run it from a location Bybit allows.
  * ``OKXSource``    -> OKX ``/api/v5/market/history-candles``.  OKX lists the
                       same TSM tokenized-stock perpetual (``TSM-USDT-SWAP``)
                       and is the working fallback used to produce the bundled
                       report.

Both fetchers page all the way back to listing and return a pandas DataFrame
indexed by UTC timestamp with columns ``open, high, low, close, volume``.
"""

from __future__ import annotations

import time
import datetime as dt
from typing import Optional

import requests
import pandas as pd

# 30 minutes expressed in milliseconds.
_HALF_HOUR_MS = 30 * 60 * 1000


def _empty_frame() -> pd.DataFrame:
    idx = pd.DatetimeIndex([], tz="UTC", name="timestamp")
    return pd.DataFrame(
        {c: pd.Series(dtype="float64") for c in ("open", "high", "low", "close", "volume")},
        index=idx,
    )


def _finalize(rows: dict[int, list[float]]) -> pd.DataFrame:
    """Turn ``{ms_timestamp: [o,h,l,c,v]}`` into a sorted, deduped UTC frame."""
    if not rows:
        return _empty_frame()
    ts = sorted(rows)
    data = {
        "open": [rows[t][0] for t in ts],
        "high": [rows[t][1] for t in ts],
        "low": [rows[t][2] for t in ts],
        "close": [rows[t][3] for t in ts],
        "volume": [rows[t][4] for t in ts],
    }
    idx = pd.to_datetime(ts, unit="ms", utc=True)
    idx.name = "timestamp"
    return pd.DataFrame(data, index=idx)


class BybitSource:
    """Fetch 30m klines from Bybit v5 (linear/USDT perpetual)."""

    # bytick is Bybit's mirror host; either works where Bybit is reachable.
    HOSTS = ("https://api.bybit.com", "https://api.bytick.com")

    def __init__(self, category: str = "linear", session: Optional[requests.Session] = None):
        self.category = category
        self.s = session or requests.Session()

    def _get(self, path: str, params: dict) -> dict:
        last_err = None
        for host in self.HOSTS:
            try:
                r = self.s.get(host + path, params=params, timeout=30)
                r.raise_for_status()
                return r.json()
            except Exception as e:  # try the mirror before giving up
                last_err = e
        raise RuntimeError(f"Bybit request failed on all hosts: {last_err}")

    def fetch_30m(self, symbol: str = "TSMUSDT", start_ms: Optional[int] = None) -> pd.DataFrame:
        """Page backward from now to ``start_ms`` (or full listing history)."""
        rows: dict[int, list[float]] = {}
        end = None  # Bybit returns bars with start < ``end``; None = now
        while True:
            params = {"category": self.category, "symbol": symbol, "interval": "30", "limit": 1000}
            if end is not None:
                params["end"] = end
            payload = self._get("/v5/market/kline", params)
            lst = payload.get("result", {}).get("list", [])
            if not lst:
                break
            for k in lst:
                # [startTime, open, high, low, close, volume, turnover]
                t = int(k[0])
                rows[t] = [float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])]
            oldest = min(int(k[0]) for k in lst)
            if start_ms is not None and oldest <= start_ms:
                break
            new_end = oldest - 1
            if end is not None and new_end >= end:
                break  # no progress -> reached the start of history
            end = new_end
            if len(lst) < 1000:
                break
            time.sleep(0.15)
        df = _finalize(rows)
        if start_ms is not None and not df.empty:
            df = df[df.index >= pd.to_datetime(start_ms, unit="ms", utc=True)]
        return df


class OKXSource:
    """Fetch 30m klines from OKX ``history-candles`` (paged backward)."""

    HOST = "https://www.okx.com"

    def __init__(self, session: Optional[requests.Session] = None):
        self.s = session or requests.Session()

    def fetch_30m(self, symbol: str = "TSM-USDT-SWAP", start_ms: Optional[int] = None) -> pd.DataFrame:
        rows: dict[int, list[float]] = {}
        after = None  # returns bars with ts < ``after``
        while True:
            params = {"instId": symbol, "bar": "30m", "limit": 100}
            if after is not None:
                params["after"] = after
            r = self.s.get(self.HOST + "/api/v5/market/history-candles", params=params, timeout=30)
            r.raise_for_status()
            payload = r.json()
            lst = payload.get("data", [])
            if not lst:
                break
            for k in lst:
                # [ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
                t = int(k[0])
                rows[t] = [float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])]
            oldest = min(int(k[0]) for k in lst)
            if start_ms is not None and oldest <= start_ms:
                break
            after = oldest
            if len(lst) < 100:
                break
            time.sleep(0.12)
        df = _finalize(rows)
        if start_ms is not None and not df.empty:
            df = df[df.index >= pd.to_datetime(start_ms, unit="ms", utc=True)]
        return df


def get_source(name: str):
    name = name.lower()
    if name == "bybit":
        return BybitSource()
    if name == "okx":
        return OKXSource()
    raise ValueError(f"unknown source: {name!r} (expected 'bybit' or 'okx')")


DEFAULT_SYMBOLS = {"bybit": "TSMUSDT", "okx": "TSM-USDT-SWAP"}
