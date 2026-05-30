#!/usr/bin/env python3
"""
stage35_kline.py — Deterministic Stage 3.5 multi-timeframe K-line pull for funnel survivors.

目的:把漏斗存活者(Stage 3 的 ~7 支)的 OKX 多時框 K 線抓取與基本結構量度,
從『AI 自律 / 腦補』改成『程式產出真實數據』。AI 只在真實 K 線上做判斷,
不得編造價格、結構或量能。

只用 Python 標準函式庫(urllib / json),無第三方相依。

用法:
    python3 scripts/stage35_kline.py NVDA MU SOXL           # 用 ticker(自動補 -USDT-SWAP)
    python3 scripts/stage35_kline.py NVDA-USDT-SWAP          # 或直接給 instId
    python3 scripts/stage35_kline.py --json NVDA MU          # JSON 輸出

資料來源(OKX public,唯讀,免 API key):
    GET /api/v5/market/ticker?instId=...                     → last / sodUtc0 / high24h
    GET /api/v5/market/candles?instId=...&bar=1m|5m|15m|1H|1Dutc&limit=...

誠實標記:
    - 結構標籤(HH/HL、LH/LL、mixed)與量能標籤是**簡單啟發式量度**,提供客觀輸入給 AI,
      不是最終結論;AI 仍須結合催化、VWAP、R:R 自行判斷(見 SKILL.md INV-13/INV-15/Stage 3.5)。
    - 任一時框缺資料 → 標 unavailable,**不得腦補**。若 15m/1h/1d 任一缺,最終不得優於
      confirmation_needed(INV-14)。
    - reference_close 用 OKX sodUtc0(當日 UTC0 起始參考);target_3pct = reference_close*1.03。
    - day_high 取今日 1Dutc candle 高點 = session high vs sodUtc0 基準(盤前/盤中當日最高)。
"""

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

OKX_BASE = "https://www.okx.com"
TIMEOUT = 20
RETRIES = 4
BARS = [("1m", 120), ("5m", 120), ("15m", 96), ("1H", 120), ("1Dutc", 30)]
PACE = 0.12  # 每個 request 之間的禮貌間隔(秒)


def _get(url):
    last_err = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "stage35-kline/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("code") not in ("0", 0):
                raise RuntimeError("OKX error code=%s msg=%s" % (payload.get("code"), payload.get("msg")))
            return payload.get("data", [])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, RuntimeError) as e:
            last_err = e
            if attempt < RETRIES - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError("OKX request failed after %d attempts: %s (%s)" % (RETRIES, url, last_err))


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pct(a, b):
    if a is None or b in (None, 0):
        return None
    return (a - b) / b * 100.0


def norm_inst(arg):
    return arg if "-" in arg else "%s-USDT-SWAP" % arg.upper()


def ts_to_str(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    except (TypeError, ValueError):
        return "n/a"


def fetch_ticker(inst):
    rows = _get(OKX_BASE + "/api/v5/market/ticker?instId=%s" % inst)
    time.sleep(PACE)
    return rows[0] if rows else None


def fetch_candles(inst, bar, limit):
    """Return list oldest->newest of dicts {ts,o,h,l,c,vol}. OKX returns newest first."""
    rows = _get(OKX_BASE + "/api/v5/market/candles?instId=%s&bar=%s&limit=%d" % (inst, bar, limit))
    time.sleep(PACE)
    out = []
    for r in rows:
        # [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        out.append({"ts": r[0], "o": _f(r[1]), "h": _f(r[2]), "l": _f(r[3]),
                    "c": _f(r[4]), "vol": _f(r[5])})
    out.reverse()
    return out


def classify_structure(candles):
    """Simple, honest heuristic on last up-to-12 candles. Returns label + raw recent highs/lows."""
    if not candles or len(candles) < 4:
        return {"label": "not_available", "recent_highs": [], "recent_lows": []}
    window = candles[-12:]
    highs = [c["h"] for c in window if c["h"] is not None]
    lows = [c["l"] for c in window if c["l"] is not None]
    if len(highs) < 4 or len(lows) < 4:
        return {"label": "not_available", "recent_highs": highs[-4:], "recent_lows": lows[-4:]}
    half = len(highs) // 2
    hh_rising = (sum(highs[half:]) / len(highs[half:])) > (sum(highs[:half]) / len(highs[:half]))
    ll_rising = (sum(lows[half:]) / len(lows[half:])) > (sum(lows[:half]) / len(lows[:half]))
    if hh_rising and ll_rising:
        label = "higher_highs_higher_lows"
    elif (not hh_rising) and (not ll_rising):
        label = "lower_highs_lower_lows"
    else:
        label = "mixed"
    return {"label": label,
            "recent_highs": [round(x, 4) for x in highs[-4:]],
            "recent_lows": [round(x, 4) for x in lows[-4:]]}


def classify_volume(candles):
    if not candles or len(candles) < 6:
        return "not_available"
    vols = [c["vol"] for c in candles if c["vol"] is not None]
    if len(vols) < 6:
        return "not_available"
    recent = vols[-3:]
    base = vols[-13:-3] if len(vols) >= 13 else vols[:-3]
    if not base:
        return "not_available"
    r = sum(recent) / len(recent)
    b = sum(base) / len(base)
    if b == 0:
        return "not_available"
    ratio = r / b
    if ratio >= 1.8:
        return "elevated_possible_blowoff"
    if ratio >= 1.2:
        return "rising"
    if ratio <= 0.6:
        return "fading"
    return "stable"


