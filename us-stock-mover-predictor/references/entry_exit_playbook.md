# 進出場策略執行手冊 (Entry/Exit Playbook)

> ⚠️ **位階說明:** 本檔是「執行手冊」,**不是規範來源**。進場/出場/R:R 規則以
> `SKILL.md §1 INV-11 / INV-12` 為準。本檔的個股名稱(MU、PLTR、AMD …)與回測數字
> **全部是非規範校準範例**,只示範策略長什麼樣;判斷現場標的時只看可觀測條件
> (R:R、剩餘空間、結構、VWAP),與是哪一隻股票無關。

針對「**已預測會漲,如何不在當日高點接手**」的核心問題,本檔詳述三種進場策略
的執行細節、停損設計、以及部位管理。

---

## 為什麼進場時機這麼重要?

**核心問題**:預測到了 MU 會漲,但如果使用者:
- 開盤跳空 +10% 才買入 → 真實風險報酬比變差
- 收盤前才買入 → 可能買在當日高點
- 等回檔等不到 → 完全錯過機會

**統計現實**(美股大型股經驗值):
- 盤前 +3% 以上的標的,**約 35-45%** 開盤後會跌回 prev_close 附近
- 盤前 +5% 以上的標的,**約 60-70%** 收盤仍會維持 +3% 以上
- 盤中觸 +3% 的標的,**約 50%** 收盤跌回 +0~+2%

→ **結論**:預測對了不等於賺到,進場時機決定真實盈虧。

---

## 三種進場策略詳述

## 0. 進場可交易性閘門（先於三策略）

三策略只在「還有可賺空間」時才有意義。先判斷這筆交易是不是已經被跳空吃掉。

### 0.1 跳空消耗閘門（Gap-Consumption Gate）

每支最終 PICK 在給進場策略前必算：

```text
target_3pct_price = prev_close * 1.03
remaining_room_pct = (target_3pct_price - candidate_entry_price) / candidate_entry_price * 100
```

判定：

| 剩餘空間 | 狀態 | 動作 |
|---:|---|---|
| `>= +2.0%` | `room_sufficient` | 可正常使用 🅰️/🅱️/🅲️ |
| `+0.8% ~ +2.0%` | `room_limited` | 只准 🅲️、半倉、TP1 設在 `target_3pct_price` |
| `< +0.8%` 或已站上命中價 | `already_realized` | 禁止新多單，只能 watch / 管理既有部位 |

若開盤價或開盤 15 分鐘內最高價已經觸及 `target_3pct_price`，標記
`gap_hit: yes`。這代表「預測可能命中，但新進場者吃不到主要漲幅」。

### 0.2 R:R 硬門檻

每個進場價都要計算：

```text
risk_reward_ratio = (reasonable_day_ceiling - candidate_entry_price) / (candidate_entry_price - stop_price)
```

規則：
- `risk_reward_ratio >= 1.5` 才能給新倉建議。
- `risk_reward_ratio < 1.5` 一律不做，即使預測仍可能命中。
- `reasonable_day_ceiling` 用 ATR、前日波幅、盤前延伸、上方阻力、VWAP 和 K 線結構估算。
- 不可假設「從進場價還會再漲 3%」。本 skill 的 +3% 目標是相對昨收，不是相對你的進場價。

### 0.3 輸出必須拆成兩欄

每支 PICK 必須分開寫：

```text
prediction:
  touch_plus_3_probability:
  target_3pct_price:
  prediction_status:

tradeable_entry:
  candidate_entry_price:
  remaining_room_pct_to_target_3pct:
  gap_consumption_status:
  stop_price:
  reasonable_day_ceiling:
  risk_reward_ratio:
  risk_reward_gate:
  entry_verdict:
```

如果 `gap_consumption_status: already_realized` 或 `risk_reward_gate: fail`：
- `tradeable_entry.entry_verdict = NONE`
- 不得給 🅰️/🅱️/🅲️ 新倉建議
- 輸出：「預測命中不等於可交易，命中已被跳空消耗 / R:R 不足」

## 0.4 進場時機輸出格式（每支 PICK 必填）

每支 PICK 必須輸出一個可以照表執行的 `entry_timing_plan`：

```text
entry_timing_plan:
  strategy:
  current_session_time_et:
  next_decision_time_et:
  valid_entry_window_et:
  trigger_condition:
  trigger_price:
  limit_price_ceiling:
  stop_price:
  target_3pct_price:
  remaining_room_pct_to_target_3pct:
  risk_reward_ratio:
  order_type:
  cancel_if:
  do_not_chase_above:
  recheck_if_missed:
  new_position_action:
  existing_position_action:
  position_size:
```

