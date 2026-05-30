#!/usr/bin/env python3
"""
stage1_scan.py — Deterministic Stage 1 full-universe scan for us-stock-mover-predictor.

目的:把「掃完全部 OKX instCategory=3 標的」從『AI 自律』變成『程式保證』。
AI 不可能漏掉任何一支(清單由程式列舉),也不可能腦補數字(數字來自 OKX 實際回傳)。

只用 Python 標準函式庫(urllib / json),無第三方相依。

用法:
    python3 scripts/stage1_scan.py              # 輸出 markdown Stage 1 表
    python3 scripts/stage1_scan.py --json        # 輸出 JSON(供程式/模型消費)
    python3 scripts/stage1_scan.py --min-vol 5   # 標記 24h 成交額 < 5M USDT 的低流動性標的

資料來源(OKX public,唯讀,免 API key):
    GET /api/v5/public/instruments?instType=SWAP   → 列舉 instCategory==3 & state==live
    GET /api/v5/market/tickers?instType=SWAP        → 一次取回全部 SWAP 的 last / sodUtc0 / high24h / vol

重要誠實標記:
    - `sodUtc0` 是 OKX 當日 (UTC0) 起始參考價,本 skill 以它作為 +3% 目標基準。
    - `high24h` 是「過去 24 小時」最高價,**含前一日**,只是 session high 的粗略代理。
      真正的盤前 / 盤中 session high 必須對漏斗存活者(20→7)另抓 candles 驗證(見 SKILL.md INV-15)。
    - 任何 instCategory=3 instrument 在 tickers 回傳中缺值 → 標 okx_live_data=unavailable,計入盲區,
      **不得腦補**。
"""

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

OKX_BASE = "https://www.okx.com"
INSTRUMENTS_URL = OKX_BASE + "/api/v5/public/instruments?instType=SWAP"
TICKERS_URL = OKX_BASE + "/api/v5/market/tickers?instType=SWAP"
TIMEOUT = 20
RETRIES = 4


def _get(url):
    """GET JSON with simple exponential backoff. Raises on final failure."""
    last_err = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "stage1-scan/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("code") not in ("0", 0):
                raise RuntimeError("OKX error code=%s msg=%s" % (payload.get("code"), payload.get("msg")))
            return payload.get("data", [])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, RuntimeError) as e:
            last_err = e
            if attempt < RETRIES - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
    raise RuntimeError("OKX request failed after %d attempts: %s (%s)" % (RETRIES, url, last_err))


def fetch_universe():
    """Return list of dicts for live instCategory==3 SWAP instruments."""
    rows = _get(INSTRUMENTS_URL)
    out = []
    for r in rows:
        if str(r.get("instCategory")) == "3" and r.get("state") == "live":
            out.append({
                "instId": r.get("instId"),
                "ruleType": r.get("ruleType", ""),  # 'normal' / 'pre_market'
            })
    return out


def fetch_tickers():
    """Return map instId -> ticker dict for all SWAP."""
    rows = _get(TICKERS_URL)
    return {r.get("instId"): r for r in rows}


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pct(a, b):
    """(a-b)/b*100, guarded."""
    if a is None or b in (None, 0):
        return None
    return (a - b) / b * 100.0


def build_rows(universe, tickers, min_vol_musd):
    rows = []
    for inst in universe:
        iid = inst["instId"]
        ticker = tickers.get(iid)
        symbol = iid.split("-")[0] if iid else iid
        if not ticker:
            rows.append({
                "ticker": symbol, "instId": iid, "ruleType": inst["ruleType"],
                "okx_live_data": "unavailable",
                "sodUtc0": None, "last": None,
                "current_vs_sodUtc0_pct": None, "high24h_vs_sodUtc0_pct": None,
                "high_to_current_pct": None, "vol_musd": None, "low_liquidity": None,
            })
            continue
        sod = _f(ticker.get("sodUtc0"))
        last = _f(ticker.get("last"))
        high24h = _f(ticker.get("high24h"))
        volccy = _f(ticker.get("volCcy24h"))  # quote-ccy (≈ USDT) volume
        vol_musd = round(volccy / 1e6, 2) if volccy is not None else None
        rows.append({
            "ticker": symbol, "instId": iid, "ruleType": inst["ruleType"],
            "okx_live_data": "available",
            "sodUtc0": sod, "last": last,
            "current_vs_sodUtc0_pct": pct(last, sod),
            "high24h_vs_sodUtc0_pct": pct(high24h, sod),
            "high_to_current_pct": pct(last, high24h),
            "vol_musd": vol_musd,
            "low_liquidity": (vol_musd is not None and vol_musd < min_vol_musd),
        })
    # sort by current vs sodUtc0 desc; None last
    rows.sort(key=lambda r: (r["current_vs_sodUtc0_pct"] is None,
                             -(r["current_vs_sodUtc0_pct"] or 0)))
    return rows


