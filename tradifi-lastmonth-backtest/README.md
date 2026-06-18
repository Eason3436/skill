# TRADIFI 基差套利 — 上月回測（含滑點模擬）

對 `btc-trading-agent` 的 Binance↔OKX TRADIFI 永續基差套利策略，回測**上一個月**
（台北時間 2026-05-18 ~ 2026-06-16，共 30 天）的歷史資料，並加入**真實成交/滑點模擬**。

- 本金 100 USDT、5x 槓桿、每腿名目 = 100×5/2 = **250 USDT**。
- 進場門檻 entry=0.40%、出場 exit=0.10%、單一時間僅持有一個價差倉。
- 資料來源：Binance/OKX 歷史 OHLCV 收盤價（離線快取），無歷史 L2 排隊模擬。

## 成本 / 滑點模型（`--simulate-costs`）

原本的回測**只算 maker 手續費、假設每次都成交在基差價位**，過度樂觀。新增的模擬把
下列實務摩擦全部納入：

| 參數 | 預設 | 說明 |
|------|------|------|
| `--maker-fee` | 0.02% | 每腿掛單手續費（開+平共 4 腿） |
| `--taker-fee` | 0.05% | 跨價成交時的吃單手續費（時間停損、單腿平倉） |
| `--slippage-per-leg` | 0.05% | 每一腿相對中價的執行滑點（開+平每腿都收） |
| `--fill-rate` | 90% | 開倉兩腿都成功掛到的機率 |
| `--single-leg-rate` | 5% | 只成交一腿、必須認賠撤單的機率 |
| `--close-fill-rate` | 80% | 平倉兩腿都以 maker 成交的機率，否則一腿吃單＋撤退滑點 |
| `--retreat-slippage` | 0.20% | 單腿撤退時付出的滑點 |
| `--forced-close-slippage` | 0.30% | 時間停損強平時每腿的滑點 |
| `--seed` | 42 | 成交/滑點亂數種子 |

未加 `--simulate-costs` 時，行為與原版**逐筆相同**（已驗證重現原 +224.15 USDT 基準）。

## 結果摘要

| 情境 | 標的/週期 | 交易數 | 勝率 | 毛利 | 滑點成本 | **淨利** | 期末權益 |
|------|-----------|--------|------|------|----------|----------|----------|
| 無成本（原版，過度樂觀） | 1m · 流動性前 10 | 284 | 96.8% | +280.9 | 0 | **+224.15** | 324.15 |
| **含滑點模擬** | 1m · 流動性前 10 | 289 | 74.7% | +274.1 | −184.3 | **+25.90** | 125.90 |
| 無成本（原版） | 15m · 全市場 63 檔 | 91 | 93.4% | — | 0 | **+54.19** | 154.19 |
| **含滑點模擬** | 15m · 全市場 63 檔 | 89 | 47.2% | — | −93.3 | **−51.20** | 48.80 |

單位：USDT，本金 100 USDT。

### 多種子穩健度（確認不是單一抽樣僥倖）

- **1m 流動性前 10（生存）**：6 個種子淨利 +20.0 ~ +29.4 USDT，平均 **+25.5**（σ=3.2）→ 約 **+25%/月**。
- **15m 全市場（崩潰）**：5 個種子淨利 −41.0 ~ −51.2 USDT，平均 **−45.0** → 穩定為負。

## 結論

1. **滑點是決定性的。** 原本 +224% 的月報酬，套入真實滑點（光滑點一項就吃掉 184 USDT）
   後縮水成 **+26%**。毛利幾乎沒變，差別全在成本——代表原回測的獲利大半是「假設零摩擦」灌出來的。
2. **只有在 1m、流動性最好的標的上才扛得住成本。** 1m 流動性前 10 檔在所有種子下都為正，
   約 +25%/月；而把週期放寬到 15m、標的擴到全市場 63 檔，單筆基差幅度相對滑點太小，
   策略**反而虧損約 −45%**。
3. 實盤要靠這套賺錢，關鍵在：盡量 maker 成交（壓低吃單與撤退滑點）、只做最深的盤口、
   控制單腿風險。在保守的滑點假設下仍有正期望，但安全邊際比帳面小很多。

> 註：本環境無法連到交易所（HTTP 451/403），回測使用專案內離線快取的 OHLCV。
> 市場探索失敗時，腳本會自動退回用快取檔推導共同標的（見 `discover_common_from_cache`）。

## 重現方式

```bash
cd btc-trading-agent/backend
# 1m 流動性前 10（含滑點）
python3 scripts/run_actual_tradifi_backtest.py \
  --capital 100 --leverage 5 --timeframe 1m \
  --start 2026-05-18 --end 2026-06-16 --entry 0.004 --exit 0.001 \
  --simulate-costs --seed 42 \
  --symbols GLW,XLE,COHR,BMNR,ARM,HIMS,QCOM,USAR,MRVL,CSCO \
  --out reports/tradifi_lastmonth_1m_top10_slippage.json \
  --csv-out reports/tradifi_lastmonth_1m_top10_slippage.csv

# 15m 全市場（含滑點）
python3 scripts/run_actual_tradifi_backtest.py \
  --capital 100 --leverage 5 --timeframe 15m \
  --start 2026-05-18 --end 2026-06-16 --entry 0.004 --exit 0.001 \
  --simulate-costs --seed 42 \
  --out reports/tradifi_lastmonth_15m_universe_slippage.json \
  --csv-out reports/tradifi_lastmonth_15m_universe_slippage.csv
```

`scripts/run_actual_tradifi_backtest.py` 為本次加入滑點模擬後的版本副本，方便檢視 diff。
產出報告在 `reports/`：`*_slippage.*` 為含滑點，`*_baseline_nocost.*` 為無成本對照。