若無法填出觸發價、限價上限、取消條件、或 R:R，就不能寫成可進場。
改寫成 `wait_only` 或 `no_new_entry`。

### 時間窗硬規則

| 時間窗（ET） | 可用策略 | 必要條件 | 不通過時 |
|---|---|---|---|
| 09:30-09:35 | 🅰️ 追高型 | HIGH、重磅新催化、09:10 確認、R:R >= 1.5、無 gap 消耗 | 不追，等 B/C |
| 09:35-10:00 | 🅱️ 回檔型 | 回踩計畫區、守 VWAP / midpoint、未破開盤支撐 | 取消，不上移買點 |
| 10:00-10:30 | 🅲️ 動能確認型 | 站上開盤 30m 高、守 15m、量能確認、R:R >= 1.5 | watch only |
| 10:30 後 | scanner only | predictor 不再給新盤前進場 | 交給盤中 scanner |

### 不追價規則

每筆交易都必須有 `do_not_chase_above`：
- 🅰️：`min(open_price * 1.005, R:R still >= 1.5 的最高價)`
- 🅱️：回檔區上緣；沒有回檔就放棄
- 🅲️：確認後的 opening-range high 上方最多 `+0.5%`，且 R:R 仍需 >= 1.5

如果價格已超過 `do_not_chase_above`：
- 新倉：`no_new_entry`
- 既有持倉：可 `hold / trim / move_stop`
- 不得把買點往上追

### 觸發與取消必須成對

每個觸發條件都必須有取消條件：
- 觸發：突破 opening-range high → 取消：跌回區間內並連續兩根 5m K 收不回
- 觸發：回踩 VWAP / midpoint → 取消：跌破 VWAP 且反彈量能不足
- 觸發：開盤延伸 → 取消：第一根 5m K 跌破開盤價或 VWAP
- 觸發：催化續攻 → 取消：同族群 / QQQ 明顯轉弱

### 錯過進場處理

錯過原計畫進場，不可以自動追高。必須重新計算：
- 剩餘空間
- R:R
- 新 stop 是否乾淨
- 是否形成新的 base / VWAP reclaim

若重算後 R:R < 1.5 或剩餘空間 < 0.8%，標記：
`missed_entry_no_chase`。

### 新倉與既有持倉分開

輸出要拆成：
- `new_position_action`: buy / wait / no_new_entry
- `existing_position_action`: hold / trim / move_stop / exit

例：開盤已 gap hit 的標的，新倉可能是 `no_new_entry`，但既有持倉可以是
`trim 50% and trail stop`。

## 推薦前複查

在輸出任何最終推薦前，必須先做一次「Final Review Agent」複查。這個複查不是
重複看多理由，而是專門找不能買、不能追、或資料不完整的理由。

複查至少檢查：
- OKX 即時資料與 K 線是否完整且時間一致
- 是否把盤中高點誤當成現價
- 催化劑是否已經被昨天 / 盤後提前消化
- 是否有負面新聞、降評、訴訟、增發、監管或政策風險
- 今日是否有財報、FDA、Investor Day、宏觀數據等二元事件
- 同族群、ETF、QQQ / SPY 是否支持
- 是否有開盤流動性出貨、盤前衰竭、VWAP 失守
- 距離 `target_3pct_price` 還有多少剩餘空間
- `risk_reward_ratio` 是否至少 `1.5`
- 是否屬於 `gap_hit` / `already_realized`
- 是否有完整 `entry_timing_plan`
- 是否有 `do_not_chase_above` 與 missed-entry 規則
- `confirmation_only` 是否被錯寫成「可以立刻買」

複查結論只有三種：
- `pass`：可保留為最終候選
- `conditional_pass`：只能列為確認型，不能寫成即時買點
- `fail`：移除、降為 watch only，或回到前一階段重排

若複查發現缺資料，不可硬補猜測；必須降權。若全部候選都不通過，輸出
`NO TRADE / NO HIGH-CONVICTION SETUP TODAY`。

## 9:10 最終確認限制

8:45 ET 的第一次掃描只產生 provisional candidates，不可以直接寫成最終買點。
最終策略必須等 9:10 ET 第二次確認後才能輸出。

9:10 必查：
- 8:45 到 9:10 價格是否持平走高
- 5m 量能是否穩定或增加
- 是否仍靠近盤前高點
- 是否守住 VWAP / midpoint
- QQQ / SPY 是否仍支持

