#!/usr/bin/env python3
"""Generate a self-contained HTML report from results.json + per_token.csv."""
import csv
import json
import os

HERE = os.path.dirname(__file__)

with open(os.path.join(HERE, "results.json")) as f:
    R = json.load(f)
with open(os.path.join(HERE, "per_token.csv")) as f:
    ROWS = list(csv.DictReader(f))

SCEN = [
    ("8H", "1.5", "8H|1.5"),
    ("8H", "2.0", "8H|2.0"),
    ("12H", "1.5", "12H|1.5"),
    ("12H", "2.0", "12H|2.0"),
]


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def scenario_card(tf, var, key):
    d = R[key]
    n = d["cycles"]
    r30, r60, r100 = d["r30"], d["r60"], d["r100"]
    f30, f60, f100 = d["final30"], d["final60"], d["final100"]
    p60, p100 = pct(r60, n), pct(r100, n)
    wr = pct(d["wins"], d["resolved"]) if d["resolved"] else 0
    # funnel bars (occurrence of reaching each depth)
    funnel = f"""
      <div class="funnel">
        <div class="frow"><span class="flab">30% 首批 (‑1.5σ)</span>
          <div class="ftrack"><div class="fbar t1" style="width:100%"></div></div>
          <span class="fval">{r30}<i>100.0%</i></span></div>
        <div class="frow"><span class="flab">60% 加碼 (‑2.0σ)</span>
          <div class="ftrack"><div class="fbar t2" style="width:{p60:.1f}%"></div></div>
          <span class="fval">{r60}<i>{p60:.1f}%</i></span></div>
        <div class="frow"><span class="flab">100% 滿倉 (‑2.5σ)</span>
          <div class="ftrack"><div class="fbar t3" style="width:{p100:.1f}%"></div></div>
          <span class="fval">{r100}<i>{p100:.1f}%</i></span></div>
      </div>"""
    # final position distribution (stacked bar)
    tot = f30 + f60 + f100
    w30, w60, w100 = pct(f30, tot), pct(f60, tot), pct(f100, tot)
    dist = f"""
      <div class="dist">
        <div class="dbar">
          <div class="seg s1" style="width:{w30:.1f}%" title="30% only"></div>
          <div class="seg s2" style="width:{w60:.1f}%" title="60% only"></div>
          <div class="seg s3" style="width:{w100:.1f}%" title="100%"></div>
        </div>
        <div class="dlegend">
          <span><i class="k s1"></i>止步30% · {f30} ({w30:.0f}%)</span>
          <span><i class="k s2"></i>止步60% · {f60} ({w60:.0f}%)</span>
          <span><i class="k s3"></i>滿倉100% · {f100} ({w100:.0f}%)</span>
        </div>
      </div>"""
    tag = "推薦" if (tf == "12H" and var == "2.0") else ""
    tagh = f'<span class="badge">{tag}</span>' if tag else ""
    return f"""
    <article class="card">
      <header class="chead">
        <div><span class="tf">{tf}</span><span class="sep">·</span><span class="ex">部分倉 +{var}σ 出場</span>{tagh}</div>
        <div class="ncyc"><b>{n}</b> 個週期</div>
      </header>
      <p class="ckick">每個週期至少觸發首批 30%。以下為<strong>加碼深度發生率</strong>：</p>
      {funnel}
      <div class="cdivider"></div>
      <p class="ckick">最終停留倉位分佈</p>
      {dist}
      <footer class="cfoot">
        <div><span>已完結</span><b>{d['resolved']}</b></div>
        <div><span>未平倉*</span><b>{d['open']}</b></div>
        <div><span>勝率</span><b>{wr:.0f}%</b></div>
      </footer>
    </article>"""


cards = "\n".join(scenario_card(*s) for s in SCEN)

