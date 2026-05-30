#!/usr/bin/env python3
"""
clock.py — Deterministic time/date anchor for news-search freshness.

破洞:AI 手算「台北→UTC→ET + 夏令/冬令」容易出錯,一旦把 {DATE} 填錯,就會去搜錯誤
日期 → 撈到舊報導/過時財報 → 判斷失誤。本腳本把日期錨點算死,並直接吐出「該用的、
已填好正確日期的搜尋字串」與「新鮮度視窗」,讓 AI 不必自己做日期算術。

只用 Python 標準函式庫。離線即可(不需網路)。

用法:
    python3 scripts/clock.py                      # 用系統 UTC 現在時間
    python3 scripts/clock.py --utc 2026-05-30T11:30   # 指定 UTC 時間(測試/重現用)
    python3 scripts/clock.py --json

ET 夏令時間規則(美東):3 月第二個週日 02:00 起 EDT(UTC-4),11 月第一個週日 02:00 止;
其餘為 EST(UTC-5)。台北固定 UTC+8(無 DST)。查詢通常落在工作日早晨,遠離轉換時點。
"""

import json
import sys
from datetime import datetime, timedelta, timezone, date


def _nth_sunday(year, month, n):
    d = date(year, month, 1)
    # weekday(): Mon=0 .. Sun=6
    first_sunday = 1 + (6 - d.weekday()) % 7
    return date(year, month, first_sunday + (n - 1) * 7)


def is_edt(d):
    """US Eastern daylight time in effect for given date (date in ET)."""
    start = _nth_sunday(d.year, 3, 2)   # 2nd Sunday of March
    end = _nth_sunday(d.year, 11, 1)    # 1st Sunday of November
    return start <= d < end


def et_offset_hours(utc_dt):
    # approximate ET date by trying EST first, then check DST; transitions are weekend
    approx = (utc_dt - timedelta(hours=5)).date()
    return -4 if is_edt(approx) else -5


def parse_utc(arg):
    arg = arg.replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(arg, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError("無法解析 UTC 時間: %s (用 YYYY-MM-DDTHH:MM)" % arg)


def compute(utc_dt):
    off = et_offset_hours(utc_dt)
    et = utc_dt + timedelta(hours=off)
    tw = utc_dt + timedelta(hours=8)
    et_d = et.date()
    wd = et.weekday()  # Mon=0..Sun=6

    # session_now relative to ET clock
    minutes_now = et.hour * 60 + et.minute
    open_min, close_min = 9 * 60 + 30, 16 * 60

    # trading_day_target: 預測對象那一個 09:30 開盤所在的 ET 日期
    target = et_d
    note = ""
    if wd >= 5:  # weekend
        target = et_d + timedelta(days=(7 - wd))
        note = "週末查詢 → 預測下週一,訊號鮮度差,須明確告知使用者"
    elif minutes_now >= close_min:  # after close → next session
        nxt = et_d + timedelta(days=1)
        if nxt.weekday() >= 5:
            nxt = nxt + timedelta(days=(7 - nxt.weekday()))
        target = nxt
        note = "已過收盤 → 預測下一個交易日"
    elif minutes_now >= open_min:
        note = "已開盤(>=09:30 ET)→ session_gate:轉 post_open_validation,非盤前預測 (INV-18)"

    if minutes_now < open_min and wd < 5:
        session_now = "premarket" if minutes_now >= 4 * 60 else "overnight"
        minutes_until_open = open_min - minutes_now
    else:
        session_now = "regular_session" if (open_min <= minutes_now < close_min and wd < 5) else "closed"
        # minutes until the target session open
        target_open = datetime(target.year, target.month, target.day, 9, 30)
        et_naive = et.replace(tzinfo=None)
        minutes_until_open = int((target_open - et_naive).total_seconds() // 60)

    yesterday = target - timedelta(days=1)  # 用於 AMC / 昨晚盤後新聞
    tzname = "EDT (UTC-4)" if off == -4 else "EST (UTC-5)"
    return {
        "query_time_utc": utc_dt.strftime("%Y-%m-%d %H:%M:%SZ"),
        "query_time_taipei": tw.strftime("%Y-%m-%d %H:%M (UTC+8)"),
        "query_time_et": et.strftime("%Y-%m-%d %H:%M ") + tzname,
        "et_dst": tzname,
        "session_now": session_now,
        "minutes_until_open": minutes_until_open,
        "trading_day_target": target.isoformat(),
        "news_search_date": target.isoformat(),
        "yesterday_date": yesterday.isoformat(),
        "freshness_window_start_et": yesterday.isoformat() + " 00:00 ET",
        "note": note,
    }


def render(c):
    out = []
    out.append("## Time / News-Freshness Anchor (program-computed — 別用手算日期)")
    out.append("")
    for k in ("query_time_utc", "query_time_taipei", "query_time_et", "session_now",
              "minutes_until_open", "trading_day_target", "news_search_date",
              "yesterday_date", "freshness_window_start_et"):
        out.append("%s: %s" % (k, c[k]))
    if c["note"]:
        out.append("note: %s" % c["note"])
    d = c["news_search_date"]
    y = c["yesterday_date"]
    out.append("")
    out.append("### 已填好日期的搜尋字串(直接用,別改日期)")
    out.append("```")
    out.append('web_search: "premarket movers %s"' % d)
    out.append('web_search: "biggest premarket gainers %s"' % d)
    out.append('web_search: "{TICKER} premarket %s"' % d)
    out.append('web_search: "earnings before bell %s"' % d)
    out.append('web_search: "earnings after the close %s"   # 昨晚盤後 AMC' % y)
    out.append('web_search: "biggest analyst price target raise %s"' % d)
    out.append('web_search: "economic calendar %s"' % d)
    out.append('web_search: "{TICKER} news %s"' % d)
    out.append("```")
    out.append("")
    out.append("### 來源時效規則(INV-19,AI 必守)")
    out.append("- 只有**發布時間 >= %s** 的來源,才能算今天的 fresh catalyst。" % c["freshness_window_start_et"])
    out.append("- 撈到的每一則新聞都要先核對**發布時間戳**;無法確認日期或早於視窗 → 只能當背景,")
    out.append("  不得支持 HIGH,並標 `source_recency: stale_or_undated`(見 INV-19)。")
    out.append("- 排程型事件(今日財報/數據/FDA)例外:以**事件日**判定,不以文章日期判定。")
    return "\n".join(out)


def main(argv):
    as_json = "--json" in argv
    utc_dt = None
    if "--utc" in argv:
        try:
            utc_dt = parse_utc(argv[argv.index("--utc") + 1])
        except (IndexError, ValueError) as e:
            sys.stderr.write("%s\n" % e)
            return 1
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)
    c = compute(utc_dt)
    print(json.dumps(c, ensure_ascii=False, indent=2) if as_json else render(c))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