若 8:45 強、9:10 回落，必須降級。META 類型的盤前衰竭應在這一步被踢出。

## 順風盤動能領漲例外

不要把「漲多」本身當成拒絕理由。真正該拒絕的是：漲多後沒有剩餘空間、
R:R 不足、VWAP 失守、量能衰退、或從高點回落。

若 QQQ / SPY 順風，且個股仍在創高或貼近高點、VWAP 上方、1m/5m 結構健康，
則此類標的屬於 `momentum_leadership`。處理方式：
- 不因為延伸而自動降階。
- 必須照樣通過「跳空消耗閘門」和 `R:R >= 1.5`。
- 若已開盤且還在延伸，優先使用 🅲️ 動能確認型，而不是直接追高。
- 若同級候選中一檔持續創高、另一檔走弱，持續創高者排序必須在前。

校準範例(**非規範**)：
- 同級但盤前 / 開盤結構走弱者,應低於仍在轉強的標的。
- 硬催化且開盤後續攻、未跳空吃滿、R:R 仍足者,應保留為 🅲️ 候選,
  不可只因「已漲很多」降成觀察(INV-6)。判斷只看結構與 R:R,與 ticker 無關。

## 財報重定價 Gap 的進場規則

財報後 `beat_raise`、上調全年財測、大型合約 / 政府續約、機構確認造成的
gap，屬於 `earnings_repricing_gap`。這種 gap 可以是高勝率 setup，但仍然
不能無條件追。

先把兩件事分開：
- `prediction_rating`：今天是否有高機率觸及 / 延續 +3%
- `tradeable_entry`：從現在進場是否還有足夠空間與 R:R

處理規則：
- 若硬催化成立、價格仍貼近高點、VWAP / midpoint 守住、量能確認，
  不因 `+8% ~ +12%` 自動降為 watch only。
- 若 +3% 目標已被開盤 gap 吃完，標記
  `prediction_valid_but_no_new_entry`。
- 若開盤後繼續創高且 R:R 仍 `>= 1.5`，優先使用 🅲️ 動能確認，不要直接
  market 追高。
- 若第一根 / 前兩根 5m K 明顯賣壓、跌破 VWAP、或從盤前高點快速回落，
  才把它改成 `fading_premarket` 或 `already_priced_in`。

> 校準範例(**非規範**)：財報 / guidance / 合約形成硬催化、開盤後仍續攻的個股,屬於
> `momentum_leadership`(INV-5 / INV-6)。正確動作不是因「太延伸」踢掉,而是等 opening
> range / VWAP / 量能確認後給 🅲️ 計畫;若 entry R:R 不足,再輸出 `no_new_entry`。

### 🅰️ 追高型 (Aggressive Entry)

**適用情境(極嚴格)**:
- 機率等級 = HIGH
- 訊號 1(盤前)≥ +3%
- 訊號 2 或 3 是**重磅催化**(目標價 +50%↑ / 財報大 beat+raise / FDA 批准 / 大型政府合約 等級)
- 該日無大盤逆風(QQQ 盤前未跌)

**執行**:
- 進場時機:**ET 09:30 開盤 0-5 分鐘**
- 進場價:開盤價附近,可掛市價單或限價單(限價以開盤價 × 1.005 為上限)
- order_type: `limit_only`
- next_decision_time_et: `09:35`
- cancel_if: 第一根 5m K 收在開盤價下方、跌破 VWAP / midpoint、或 QQQ/SPY 開盤轉弱
- do_not_chase_above: `min(open_price * 1.005, R:R 仍 >= 1.5 的價格)`
- 部位:正常部位(若採用此策略,代表確信度高)

**風險與心理建設**:
- 即使重磅催化等級的強勢標的,盤中也可能先回踩 -2% 再衝,**心理上要扛得住**
- 若一進場立刻 -2%(觸 hard stop)→ 紀律出場,不戀棧
- **追高型的最大敵人是貪婪**,不是市場 — 別 +5% 不出,結果坐到 +2% 才認輸

### 🅱️ 回檔型 (Pullback Entry)

**適用情境(常見)**:
- 機率等級 = HIGH
- 訊號 1(盤前)介於 +1% ~ +3%
- 催化已存在但不是極端等級

**執行**:
- 進場時機:**ET 09:30-10:00**(開盤後 30 分鐘內)
- 進場價:`prev_close × (1.005 ~ 1.015)`,亦即 prev_close 上方 0.5%-1.5%
- 條件:回檔過程**不可破 prev_close**(破了就放棄此筆)
- order_type: `limit_only`
- next_decision_time_et: `10:00`
- cancel_if: 回檔跌破 prev_close、VWAP 失守後無法收回、或回彈量能不足
- do_not_chase_above: 回檔區上緣；若沒有回檔到計畫區,不追
- 部位:正常部位

