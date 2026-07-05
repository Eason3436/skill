# TSM 週末布林通道策略 — 回測系統

30 分鐘 K 線、僅週末交易的 TSM 代幣化股票（永續合約）布林通道均值回歸策略回測。

## 策略規則（固定）

| 項目 | 設定 |
|---|---|
| 標的 | TSM 代幣化商品（股票代幣現貨 / 永續合約） |
| K 線 | 30 分鐘 |
| 通道 | 布林：20 期均線 ± 2.5 倍標準差（母體標準差 ddof=0） |
| 交易時段 | 僅週六、週日 |
| 進場 | K 棒最低價 ≤ 下軌 → 以下軌價買進 |
| 出場 | K 棒最高價 ≥ 上軌 → 以上軌價賣出 |
| 強制平倉 | 週日 23:30（該時區週末最後一根 K 棒）若仍持倉，以收盤價平倉，不跨週 |
| 止損 | 無 |
| 倉位 | 每次全倉、複利、不加碼 |

## ⚠️ 資料可得性（重要）

本任務要求「**調用 Bybit、回測 52 週**」。實際執行時遇到兩個硬限制：

1. **Bybit 從本執行環境無法連線** — `api.bybit.com` / `api.bytick.com`（含 testnet、demo）
   全部被 CloudFront 依出口地區地理封鎖（回傳 *"CloudFront distribution is configured to
   block access from your country"*）。這是 Bybit 端的封鎖，非本環境的政策，無法也不應繞過。
   → 程式中的 `BybitSource` 已寫好（v5 `/v5/market/kline`，向後翻頁到上市日），
   在 **Bybit 可連線的地區可直接執行**。惟需先向 Bybit 合約清單確認 TSM 代幣的實際 symbol
   （預設 `TSMUSDT` 僅為佔位，Bybit 代幣化股票命名可能不同）。

2. **TSM 代幣化商品沒有 52 週的歷史** — 目前唯一可連線、且有同一 TSM 代幣化永續的交易所是 OKX
   （`TSM-USDT-SWAP`）。其 30 分鐘歷史最早僅到 **2026-03-11**（約 **16.6 週**），
   與你原先「OKX 只有 17 週」的觀察一致。這類代幣化美股上市時間都很新（2025 之後），
   52 週的資料在任何交易所都不存在。此外，本策略「僅週末交易」的前提，正是代幣化商品週末照常交易；
   一般美股（NYSE）週末休市、行情源無任何週末 K 棒，因此**無法**用真實股票資料替代。

**結論**：無法產出真正「52 週」的回測。本專案改以「**現存的完整歷史（OKX TSM-USDT-SWAP，約 16.6 週）**」
執行了一次**真實**回測，並保留 Bybit 抓取器供日後在可連線環境重跑（屆時資料一多即可加長區間）。

## 回測結果（OKX `TSM-USDT-SWAP`，2026-03-11 ~ 2026-07-05，起始 $10,000）

| 指標 | 值 |
|---|---|
| 最終淨值 | **$12,519.68** |
| 總報酬 | **+25.20%** |
| 最大回撤 | -2.50%（2026-04-18） |
| 總交易組數 | 41（自然出場 29 / 強制平倉 12） |
| 勝率 | 87.8% |
| 單筆最大獲利 / 虧損 | +1.82% / -1.63% |
| 平均每筆損益 | +0.55% |

保守模式（`--no-same-bar-exit`，禁止同根 K 棒進出）：+23.15%、39 筆，結果穩健。

完整輸出見 `results/`：`report.txt`、`trades.csv`、`weekly.csv`、`equity_curve.csv`。

## 使用方式

```bash
pip install -r requirements.txt

# OKX（本環境可執行，抓取全部可得歷史並快取）
python main.py --source okx --csv data/tsm_okx_30m.csv

# Bybit（在 Bybit 可連線地區；先確認 symbol）
python main.py --source bybit --symbol TSMUSDT --weeks 52

# 常用參數
python main.py --source okx --capital 10000 --period 20 --mult 2.5 \
               --tz UTC --fee-rate 0.0 [--no-same-bar-exit]
```

### 參數

| 參數 | 預設 | 說明 |
|---|---|---|
| `--source` | `okx` | `okx` 或 `bybit` |
| `--symbol` | 依 source | OKX `TSM-USDT-SWAP` / Bybit `TSMUSDT`（待確認） |
| `--weeks` | 全部 | 只取最近 N 週 |
| `--capital` | 10000 | 起始資金（USD） |
| `--period` / `--mult` | 20 / 2.5 | 布林參數 |
| `--tz` | `UTC` | 判定週末與 23:30 強制平倉的時區 |
| `--fee-rate` | 0.0 | 單邊手續費率（規格未列，預設 0） |
| `--no-same-bar-exit` | off | 保守模式：禁止同根 K 棒進出 |

## 建模假設（皆可調、已於程式註記）

- 布林通道以**連續** 30m 序列計算（含平日 K 棒），確保 20 期窗口完整；只在週末 K 棒交易。
- 若某週末 K 棒同時觸下軌與上軌，先判進場、同根可再出場（滿通道獲利）。K 棒內觸價先後未知，
  此為均值回歸回測的慣用樂觀假設；可用 `--no-same-bar-exit` 改為保守。
- 一個週末內自然出場後，若再觸下軌可再進場（視為新一筆）。
- USDT 永續價格視同 USD；每筆以 `淨值 / 進場價` 買入、無槓桿，故單筆報酬 = (出場−進場)/進場。

## 檔案

```
tsm_backtest/
├── data_sources.py   # BybitSource / OKXSource（統一輸出 UTC 30m OHLCV）
├── strategy.py       # 回測引擎 + 交易統計 + 逐週彙總
├── main.py           # CLI：抓取→回測→輸出報告與 CSV
├── requirements.txt
├── data/             # 原始 K 線快取
└── results/          # report.txt / trades.csv / weekly.csv / equity_curve.csv
```