def analyze(inst):
    ticker = fetch_ticker(inst)
    res = {"instId": inst, "ticker": inst.split("-")[0]}
    if not ticker:
        res["okx_live_data"] = "unavailable"
        return res
    res["okx_live_data"] = "available"
    sod = _f(ticker.get("sodUtc0"))
    last = _f(ticker.get("last"))
    ticker_ts = ticker.get("ts")
    res["ticker_ts"] = ts_to_str(ticker_ts)

    timeframes = {}
    candle_sets = {}
    for bar, limit in BARS:
        try:
            cs = fetch_candles(inst, bar, limit)
        except Exception as e:  # noqa: BLE001
            timeframes[bar] = {"available": False, "error": str(e)}
            candle_sets[bar] = None
            continue
        if not cs:
            timeframes[bar] = {"available": False}
            candle_sets[bar] = None
            continue
        candle_sets[bar] = cs
        struct = classify_structure(cs)
        timeframes[bar] = {
            "available": True,
            "n_candles": len(cs),
            "last_close": cs[-1]["c"],
            "last_candle_ts": ts_to_str(cs[-1]["ts"]),
            "structure": struct["label"],
            "recent_highs": struct["recent_highs"],
            "recent_lows": struct["recent_lows"],
            "volume_signal": classify_volume(cs),
        }
    res["timeframes"] = timeframes

    # price semantics from ticker + today's 1Dutc candle
    day = candle_sets.get("1Dutc")
    day_high = day[-1]["h"] if day else _f(ticker.get("high24h"))
    ref = sod
    target = ref * 1.03 if ref else None
    res["price_semantics"] = {
        "reference_close_sodUtc0": ref,
        "target_3pct_price": round(target, 4) if target else None,
        "current_price": last,
        "current_vs_ref_pct": pct(last, ref),
        "day_high": day_high,
        "day_high_vs_ref_pct": pct(day_high, ref),
        "high_to_current_pullback_pct": pct(last, day_high),
        "did_hit_plus_3": (day_high is not None and target is not None and day_high >= target),
    }
    # timestamp alignment: ticker vs latest 1m candle
    m1 = candle_sets.get("1m")
    align = "unknown"
    if m1 and ticker_ts:
        try:
            diff = abs(int(ticker_ts) - int(m1[-1]["ts"])) / 1000.0
            align = "aligned" if diff <= 180 else "mixed"
        except (TypeError, ValueError):
            align = "unknown"
    res["timestamp_alignment"] = align
    missing_higher = [b for b in ("15m", "1H", "1Dutc")
                      if not timeframes.get(b, {}).get("available")]
    res["higher_tf_missing"] = missing_higher
    res["max_actionability_cap"] = "confirmation_needed" if missing_higher else "none"
    return res


def render(results):
    out = []
    out.append("## Stage 3.5 K-line Pull (program-generated — numbers from OKX, do NOT fabricate)")
    out.append("")
    out.append("generated_at_utc: %s" % datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"))
    out.append("note: 結構/量能標籤為啟發式量度,提供客觀輸入;AI 須結合催化/VWAP/R:R 自行判斷 (INV-13)。")
    out.append("")
    for r in results:
        out.append("### %s (%s)" % (r["ticker"], r["instId"]))
        if r.get("okx_live_data") != "available":
            out.append("- okx_live_data: **unavailable** → 資料盲區,不得 final buy,不得腦補。")
            out.append("")
            continue
        ps = r["price_semantics"]
        out.append("- okx_live_data: available | ticker_ts: %s | timestamp_alignment: %s"
                   % (r["ticker_ts"], r["timestamp_alignment"]))
        out.append("- reference_close(sodUtc0): %s | target_3pct: %s | current: %s (%s vs ref)"
                   % (ps["reference_close_sodUtc0"], ps["target_3pct_price"], ps["current_price"],
                      "n/a" if ps["current_vs_ref_pct"] is None else "%+.2f%%" % ps["current_vs_ref_pct"]))
        out.append("- day_high: %s (%s vs ref) | high_to_current_pullback: %s | did_hit_plus_3: %s"
                   % (ps["day_high"],
                      "n/a" if ps["day_high_vs_ref_pct"] is None else "%+.2f%%" % ps["day_high_vs_ref_pct"],
                      "n/a" if ps["high_to_current_pullback_pct"] is None else "%+.2f%%" % ps["high_to_current_pullback_pct"],
                      ps["did_hit_plus_3"]))
        if r["higher_tf_missing"]:
            out.append("- ⚠️ higher_tf_missing: %s → max_actionability_cap: confirmation_needed (INV-14)"
                       % ", ".join(r["higher_tf_missing"]))
        out.append("")
        out.append("| timeframe | available | n | last_close | structure | volume | last_candle_ts |")
        out.append("|---|---|---:|---:|---|---|---|")
        for bar, _ in BARS:
            tf = r["timeframes"].get(bar, {})
            if not tf.get("available"):
                out.append("| %s | no | - | - | - | - | - |" % bar)
            else:
                out.append("| %s | yes | %d | %s | %s | %s | %s |" % (
                    bar, tf["n_candles"], tf["last_close"], tf["structure"],
                    tf["volume_signal"], tf["last_candle_ts"]))
        out.append("")
    return "\n".join(out)


def main(argv):
    as_json = "--json" in argv
    names = [a for a in argv if not a.startswith("--")]
    if not names:
        sys.stderr.write("usage: stage35_kline.py [--json] TICKER [TICKER ...]\n")
        return 1
    insts = [norm_inst(n) for n in names]
    results = []
    for inst in insts:
        try:
            results.append(analyze(inst))
        except Exception as e:  # noqa: BLE001
            results.append({"instId": inst, "ticker": inst.split("-")[0],
                            "okx_live_data": "unavailable", "error": str(e)})
    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(render(results))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