**為何不直接買 prev_close?**
- 真正會大漲的標的，回檔常不到 prev_close 就反彈
- 等 prev_close 的人會經常**等不到**而錯過
- 守在 prev_close + 0.5% 是「兼顧安全與不錯過」的折衷

### 🅲️ 動能確認型 (Momentum Confirmation)

**適用情境(預設)**:
- 機率等級 = MEDIUM-HIGH 或更低
- 或 HIGH 但盤前未啟動(訊號 1 < +1%)
- 或催化是「待釋放型」(BMO 財報 pending、盤中等 Fed 講話)

**執行**:
- 進場時機:**ET 10:00-10:30**(開盤後 30-60 分鐘)
- 進場條件(**ALL** 需滿足):
  1. 站上開盤後第一個 30 分鐘的高點
  2. 站穩 15 分鐘以上(不要 spike then fall)
  3. 30 分鐘量能 > 過去 10 個交易日同期均量
- 進場價:依當下實際成交價(通常 prev_close + 1% ~ +2%)
- order_type: `stop_limit_after_trigger`
- next_decision_time_et: `10:30`
- cancel_if: 突破後跌回 opening range、VWAP 失守、或量能未放大
- do_not_chase_above: opening-range high + 0.5%,且 R:R 必須仍 >= 1.5
- 部位:正常或半倉(若機率為 MEDIUM,建議半倉)

**為何要等 30 分鐘?**
- 開盤前 30 分鐘流動性紊亂,常見 spike 後回吐
- 30 分後若仍站穩 → 真實動能確認

### 槓桿 ETF 特例（SOXL / TQQQ 類）

槓桿 ETF 可以列入候選，但必須降低部位和提前停利。

規則：
- 預設半倉
- 不做 🅱️ 回檔型，因為 3x ETF 回檔深度不穩定
- 若盤前已 > `+3%` 且板塊 breadth 支持，可用 🅰️ 小倉或 🅲️ 確認
- TP1 提前至 `+2%`
- 若失守 VWAP、從高點回落超過 `-3%`，不得追高
- 報告中必須明寫 `ETF leverage risk`
- 代價:放棄 1-2% 漲幅;**換來的是大幅降低假突破風險**

---

## 出場計畫(三層階梯)

### 獲利了結 (Take Profit)

**為何要分批?**
- 一次出全部 → 出在 +3% 結果它漲到 +15%,你會懊悔
- 從不出 → 出在 +1% 你會痛恨自己
- 分批可讓**情緒不左右決策**,且不論最終走勢如何都有合理結果

**標準階梯**:
```
TP1 @ entry × 1.03   出 50% 部位  ← 觸 +3% 主要目標達成,鎖一半利潤
TP2 @ entry × 1.05   出 30% 部位  ← 觸 +5% 再減
TP3 @ 移動停利       出 20% 部位  ← 用 trailing stop 或收盤前出
```

**移動停利建議**:當價格 > entry × 1.05,啟動以「最高點 - 1.5%」為停利位。
這讓你在一路走高的強勢股(盤中可觸 +15%↑)中能跟到大部分漲幅。

### 停損 (Stop Loss)

**Hard Stop** = `entry × 0.98`(進場價下方 2%)

**為何 2%,不是更鬆?**
- 預測類交易的勝率約 55-65%(HIGH 等級)
- 設停損 -2%、停利 +3% → 期望值: 0.6 × 3 - 0.4 × 2 = +1.0%(正期望)
- 若停損 -5% → 期望值: 0.6 × 3 - 0.4 × 5 = -0.2%(負期望,**不要交易**)

**停損紀律**:
- 設好就不要動,不要因為「就快反彈了」而拖
- 用實際 stop order 掛單,不要心理停損

### 時間退出 (Time Stop)

```
ET 11:00 (台北 23:00)  → 若仍未觸 +2%,出 1/3,動能不如預期
ET 14:00 (台北 02:00)  → 若仍未觸 +3%,出 1/2,本日機會降低
ET 15:30 (台北 03:30)  → 收盤前 30 分,全部出清
```

**為何收盤前必須全出?**
- 隔日跳空風險(尤其後續財報、宏觀事件)
- 本 skill 是**日內預測**,持倉過夜超出設計範圍
- 想做波段持有要用不同的 skill / 邏輯

---

## 雙模式部位計算

