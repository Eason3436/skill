#!/usr/bin/env python3
"""Generate a self-contained HTML report for the simple single-entry/exit study."""
import json
import os

HERE = os.path.dirname(__file__)
with open(os.path.join(HERE, "results_simple.json")) as f:
    R = json.load(f)

SCEN = [("8H", "2.5"), ("8H", "2.0"), ("12H", "2.5"), ("12H", "2.0")]


def card(tf, xs):
    d = R[f"{tf}|{xs}"]
    reach = d["reach_exit_pct"]
    openp = 100 - reach
    honest = d["honest_roi"]
    hcls = "pos" if honest >= 0 else "neg"
    return f"""
    <article class="card">
      <header class="chead">
        <div><span class="tf">{tf}</span><span class="sep">·</span><span class="ex">進 −2.5σ → 出 +{xs}σ</span></div>
        <div class="ncyc"><b>{d['trades']}</b> 筆交易</div>
      </header>
      <div class="funnel">
        <div class="frow"><span class="flab">進場觸發</span>
          <div class="ftrack"><div class="fbar t2" style="width:100%"></div></div>
          <span class="fval">{d['trades']}<i>100%</i></span></div>
        <div class="frow"><span class="flab">已到出場</span>
          <div class="ftrack"><div class="fbar t3" style="width:{reach:.1f}%"></div></div>
          <span class="fval">{d['resolved']}<i>{reach:.0f}%</i></span></div>
        <div class="frow"><span class="flab">仍套牢</span>
          <div class="ftrack"><div class="fbar warn" style="width:{openp:.1f}%"></div></div>
          <span class="fval">{d['open']}<i>{openp:.0f}%</i></span></div>
      </div>
      <div class="cdivider"></div>
      <div class="kpis">
        <div><span>平倉勝率</span><b>{d['win_rate']:.0f}%</b></div>
        <div><span>平倉均ROI</span><b class="pos">{d['avg_roi']:+.2f}%</b></div>
        <div><span>最差單筆</span><b class="neg">{d['worst']:+.0f}%</b></div>
        <div><span>平均持有</span><b>{d['avg_held_bars']:.0f} 根</b></div>
      </div>
      <div class="honest {hcls}">
        <span>誠實均ROI（含套牢 mark-to-market）</span><b>{honest:+.2f}% / 交易</b>
      </div>
    </article>"""


cards = "\n".join(card(*s) for s in SCEN)

