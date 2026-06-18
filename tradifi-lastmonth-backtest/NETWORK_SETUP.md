# 放開網路權限 → 用真實即時資料回測

## 為什麼需要

本策略兩條腿的資料來源在目前環境被擋:
- 幣安 futures `fapi.binance.com` → **HTTP 451**
- OKX `www.okx.com` → **HTTP 403**

要直連抓新/更長的真實資料,需在**環境的網路政策**放行這些網域。
（Session 內無法更改網路政策——它在「建立/設定環境」時決定。）

## 要放行的網域（白名單）

| 網域 | 用途 |
|------|------|
| `fapi.binance.com` | 幣安 USDT 永續(TRADIFI 多腿) |
| `www.okx.com` | OKX 永續 |
| `aws.okx.com` | OKX ccxt 備援節點 |

（只開這 3 個即可；要更省事可用允許一般對外連線的政策。）

## 怎麼設定

1. 到 Claude Code on the web 的**環境設定**，把網路政策改成允許上述網域的
   自訂白名單（或更寬鬆的政策）。說明見
   <https://code.claude.com/docs/en/claude-code-on-the-web>。
2. **開一個新 session**（網路政策在環境建立時生效，需重啟才套用）。
3. 在新 session 跟我說一聲，我直接跑下面的一鍵腳本。

## 一鍵抓真實資料 + 回測（網路一通就能跑）

`fetch_and_backtest.sh`（已附在本資料夾），預設用金牌參數、任意期間:

```bash
cd btc-trading-agent/backend
# 用法: ./fetch_and_backtest.sh <START> <END> [LEVERAGE]
./fetch_and_backtest.sh 2026-05-01 2026-06-17 15
```

腳本會即時向幣安/OKX 抓該期間 1m 真實 K 線（自動快取），再用最佳參數
（entry 0.4% / exit 0.05% / hold 180m + 自動平倉 + 完整滑點/爆倉模擬）回測並輸出報告。
網路一通，就能做**跨月、跨更多標的**的完整驗證——這是目前離線唯一缺的一塊。
