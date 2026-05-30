#!/usr/bin/env python3
"""
sweep_breadth.py — Deterministic movers ranking + Sweep + theme-breadth/decoupling counts.

補上 Stage 2 的「數據面」與兩個 Sweep(INV-16)、籃子廣度/脫鉤計數(INV-7/INV-10):
這些全是純算術,卻最容易被 AI 漏算或憑印象說「沒有別的標的了」。本腳本用 OKX 實際
數據強制算出來,讓:
- Missed Winner Sweep / Intraday Hit Sweep 的清單由程式列舉,AI 不得遺漏。
- 籃子 decoupling 與板塊 breadth 的「成員計數」由程式算,AI 不得用「BTC 弱所以整組砍」搪塞。

催化、新聞、lifecycle、負面搜尋等**判讀**仍由 AI 做(本腳本不碰),這是誠實邊界。

只用 Python 標準函式庫。資料來源同 stage1(instruments + tickers,兩個 call)。

用法:
    python3 scripts/sweep_breadth.py                 # markdown:漲幅榜 + sweep + breadth
    python3 scripts/sweep_breadth.py --json
    python3 scripts/sweep_breadth.py --top 20        # 漲幅榜顯示前 N(預設 15)

門檻(對齊 SKILL.md INV-16):
    current_vs_sodUtc0 >= +2.5%   → Missed Winner 候選
    high24h_vs_sodUtc0 >= +3.0%   → Intraday Hit / 「曾觸 +3%」候選
    板塊內 >= 2 成員 current>=+2% 或 high>=+3% → decoupling/breadth 觸發

theme 分組:盡力從 references/okx_stock_universe.md 的 Suggested Buckets 解析(**非權威,僅輔助計數**);
未列到的標的標 untagged,交由 AI 動態分類(SKILL.md §2.2)。
"""

import json
import os
import re
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

CUR_SWEEP = 2.5   # current vs sodUtc0 %
HIGH_SWEEP = 3.0  # high24h vs sodUtc0 %
MEMBER_CUR = 2.0  # breadth member current threshold
MEMBER_HIGH = 3.0  # breadth member high threshold

HERE = os.path.dirname(os.path.abspath(__file__))
UNIVERSE_REF = os.path.join(HERE, "..", "references", "okx_stock_universe.md")


def _get(url):
    last_err = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sweep-breadth/1.0"})
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


def fetch_universe():
    rows = _get(INSTRUMENTS_URL)
    return [r.get("instId") for r in rows
            if str(r.get("instCategory")) == "3" and r.get("state") == "live"]


def fetch_tickers():
    rows = _get(TICKERS_URL)
    return {r.get("instId"): r for r in rows}


def parse_theme_map():
    """Best-effort ticker->theme from reference Suggested Buckets. Non-authoritative."""
    theme_of = {}
    if not os.path.exists(UNIVERSE_REF):
        return theme_of
    try:
        text = open(UNIVERSE_REF, encoding="utf-8").read()
    except OSError:
        return theme_of
    # find the Suggested Buckets section
    m = re.search(r"Suggested Sector Buckets.*?(?=\n## |\Z)", text, re.S)
    section = m.group(0) if m else text
    # join wrapped continuation lines into their bucket bullet
    buckets = []
    for raw in section.splitlines():
        if raw.lstrip().startswith("- ") and ":" in raw:
            buckets.append(raw.strip()[2:])
        elif buckets and raw.strip() and not raw.lstrip().startswith(("#", ">", "-", "|")):
            buckets[-1] += " " + raw.strip()  # continuation of previous bucket
    for entry in buckets:
        label, _, rest = entry.partition(":")
        label = label.strip()
        for tok in re.split(r"[,\s]+", rest):
            tok = tok.strip().upper()
            if tok and re.match(r"^[A-Z][A-Z0-9.]{0,9}$", tok):
                theme_of.setdefault(tok, label)
    return theme_of


def build(rows_map, universe):
    data = []
    for iid in universe:
        t = rows_map.get(iid)
        sym = iid.split("-")[0]
        if not t:
            data.append({"ticker": sym, "instId": iid, "live": False,
                         "cur": None, "high": None})
            continue
        sod = _f(t.get("sodUtc0"))
        last = _f(t.get("last"))
        high24h = _f(t.get("high24h"))
        data.append({"ticker": sym, "instId": iid, "live": True,
                     "cur": pct(last, sod), "high": pct(high24h, sod)})
    return data