HTML = f"""<title>OKX 美股代幣 · 布林 −2.5σ 進 / +2.5σ·+2σ 出</title>
<style>
:root{{--bg:#F6F8F7;--surface:#FFFFFF;--surface2:#F0F3F2;--ink:#0F1E1C;--muted:#5C6C6A;--line:#E3E8E6;
  --accent:#0E8A78;--t2:#2C9E88;--t3:#0E6F5F;--good:#1B9E6F;--warn:#C2870B;--bad:#C0453B;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",system-ui,sans-serif;}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0B100F;--surface:#121A18;--surface2:#0F1615;--ink:#E7EEEC;--muted:#8A9997;
  --line:#20302C;--accent:#2FBFA8;--t2:#2C9E88;--t3:#37D0B6;--good:#37C98E;--warn:#E0A62E;--bad:#E0685C;}}}}
:root[data-theme="dark"]{{--bg:#0B100F;--surface:#121A18;--surface2:#0F1615;--ink:#E7EEEC;--muted:#8A9997;
  --line:#20302C;--accent:#2FBFA8;--t2:#2C9E88;--t3:#37D0B6;--good:#37C98E;--warn:#E0A62E;--bad:#E0685C;}}
:root[data-theme="light"]{{--bg:#F6F8F7;--surface:#FFFFFF;--surface2:#F0F3F2;--ink:#0F1E1C;--muted:#5C6C6A;--line:#E3E8E6;
  --accent:#0E8A78;--t2:#2C9E88;--t3:#0E6F5F;--good:#1B9E6F;--warn:#C2870B;--bad:#C0453B;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.55;font-size:16px;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:960px;margin:0 auto;padding:40px 22px 80px}}
.eyebrow{{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);font-weight:600;font-family:var(--mono)}}
h1{{font-size:clamp(24px,4vw,36px);line-height:1.12;margin:.3em 0 .2em;text-wrap:balance;letter-spacing:-.01em}}
.lede{{color:var(--muted);max-width:62ch;margin:.2em 0 0}}
.meta{{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 0}}
.chip{{font-family:var(--mono);font-size:12.5px;padding:5px 11px;border:1px solid var(--line);border-radius:999px;background:var(--surface);color:var(--muted)}}
.chip b{{color:var(--ink);font-weight:600}}
section{{margin-top:40px}}
h2{{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-family:var(--mono);font-weight:600;margin:0 0 16px;padding-bottom:10px;border-bottom:1px solid var(--line)}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}}
@media(max-width:720px){{.grid{{grid-template-columns:1fr}}}}
.card{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px}}
.chead{{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:16px}}
.tf{{font-family:var(--mono);font-weight:700;font-size:18px}}
.sep{{color:var(--muted);margin:0 7px}} .ex{{font-size:13px;color:var(--muted)}}
.ncyc{{font-family:var(--mono);font-size:13px;color:var(--muted);white-space:nowrap}} .ncyc b{{color:var(--ink);font-size:16px}}
.funnel{{display:flex;flex-direction:column;gap:9px}}
.frow{{display:grid;grid-template-columns:74px 1fr auto;align-items:center;gap:10px}}
.flab{{font-size:12px;color:var(--muted);font-family:var(--mono)}}
.ftrack{{height:16px;background:var(--surface2);border-radius:5px;overflow:hidden}}
.fbar{{height:100%;border-radius:5px}} .fbar.t2{{background:var(--t2)}} .fbar.t3{{background:var(--t3)}} .fbar.warn{{background:var(--warn)}}
.fval{{font-family:var(--mono);font-size:12.5px;text-align:right;min-width:72px}}
.fval i{{display:inline-block;font-style:normal;color:var(--muted);margin-left:6px;width:38px}}
.cdivider{{height:1px;background:var(--line);margin:16px 0}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
.kpis div{{display:flex;flex-direction:column;gap:3px}}
.kpis span{{font-size:10.5px;color:var(--muted);font-family:var(--mono);text-transform:uppercase;letter-spacing:.04em}}
.kpis b{{font-family:var(--mono);font-size:16px}}
.pos{{color:var(--good)}} .neg{{color:var(--bad)}}
.honest{{margin-top:14px;display:flex;justify-content:space-between;align-items:center;gap:10px;padding:11px 13px;border-radius:9px;background:var(--surface2);border:1px solid var(--line)}}
.honest span{{font-size:11.5px;color:var(--muted)}}
.honest b{{font-family:var(--mono);font-size:16px}}
.honest.pos{{border-left:3px solid var(--good)}} .honest.neg{{border-left:3px solid var(--bad)}}
.note{{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--warn);border-radius:10px;padding:16px 18px;font-size:13.5px;color:var(--muted)}}
.note strong{{color:var(--ink)}}
.method{{font-size:13.5px;color:var(--muted)}} .method p{{margin:0 0 10px}} .method b{{color:var(--ink);font-family:var(--mono);font-size:12.5px}}
.foot{{margin-top:46px;padding-top:18px;border-top:1px solid var(--line);font-size:12px;color:var(--muted);font-family:var(--mono)}}
</style>

<div class="wrap">
  <div class="eyebrow">OKX Stock Tokens · Bollinger Mean-Reversion (single entry/exit)</div>
  <h1>布林通道 −2.5σ 進 / +2.5σ·+2σ 出</h1>
  <p class="lede">單進單出的均值回歸：價格觸下軌 −2.5σ 買滿倉，觸上軌 +2.5σ（或 +2σ）全數賣出。測 8H 與 12H 兩個時間框架，共 120+ 檔 OKX 美股永續代幣。</p>
  <div class="meta">
    <span class="chip">布林 <b>SMA20 · σ(ddof0)</b></span>
    <span class="chip">進場 <b>−2.5σ 滿倉</b></span>
    <span class="chip">出場 <b>+2.5σ / +2σ</b></span>
    <span class="chip">時框 <b>8H / 12H</b></span>
    <span class="chip">資料截至 <b>2026‑07‑21</b></span>
  </div>

  <section>
    <h2>四種情境</h2>
    <div class="grid">{cards}</div>
  </section>

  <section>
    <h2>方法</h2>
    <div class="method">
      <p><b>進場</b> 最低價觸 中軌 − 2.5σ → 買入滿倉，成交於軌價。</p>
      <p><b>出場</b> 最高價觸 中軌 + 2.5σ（或 +2σ）→ 全數賣出。之後可重新進場。</p>
      <p><b>8H K棒</b> 由 2 根原生 4H 合成（OKX 無原生 8H）；12H 為原生。布林逐根動態重算。</p>
      <p><b>誠實 ROI</b> = 已平倉損益 ＋ 未平倉部位以最後收盤價 mark-to-market，避免只看贏家的倖存者偏誤。未扣手續費／資金費率／滑價，無槓桿。</p>
    </div>
  </section>

  <section>
    <div class="note">
      <strong>怎麼讀這份結果</strong>　平倉勝率高（76%~84%）、平倉平均 ROI 為正，但一旦把「還沒漲回上軌、仍套牢」的部位（8H 約 25~29%、12H 約 36~43%）用現價計入，<strong>誠實平均每筆約 −0.4%~−0.7%</strong>——因為單筆最差可達 −92%。出場設 +2.5σ 需要一次完整的極端擺盪，套牢比例最高、尤其 12H 高達 43% 未回本。樣本僅約 2 個月且偏多頭，僅供研究，非投資建議。
    </div>
  </section>

  <div class="foot">OKX 公開行情 · 單進單出布林回測 · 2026‑07‑21 · 僅供研究參考，非投資建議</div>
</div>
"""

with open(os.path.join(HERE, "report_simple.html"), "w") as f:
    f.write(HTML)
print("report_simple.html written:", len(HTML), "bytes")