def fmt_pct(v):
    return "n/a" if v is None else "%+.2f%%" % v


def fmt_num(v):
    return "n/a" if v is None else ("%.4f" % v if v < 100 else "%.2f" % v)


def render_markdown(rows, meta):
    out = []
    out.append("## Stage 1 Raw Scan (program-generated — do NOT edit numbers by hand)")
    out.append("")
    out.append("generated_at_utc: %s" % meta["ts"])
    out.append("universe_source: %s" % meta["universe_source"])
    out.append("okx_universe_count: %d" % meta["okx_universe_count"])
    out.append("okx_live_supported_count: %d" % meta["okx_live_supported_count"])
    out.append("okx_unavailable_count: %d" % meta["okx_unavailable_count"])
    out.append("note: high24h_vs_sodUtc0 是 24h 高點(含前一日)代理,真正 session/premarket high 需對 20→7 另抓 candles 驗證 (INV-15)。")
    out.append("")
    out.append("| # | Ticker | OKX instId | live | ruleType | sodUtc0 | last | current_vs_sodUtc0 | high24h_vs_sodUtc0 | high_to_current | 24h_vol(M USDT) | low_liq |")
    out.append("|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---|")
    for i, r in enumerate(rows, 1):
        out.append("| %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            i, r["ticker"], r["instId"], r["okx_live_data"], r["ruleType"] or "-",
            fmt_num(r["sodUtc0"]), fmt_num(r["last"]),
            fmt_pct(r["current_vs_sodUtc0_pct"]), fmt_pct(r["high24h_vs_sodUtc0_pct"]),
            fmt_pct(r["high_to_current_pct"]),
            "n/a" if r["vol_musd"] is None else "%.2f" % r["vol_musd"],
            "" if not r["low_liquidity"] else "LOW",
        ))
    out.append("")
    out.append("### 程式已強制保證(AI 不得違反)")
    out.append("- 上表列出**每一支** live instCategory=3 標的,共 %d 支;AI 不得新增、刪除、或合併任何一列。" % meta["okx_universe_count"])
    out.append("- 上表所有數字來自 OKX 實際回傳;AI **不得修改或腦補**。後續 Stage 1 判斷欄(catalyst/sector/decision)才由 AI 填。")
    out.append("- `unavailable` 的 %d 支為資料盲區,只能 watch、不得 final buy,也不得假裝有數據。" % meta["okx_unavailable_count"])
    return "\n".join(out)


def main(argv):
    as_json = "--json" in argv
    min_vol_musd = 5.0
    if "--min-vol" in argv:
        try:
            min_vol_musd = float(argv[argv.index("--min-vol") + 1])
        except (IndexError, ValueError):
            pass

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    try:
        universe = fetch_universe()
        tickers = fetch_tickers()
    except Exception as e:  # noqa: BLE001 — surface clearly for the model
        msg = {
            "universe_source": "UNAVAILABLE",
            "error": str(e),
            "instruction": "OKX live discovery failed. Fall back to references/okx_stock_universe.md "
                           "and label universe_source: static_fallback. 不得用記憶中的清單或數字腦補。",
        }
        if as_json:
            print(json.dumps(msg, ensure_ascii=False, indent=2))
        else:
            print("## Stage 1 Raw Scan — FAILED\n")
            print("universe_source: UNAVAILABLE")
            print("error: %s" % e)
            print("\n" + msg["instruction"])
        return 2

    rows = build_rows(universe, tickers, min_vol_musd)
    live = sum(1 for r in rows if r["okx_live_data"] == "available")
    meta = {
        "ts": ts,
        "universe_source": "okx_live_instCategory_3",
        "okx_universe_count": len(rows),
        "okx_live_supported_count": live,
        "okx_unavailable_count": len(rows) - live,
    }

    if as_json:
        print(json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(rows, meta))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