def render(data, theme_of, top):
    out = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    live = [d for d in data if d["live"] and d["cur"] is not None]

    out.append("## Movers Ranking + Sweep + Breadth (program-generated — INV-16/INV-7/INV-10)")
    out.append("")
    out.append("generated_at_utc: %s | universe=%d live=%d" % (ts, len(data), len(live)))
    out.append("note: high24h 含前一日,是 session high 粗略代理;真正 session/premarket high 需 candles 驗證 (INV-15)。")
    out.append("")

    # Movers by current
    by_cur = sorted(live, key=lambda d: -d["cur"])[:top]
    out.append("### 漲幅榜 — by current_vs_sodUtc0 (top %d)" % top)
    out.append("| # | Ticker | current_vs_sodUtc0 | high24h_vs_sodUtc0 | theme(輔助) |")
    out.append("|---:|---|---:|---:|---|")
    for i, d in enumerate(by_cur, 1):
        out.append("| %d | %s | %+.2f%% | %s | %s |" % (
            i, d["ticker"], d["cur"],
            "n/a" if d["high"] is None else "%+.2f%%" % d["high"],
            theme_of.get(d["ticker"], "untagged")))
    out.append("")

    # Sweep lists (INV-16)
    cur_hits = sorted([d for d in live if d["cur"] >= CUR_SWEEP], key=lambda d: -d["cur"])
    high_hits = sorted([d for d in live if d["high"] is not None and d["high"] >= HIGH_SWEEP],
                       key=lambda d: -d["high"])
    out.append("### Missed Winner / Intraday Hit Sweep 候選(程式列舉,AI 不得遺漏)")
    out.append("- current_vs_sodUtc0 >= +%.1f%%(共 %d 支):%s"
               % (CUR_SWEEP, len(cur_hits),
                  ", ".join("%s(%+.1f%%)" % (d["ticker"], d["cur"]) for d in cur_hits) or "(無)"))
    out.append("- high24h_vs_sodUtc0 >= +%.1f%%(曾觸 +3%% 代理,共 %d 支):%s"
               % (HIGH_SWEEP, len(high_hits),
                  ", ".join("%s(%+.1f%%)" % (d["ticker"], d["high"]) for d in high_hits) or "(無)"))
    out.append("- 規則:以上每支必須是 Stage 2+ 研究 / rollback / 明確硬 reject,不得無聲消失 (INV-16)。")
    out.append("")

    # Breadth by theme (INV-7/INV-10)
    themes = {}
    for d in live:
        th = theme_of.get(d["ticker"])
        if not th:
            continue
        themes.setdefault(th, []).append(d)
    out.append("### 板塊 Breadth / Basket Decoupling 計數(輔助分組,非權威)")
    out.append("| Theme | members(有資料) | current>=+%.0f%% | high>=+%.0f%% | breadth/decoupling 觸發? | 貢獻成員 |"
               % (MEMBER_CUR, MEMBER_HIGH))
    out.append("|---|---:|---:|---:|---|---|")
    for th in sorted(themes):
        ms = themes[th]
        cur_n = [d for d in ms if d["cur"] is not None and d["cur"] >= MEMBER_CUR]
        high_n = [d for d in ms if d["high"] is not None and d["high"] >= MEMBER_HIGH]
        contrib = sorted(set(d["ticker"] for d in cur_n) | set(d["ticker"] for d in high_n))
        trig = "YES" if (len(cur_n) >= 2 or len(high_n) >= 2) else "no"
        out.append("| %s | %d | %d | %d | %s | %s |" % (
            th, len(ms), len(cur_n), len(high_n), trig, ", ".join(contrib) or "-"))
    out.append("")
    untagged = sorted(d["ticker"] for d in live if d["ticker"] not in theme_of)
    out.append("- **untagged(腳本未能分組,AI 必須動態分類 §2.2)**:%s" % (", ".join(untagged) or "(無)"))
    out.append("- 規則:任何 theme 觸發=YES → 寬論述不得整組 reject,須逐檔重查並 re-run Stage 2 (INV-7/INV-10)。")
    out.append("- ⚠️ 此分組來自 references 範例,**非權威**;成員應以 live universe 動態 theme_tag 為準。")
    return "\n".join(out)


def main(argv):
    as_json = "--json" in argv
    top = 15
    if "--top" in argv:
        try:
            top = int(argv[argv.index("--top") + 1])
        except (IndexError, ValueError):
            pass
    try:
        universe = fetch_universe()
        tickers = fetch_tickers()
    except Exception as e:  # noqa: BLE001
        msg = {"status": "UNAVAILABLE", "error": str(e),
               "instruction": "OKX 不可用 → 改用 static_fallback,不得腦補。"}
        print(json.dumps(msg, ensure_ascii=False, indent=2) if as_json
              else "## Sweep/Breadth — FAILED\nerror: %s\n%s" % (e, msg["instruction"]))
        return 2
    data = build(tickers, universe)
    theme_of = parse_theme_map()
    if as_json:
        live = [d for d in data if d["live"] and d["cur"] is not None]
        payload = {
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
            "thresholds": {"cur_sweep": CUR_SWEEP, "high_sweep": HIGH_SWEEP,
                           "member_cur": MEMBER_CUR, "member_high": MEMBER_HIGH},
            "rows": data,
            "current_sweep": [d["ticker"] for d in live if d["cur"] >= CUR_SWEEP],
            "high_sweep": [d["ticker"] for d in live if d["high"] is not None and d["high"] >= HIGH_SWEEP],
            "theme_of": theme_of,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render(data, theme_of, top))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