# per-token table, 8H rows, sorted by cycles desc
t8 = [r for r in ROWS if r["tf"] == "8H"]
t8.sort(key=lambda r: int(r["cycles"]), reverse=True)
trows = []
for r in t8:
    n = int(r["cycles"])
    p60 = pct(int(r["reach60"]), n)
    p100 = pct(int(r["reach100"]), n)
    pnl = float(r["pnl"])
    pcls = "pos" if pnl >= 0 else "neg"
    trows.append(
        f"<tr><td class='sym'>{r['token']}</td><td class='num'>{r['bars']}</td>"
        f"<td class='num'>{n}</td><td class='num'>{p60:.0f}%</td>"
        f"<td class='num'>{p100:.0f}%</td><td class='num'>{r['open']}</td>"
        f"<td class='num {pcls}'>{pnl:+.1f}</td></tr>"
    )
table_rows = "\n".join(trows)

HTML = f"""<title>OKX 美股代幣 · 布林通道分批進出場回測</title>
<style>
:root{{
  --bg:#F6F8F7; --surface:#FFFFFF; --surface2:#F0F3F2; --ink:#0F1E1C; --muted:#5C6C6A;
  --line:#E3E8E6; --accent:#0E8A78; --accent2:#14A38D; --t1:#8FB9B1; --t2:#2C9E88; --t3:#0E6F5F;
  --good:#1B9E6F; --warn:#C2870B; --bad:#C0453B;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",system-ui,sans-serif;
}}
@media (prefers-color-scheme:dark){{
  :root{{--bg:#0B100F; --surface:#121A18; --surface2:#0F1615; --ink:#E7EEEC; --muted:#8A9997;
    --line:#20302C; --accent:#2FBFA8; --accent2:#37D0B6; --t1:#3C5751; --t2:#2C9E88; --t3:#37D0B6;
    --good:#37C98E; --warn:#E0A62E; --bad:#E0685C;}}
}}
:root[data-theme="dark"]{{--bg:#0B100F; --surface:#121A18; --surface2:#0F1615; --ink:#E7EEEC; --muted:#8A9997;
  --line:#20302C; --accent:#2FBFA8; --accent2:#37D0B6; --t1:#3C5751; --t2:#2C9E88; --t3:#37D0B6;
  --good:#37C98E; --warn:#E0A62E; --bad:#E0685C;}}
:root[data-theme="light"]{{--bg:#F6F8F7; --surface:#FFFFFF; --surface2:#F0F3F2; --ink:#0F1E1C; --muted:#5C6C6A;
  --line:#E3E8E6; --accent:#0E8A78; --accent2:#14A38D; --t1:#8FB9B1; --t2:#2C9E88; --t3:#0E6F5F;
  --good:#1B9E6F; --warn:#C2870B; --bad:#C0453B;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.55;
  font-size:16px;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1080px;margin:0 auto;padding:40px 22px 80px}}
.eyebrow{{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);font-weight:600;font-family:var(--mono)}}
h1{{font-size:clamp(26px,4vw,40px);line-height:1.1;margin:.3em 0 .2em;text-wrap:balance;letter-spacing:-.01em}}
.lede{{color:var(--muted);max-width:64ch;font-size:16px;margin:.2em 0 0}}
.meta{{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 0}}
.chip{{font-family:var(--mono);font-size:12.5px;padding:5px 11px;border:1px solid var(--line);
  border-radius:999px;background:var(--surface);color:var(--muted)}}
.chip b{{color:var(--ink);font-weight:600}}
section{{margin-top:44px}}
h2{{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-family:var(--mono);
  font-weight:600;margin:0 0 16px;padding-bottom:10px;border-bottom:1px solid var(--line)}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}}
@media(max-width:720px){{.grid{{grid-template-columns:1fr}}}}
.card{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px 20px 16px}}
.chead{{display:flex;justify-content:space-between;align-items:baseline;gap:10px}}
.tf{{font-family:var(--mono);font-weight:700;font-size:18px;color:var(--ink)}}
.sep{{color:var(--muted);margin:0 7px}}
.ex{{font-size:13.5px;color:var(--muted)}}
.badge{{margin-left:8px;font-size:11px;font-family:var(--mono);color:var(--accent);border:1px solid var(--accent);
  border-radius:6px;padding:1px 6px;vertical-align:middle}}
.ncyc{{font-family:var(--mono);font-size:13px;color:var(--muted);white-space:nowrap}}
.ncyc b{{color:var(--ink);font-size:16px}}
.ckick{{font-size:13px;color:var(--muted);margin:16px 0 10px}}
.ckick strong{{color:var(--ink)}}
.funnel{{display:flex;flex-direction:column;gap:9px}}
.frow{{display:grid;grid-template-columns:118px 1fr auto;align-items:center;gap:10px}}
.flab{{font-size:12px;color:var(--muted);font-family:var(--mono)}}
.ftrack{{height:16px;background:var(--surface2);border-radius:5px;overflow:hidden}}
.fbar{{height:100%;border-radius:5px}}
.fbar.t1{{background:var(--t1)}} .fbar.t2{{background:var(--t2)}} .fbar.t3{{background:var(--t3)}}
.fval{{font-family:var(--mono);font-size:12.5px;text-align:right;min-width:82px}}
.fval i{{display:inline-block;font-style:normal;color:var(--muted);margin-left:6px;width:46px}}
.cdivider{{height:1px;background:var(--line);margin:16px 0 2px}}
.dist{{margin-top:4px}}
.dbar{{display:flex;height:14px;border-radius:5px;overflow:hidden;background:var(--surface2)}}
.seg.s1{{background:var(--warn)}} .seg.s2{{background:var(--accent2)}} .seg.s3{{background:var(--t3)}}
.dlegend{{display:flex;flex-wrap:wrap;gap:12px;margin-top:9px;font-family:var(--mono);font-size:11.5px;color:var(--muted)}}
.dlegend i.k{{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:baseline}}
.k.s1{{background:var(--warn)}} .k.s2{{background:var(--accent2)}} .k.s3{{background:var(--t3)}}
.cfoot{{display:flex;gap:22px;margin-top:16px;padding-top:13px;border-top:1px solid var(--line)}}
.cfoot div{{display:flex;flex-direction:column}}
.cfoot span{{font-size:11px;color:var(--muted);font-family:var(--mono);text-transform:uppercase;letter-spacing:.05em}}
.cfoot b{{font-family:var(--mono);font-size:17px;margin-top:2px}}
table{{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:13px}}
.tscroll{{overflow-x:auto;border:1px solid var(--line);border-radius:12px}}
thead th{{position:sticky;top:0;background:var(--surface);text-align:right;padding:11px 14px;font-size:11px;
  letter-spacing:.05em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--line);font-weight:600}}
thead th:first-child{{text-align:left}}
tbody td{{padding:8px 14px;border-bottom:1px solid var(--line)}}
tbody tr:last-child td{{border-bottom:none}}
tbody tr:nth-child(even){{background:var(--surface2)}}
td.sym{{font-weight:600;color:var(--ink)}}
td.num{{text-align:right;font-variant-numeric:tabular-nums}}
td.pos{{color:var(--good)}} td.neg{{color:var(--bad)}}
.tblwrap{{max-height:520px;overflow-y:auto}}
.note{{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--warn);border-radius:10px;
  padding:16px 18px;font-size:13.5px;color:var(--muted)}}
.note strong{{color:var(--ink)}}
.method{{columns:2;column-gap:34px;font-size:13.5px;color:var(--muted)}}
@media(max-width:720px){{.method{{columns:1}}}}
.method p{{break-inside:avoid;margin:0 0 12px}}
.method b{{color:var(--ink);font-family:var(--mono);font-size:12.5px}}
.foot{{margin-top:50px;padding-top:18px;border-top:1px solid var(--line);font-size:12px;color:var(--muted);font-family:var(--mono)}}
strong.hl{{color:var(--accent);font-weight:600}}
</style>

<div class="wrap">
  <div class="eyebrow">OKX Stock Tokens · Bollinger Scale-In Backtest</div>
  <h1>布林通道分批進出場策略回測</h1>
  <p class="lede">在 124 檔 OKX 美股永續代幣上，測試「跌破下軌分三批進場、漲回上軌分批出場」的均值回歸策略。核心產出：<strong class="hl">建倉深度的發生率與次數（30% / 30% / 40%）</strong>。</p>
  <div class="meta">
    <span class="chip">布林參數 <b>SMA20 · σ(ddof0)</b></span>
    <span class="chip">時間框架 <b>8H / 12H</b></span>
    <span class="chip">樣本 <b>124 檔代幣</b></span>
    <span class="chip">進場 <b>‑1.5σ / ‑2σ / ‑2.5σ</b></span>
    <span class="chip">出場 <b>+1.5σ / +2σ</b></span>
    <span class="chip">資料截至 <b>2026‑07‑21</b></span>
  </div>

  <section>
    <h2>四種情境 · 建倉深度發生率</h2>
    <div class="grid">
      {cards}
    </div>
    <p class="ckick" style="margin-top:14px">* 未平倉 = 資料末端價格仍在低檔、尚未觸及出場上軌的週期；其建倉次數仍計入，但不計入勝率／損益。</p>
  </section>

  <section>
    <h2>逐檔明細 · 8H（依週期數排序）</h2>
    <div class="tscroll"><div class="tblwrap">
    <table>
      <thead><tr><th>代幣</th><th>8H K棒</th><th>週期</th><th>達60%</th><th>達100%</th><th>未平倉</th><th>累積損益†</th></tr></thead>
      <tbody>
      {table_rows}
      </tbody>
    </table>
    </div></div>
    <p class="ckick" style="margin-top:10px">† 損益為「每週期 1 單位名目、依 30/30/40 權重成交於軌價」的無槓桿、未扣手續費理論值，僅供相對比較。</p>
  </section>

  <section>
    <h2>方法與規則</h2>
    <div class="method">
      <p><b>布林通道</b> 中軌 = 收盤價 SMA(20)；σ 為 20 根母體標準差。上下軌 = 中軌 ± k·σ，k ∈ {{1.5, 2, 2.5}}。逐根重算（動態軌道）。</p>
      <p><b>8H K棒</b> OKX 無原生 8H，故由 2 根原生 4H 合成（對齊 0/8/16 UTC）。12H 為原生。</p>
      <p><b>分批進場</b> 最低價觸 ‑1.5σ 買 30%；觸 ‑2σ 再買 30%；觸 ‑2.5σ 再買 40%。單根深跌可一次觸發多批。</p>
      <p><b>滿倉出場</b> 三批全到（100%）時：最高價觸 +1.5σ 賣 60%，觸 +2σ 賣剩餘 40%。</p>
      <p><b>部分倉出場</b> 只成交 1 或 2 批（30%/60%）時，於上軌全數了結；分別測試 <b>+1.5σ</b> 與 <b>+2σ</b> 兩種目標。</p>
      <p><b>成交假設</b> 掛單成交於軌價本身；進場看最低價、出場看最高價。價格回到 0 倉即結束一個週期，之後可重新開始。</p>
      <p><b>統計口徑</b> 每個週期記錄「最深建倉批次」，彙總達 30%/60%/100% 的次數與比率，以及最終停留倉位分佈。</p>
    </div>
  </section>

  <section>
    <div class="note">
      <strong>重要限制</strong>　這些代幣多於 2026 年才上市，樣本歷史偏短（8H K棒中位數約 162 根 ≈ 54 天）。回測期整體偏多頭，均值回歸買跌自然討好，勝率與損益具倖存者偏誤（未平倉週期未計損益）。結果僅為歷史統計，非未來獲利保證，亦未計手續費、資金費率、滑價與槓桿爆倉風險。務必自行判斷。
    </div>
  </section>

  <div class="foot">OKX 公開行情資料 · 布林分批進出場回測 · 產生於 2026‑07‑21 · 僅供研究參考，非投資建議</div>
</div>
"""

with open(os.path.join(HERE, "report.html"), "w") as f:
    f.write(HTML)
print("report.html written:", len(HTML), "bytes")