### 🟢 現貨模式(OKX spot / Robinhood / IBKR)

**範例**:預測 MU(prev_close $750),進場價 $760(回檔型)

| 項目 | 計算 | 金額 |
|------|------|------|
| 配置部位 | $1,000(自選資金大小) | $1,000 |
| 進場價 | $760 | - |
| 股數 | $1000 / $760 | 1.32 股(分數股)或 1 股 |
| Hard Stop | $760 × 0.98 = $744.8 | -$20(-2% per trade) |
| TP1 (+3%) | $760 × 1.03 = $782.8 | +$15(半倉鎖利) |
| TP2 (+5%) | $760 × 1.05 = $798 | +$15(再鎖) |

### 🟡 OKX 永續模式 (OKX USDT-SWAP)

**範例**:同樣是 MU,用 OKX 永續 `MU-USDT-SWAP`

| 項目 | 計算 | 金額 |
|------|------|------|
| 保證金 | $100(自選) | $100 |
| 槓桿 | 3x(新手建議) | - |
| Notional | $100 × 3 = $300 | $300 |
| 進場價 | $760(MU-USDT-SWAP 價格) | - |
| 1% 個股波動 → 損益 | $300 × 1% = $3 | $3/% |
| Hard Stop -2% | -$300 × 2% = -$6 | **-6% ROI on margin** |
| TP1 +3% | +$300 × 3% = +$9 | **+9% ROI on margin** |
| 強平距離 | 約 -33% 個股跌幅(3x) | 極不可能觸發 |

**永續模式特別注意**:
1. **資金費率(funding rate)** — 持倉跨過資金費結算時(每 8 小時)會收/付費。
   美股永續 funding rate 通常 ≤ 0.01%/8h,影響小,但要記住
2. **24/7 交易** — 即使美股休市,永續仍會動。本 skill 預測限定美股開盤時段
3. **滑點** — 永續流動性 < 現貨,大單會有滑點,小單(< $1000 notional)影響小
4. **槓桿選擇**:
   - 新手:1-3x
   - 經驗:3-5x
   - 老手:5-10x(但日內快進快出,絕不過夜)
   - **絕不超過 10x**(本 skill 的訊號精度不支援高槓桿)

---

## 三策略回測對照(**非規範校準範例**)

> 以下用一個歷史強勢股(盤前 +6%+、開盤跳空、盤中觸 +18%)示範三策略的盈虧差異。
> 這是說明用的回測,**不是規則**:重點是「HIGH + 重磅催化 + 盤前已飛 → 主動指定 🅰️」
> 這條可觀測邏輯(§4.4 / INV-12),與是哪一隻股票、哪一天無關。

**已知**:
- prev_close: ~$750
- 盤前:+6.3% to ~$798
- 開盤:跳空 ~$830 (+10.7%)
- ET 11:00 觸最高 ~$885 (+18%)
- 收盤:~$876 (+16.7%)

| 策略 | 進場價 | TP1 出場 | TP2 出場 | TP3 出場 | 加權報酬 |
|------|--------|---------|---------|---------|---------|
| 🅰️ 追高型 | $830(開盤) | $855(+3%)出 50% | $872(+5%)出 30% | 收盤 $876 出 20% | ~+4.7% |
| 🅱️ 回檔型 | **等不到**($760 沒回檔到) | - | - | - | **0%(放棄)** |
| 🅲️ 動能確認型 | $850(30 分後) | $876(+3%)出 50% | 觸 +5% 但未達 → 移動停利 | 高點 $885 → 移動停 ~$871 | ~+3.5% |

**結論**:MU 這種「全程一路漲」的標的:
- 追高型最大贏家(+4.7%)
- 動能確認型也賺(+3.5%)
- 回檔型完全錯過(因為訊號是 HIGH + 重磅催化,skill 應該推 🅰️ 而不是 🅱️)

**對 skill 的啟示**:**為 PICK 主動指定策略很重要**,不能讓使用者自己三選一。
HIGH + 重磅催化必須推 🅰️,不然會錯過 MU 等級的機會。

---

## 一個重要免責

預測類交易的長期勝率上限約 60-65%(即使是頂級量化基金)。
本 skill 設計目標是**正期望值的紀律框架**,不是「保證賺錢」。

每筆 -2% 停損是預期內成本,連續 3-4 筆停損是正常統計波動。
若使用者無法承受連續停損的心理壓力,**建議只做紙上交易**累積經驗。

最後更新:2026/05/29(通用化重構:個股/回測標為非規範,規則統一指向 SKILL.md §1 INV-11 / INV-12)
