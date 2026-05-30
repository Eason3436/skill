# 盤前訊號搜尋手冊 (Pre-market Signal Playbook)

> ⚠️ **位階說明(務必先讀):** 本檔是「搜尋與分類手冊」,**不是規範來源**。
> 所有判斷規則以 `SKILL.md §1 INV-*` 為準;本檔與 INV 衝突時以 INV 為準。
> 本檔出現的**任何個股清單都是非窮舉範例**,只示範分類粒度 —— 實際 basket /
> peer / breadth 一律對 **live OKX universe 中帶相同 `theme_tag` 的成員**動態推導
> (見 `SKILL.md §2`)。本檔出現的**任何「XXX 日 / XXX 類型」案例都是非規範校準說明**,
> 判斷現場標的時只看對應 INV 的可觀測條件,與是哪一隻股票、哪一個日期無關。

針對台灣使用者晚上 7-9 點查詢的場景,優化新聞與行事曆搜尋。
此時 ET 約 07:00-09:00,具備兩大資訊優勢:
1. **隔夜亞洲時段新聞**已釋出約 8 小時(台積電月營收、中概股政策、亞洲產業鏈)
2. **盤前異動**已累積 3-5 小時(ET 04:00 開始的盤前交易已有量能)

---

## 訊號 1:盤前異動(Premarket Movers)

### 主要搜尋

```
web_search: "premarket movers {DATE}"
web_search: "biggest premarket gainers {DATE}"
web_search: "stocks moving premarket {DATE}"
```

### 個股盤前報價

```
web_search: "{TICKER} premarket {DATE}"
web_search: "{TICKER} premarket price quote {DATE}"
```

### 解讀規則

| 盤前漲幅 | 開盤後續漲 +3% 機率(經驗值)|
|---------|---------------------------|
| +5% 以上 | 70-80%(但已大漲,進場價差不利) |
| +2% 到 +5% | 50-60%(甜蜜區) |
| +1% 到 +2% | 30-40% |
| <+1% | 10-15%(接近基準率) |

⚠️ 盤前流動性低,**盤前 +X% 不等於開盤就 +X%**,常見開盤跳空後回吐。

### sodUtc0 全清單排序

每次 Stage 1 都要先算每支 OKX instCategory=3 支援標的：
- `current_vs_sodUtc0_pct`
- `session_high_vs_sodUtc0_pct`
- `high_to_current_pullback_pct`

不要只看 24h change。24h 視窗會混入前一日波動，容易漏掉今日真正從昨收反彈
的標的。

規則：
- 現漲幅 `>= +2.5%` 的標的不能直接消失。
- 盤中最高漲幅 `>= +3%` 的標的必須標成 `hit_and_actionable`、
  `hit_but_faded`、`watch only` 或明確 reject。
- 若盤前一開始是紅的，但後來站回 `sodUtc0`，要進入 `reversal_bucket`。

---

## 訊號 2:財報行事曆

### 今日盤前財報(BMO,Before Market Open)

```
web_search: "earnings before bell {DATE}"
web_search: "earnings calendar BMO {DATE}"
web_search: "biggest earnings reports today {DATE}"
```

### 昨晚盤後財報(AMC,After Market Close,影響今日)

```
# {YESTERDAY} = ET 前一日
web_search: "earnings after the close {YESTERDAY}"
web_search: "{TICKER} earnings results {YESTERDAY}"
```

### 本週財報行事曆(用於 1-2 日前布局)

```
web_search: "earnings this week {WEEK_OF_DATE}"
```

### 解讀規則

| 情境 | 訊號等級 |
|------|---------|
| AMC 昨晚財報 beat + 指引上調 | high(常見今日跳空 +5-10%) |
| BMO 財報已公布 + beat | high |
| BMO 財報未公布(8:30 ET 前)| **event_pending**(只能標 medium 並警示) |
| 本週稍後有財報(2-5 日)| medium(預期心理 + IV 上升) |
| 無財報 | 無觸發 |

⚠️ **BMO 財報的最大陷阱**:財報在開盤前 30 分鐘公布,公布前推 HIGH 是危險的
(beat → 飛,miss → 崩,binary 結果)。**等財報出來再推**。

### 財報後次日開盤延遲反應

有些 AMC 財報 beat 的股票，盤前只小漲，但正式開盤後因流動性進來才爆發。

觸發條件：
- 前一日 AMC 財報 `beat_raise` 或明顯 beat
- 盤前 Signal 1 介於 `+0.5% ~ +1.5%`
- 沒有反向 guidance、降評或重大負面

處理方式：
- 標記 `open_premium_candidate: yes`
- 不因「盤前只有小漲」直接淘汰
- 放入 Stage 2 或 `reversal_bucket`
- 策略以 🅲️ 動能確認為主，保留到 10:00-10:30 ET 看開盤區間突破

> 校準範例(**非規範**)：某 AMC beat_raise 個股盤前僅約 +0.8% 偏弱,但開盤瞬間放量上攻;
> 過度相信盤前反應會低估 regular-session liquidity premium → 應標 `open_premium_candidate`
> 留到開盤後確認(INV-2 / INV-11)。

### 財報重定價 Gap 例外

財報後的大幅 gap 不能和「無催化追高」混為一談。若結果是 `beat_raise`
（營收 / EPS 雙超預期且上調財測），或同時有大合約、政府續約、機構加碼等
硬資訊，這是基本面重定價。

處理方式：
- 標記 `extension_type: earnings_repricing_gap`
- 不因盤前 `+8% ~ +12%` 自動降成 watch only
- 先保留到 Stage 3 / Stage 3.5，再用 K 線、VWAP、量能與 R:R 決定能不能進
- 若 +3% 目標已被跳空消耗，結論是 `prediction_valid_but_no_new_entry`，
  不是把預測本身打成錯誤

> 校準範例(**非規範**)：財報 / guidance / 合約 / 機構確認形成硬催化的個股,若 live
> structure 持續創高,應歸類為 `momentum_leadership` 或 `earnings_repricing_gap`,
> 不能只因「太延伸」拒絕(INV-5 / INV-6)。

---

## 訊號 3:隔夜消息(台灣使用者獨家優勢)

### 通用搜尋

```
web_search: "{TICKER} news overnight {DATE}"
web_search: "{COMPANY_NAME} announcement {DATE}"
web_search: "{TICKER} analyst upgrade downgrade {DATE}"
```

### 亞洲時段重點(台灣使用者最有利)

| 標的 | 隔夜訊號來源 |
|------|-------------|
| TSM(台積電)| 月營收公告(每月 10 日左右) |
| TSM, NVDA, AVGO | 台積電法說會、業績指引 |
| BABA(阿里巴巴)| 中國政策、港股表現、中概股監管 |
| MU, SNDK, AMD | 韓國/日本記憶體大廠(三星、SK 海力士、鎧俠)新聞 |
| 所有半導體 | 日經科技新聞、韓國貿易數據 |
| 加密相關股(COIN, MSTR, CRCL)| 亞洲時段比特幣/以太坊走勢 |

### 重點搜尋查詢

```
web_search: "TSMC monthly revenue {DATE}"           ← 台積電月營收
web_search: "Samsung memory pricing {DATE}"         ← 記憶體價格
web_search: "China tech regulation {DATE}"          ← 中概股政策
web_search: "Bitcoin overnight price {DATE}"        ← 加密股連動
web_search: "Nikkei semiconductor news {DATE}"      ← 日本半導體
```

### 分析師動作(隔夜常見發布)

```
web_search: "analyst price target raise {DATE}"
web_search: "{TICKER} upgraded {DATE}"
web_search: "{TICKER} downgraded {DATE}"
web_search: "sell-side initiation {DATE}"
```

### ⭐ 強訊號專屬搜尋(對應 SKILL.md 組合 B)

當查詢的目的是「**找今天會大漲的標的**」時,以下這幾條搜尋**必須跑一次**,
因為這些是歷史上 +10% 等級的個股漲幅主要來源:

```
# 1. 重磅目標價上修(歷史上多次抓到 +10%↑ 標的的關鍵搜尋)
web_search: "biggest analyst price target raise {DATE}"
web_search: "street high price target {DATE}"
web_search: "stocks upgraded today {DATE}"

# 2. 盤前財報結果(常見 BMO 7:00 / 8:00 / 8:30 ET 公布)
web_search: "premarket earnings beat {DATE}"
web_search: "earnings surprise beat {DATE}"

# 3. 重大企業事件
web_search: "stock buyback announcement {DATE}"
web_search: "merger acquisition {DATE} tech"
web_search: "FDA approval {DATE}"           ← 藥廠

# 4. 直接掃 premarket 漲幅榜
web_search: "biggest premarket movers {DATE}"
web_search: "premarket gainers list {DATE}"
```

> 校準範例(**非規範**):某日「target raise」搜尋找到一檔券商目標價巨幅上修的標的,
> 「premarket movers」搜尋又顯示它盤前已 +6%+ → 組合 A(盤前 ≥ +2%)+ 組合 B(重磅上修)
> 雙重滿足 → HIGH(§4.3.1)。重點是兩條可觀測訊號疊加,與是哪一隻股票無關。

### 解讀規則

| 隔夜消息類型 | 訊號等級 |
|--------------|---------|
| 重大企業利多(收購、合約、產品突破)| high |
| 重磅 sell-side 上修(目標價 +30% 以上)| high |
| 一般分析師升評 | medium-high |
| 亞洲產業鏈正面數據(月營收 yoy 雙位數成長)| medium |
| 亞洲股市大漲(同類 ADR 受惠)| medium |
| 無消息 | 無觸發 |

### 新鮮度 / 驚喜度檢查

Signal 3 不能只判斷新聞是正面還是負面，還要判斷市場是否已經反應。

每個靠新聞推進的候選股，都要補查：

```
web_search: "{TICKER} {CATALYST_KEYWORD} yesterday"
web_search: "{TICKER} {CATALYST_KEYWORD} after hours"
web_search: "{TICKER} stock moved yesterday why"
```

必填欄位：
- `catalyst_first_seen_time`
- `catalyst_lifecycle_stage`
- `market_already_paid`
- `new_information_delta`
- `tradable_edge_remaining`
- `prior_reaction_attribution`
- `same_catalyst_prior_reaction_pct`
- `surprise_factor`
- `buy_the_rumor_sell_the_news_risk`

降權規則：
- 同一催化劑已在 24 小時內推動股價超過 `+2%`：Signal 3 轉中性或偏負。
- 前一交易日已因同一催化劑上漲超過 `+3%`：今天同催化自動降一級。
- 今天只是「正式上線 / 正式公布 / 活動開始」，但市場昨天已經知道：視為
  `known-execution`，不是 fresh catalyst。
- 若同時出現盤前高點提前形成、開盤前 20-30 分鐘 lower highs，標記
  `buy_the_rumor_sell_the_news_risk: high`。

> 校準範例(**非規範**)：某「正式上線」當天,前一日測試/洩漏消息已推約 +3.7%,
> 盤前高點過早形成後回落 → `formal_execution` + `market_already_paid` + 盤前衰竭;
> Signal 3 降權、禁追、等 10:00 後動能確認(INV-4 / INV-13)。判斷只看 lifecycle 與
> 結構,與是哪一隻股票無關。

### 個股催化優先於板塊假設

Broad proxy 只能當背景，不能直接否決有自身催化的股票。

在拒絕**任何容易被宏觀/板塊敘事覆蓋的標的**(crypto-adjacent、high-beta、China-linked、
sector-linked …)前，必須先對該 ticker 跑自身催化檢查：

```
web_search: "{TICKER} product launch {DATE}"
web_search: "{TICKER} regulatory approval {DATE}"
web_search: "{TICKER} analyst reiterates buy {DATE}"
web_search: "{TICKER} partnership contract {DATE}"
web_search: "{TICKER} company news today {DATE}"
```

若找到產品上線、監管批准、合作案、分析師上調 / 重申買入等個股催化，且
OKX 盤前 / 盤中顯示 current `>= +2%` 或 high `>= +3%`：
- 標記 `company_specific_catalyst_override: yes`
- 不得因 BTC 弱、China risk、sector fade 等 broad thesis 直接 `REJECT`
- 至少進 Stage 2，除非直接負面新聞或 K 線 / R:R 失敗

> 校準範例(**非規範**)：被歸類成 crypto-adjacent 的個股,仍要先確認是否有 fintech /
> app / 產品 / 監管 / 分析師催化;若有,proxy(如 BTC)弱不能當 veto(INV-7)。

### 催化劑生命週期分類

先分類，再評分：

| lifecycle | 意義 | 預設處理 |
|---|---|---|
| `rumor_leak` | 傳聞 / 測試 / 洩漏 | 需等確認，最高 MEDIUM-HIGH |
| `first_confirmation` | 第一次被正式確認 | 可高分，但要看價格是否已消化 |
| `formal_execution` | 已知事件正式上線 / 執行 | 通常降權 |
| `post_reaction_day2` | 昨天已反應，今天第二天 | 先降一級 |
| `repeated_headline` | 同一新聞重複轉載 | 不可當新催化 |
| `binary_event_pending` | 財報 / FDA / 監管結果未出 | 禁止追高 |
| `binary_event_resolved` | 結果已出 | 重新看驚喜度與價格結構 |
| `analyst_repricing` | 分析師大幅重估 | 可高分，但要看幅度與是否已反應 |
| `sector_sympathy` | 同族群補漲 | 不能單獨 HIGH |

未來類似陷阱：
- 產品正式上市，但前一天已因測試消息上漲。
- FDA 正式核准，但市場早已在 advisory committee 後押注。
- 財報前分析師集體上修，但真正財報還沒公布。
- Investor day / conference demo 只是重複已知敘事，沒有新數字。
- 合作案由另一家公司再發一次新聞稿，但合約金額沒有新增。

正確做法：
- 若 `new_information_delta: none`，不論新聞標題多正面，都不能給 HIGH。
- 若 `market_already_paid: yes`，只能等價格重新確認，不能盤前直接追。
- 若 `prior_reaction_attribution: uncertain`，最多 MEDIUM-HIGH。

---

## 訊號 4:同類股延伸動能查詢

### 步驟

1. 取昨日漲幅 ≥ 5% 的清單內標的(用 OKX `chg24hPct` desc)
2. 對每檔大漲股,查其同類股是否昨日漲幅相對較弱
3. 若有,該同類股就是今日「補漲候選」

### 範例(**非規範,僅示意**)

```
昨日:某記憶體龍頭 +17%(券商大幅上修目標價)
今日候選:同 memory/storage 中昨日漲幅相對較弱的 peer(有補漲空間)
        同板塊 3x ETF(放大效應)
→ 實際 peer 由 live universe 的 theme_tag 動態取得(INV-9 / INV-10),不依賴固定代號。
```

### 規則

- 同類股昨日 +10% 以上 + 本檔昨日 +0~+3% → 強補漲(medium-high)
- 同類股昨日 +5-10% + 本檔昨日 +0~+2% → 一般補漲(medium)
- 同類股昨日 + 本檔昨日都已大漲 → 弱(無觸發)

### Product-Line Peer Mapping

Signal 4 要區分「同板塊」與「同產品線」。同產品線財報 beat 的 read-through
比一般同族群補漲更強。

映射機制(通用)：來源公司財報/指引重定價某條產品鏈 → 對 **live universe 中同產品鏈
(`theme_tag` 相同或上下游)的成員**做 read-through 重查。映射由 `theme_tag` + 產品鏈關係
動態推導,**不依賴任何封閉清單**。

> 範例(**非窮舉,僅示範粒度**)：記憶體龍頭 beat / HBM 需求 → 重查同 memory/storage 與相關
> semis;AI 晶片龍頭 beat / AI capex → 重查 AI chips 與 foundry;雲端 AI capex 強 → 重查
> AI 供應鏈;加密交易所 / 幣價突破 → 重查 fintech/crypto-adjacent。具體個股代號僅為說明,
> 新標的進 universe 時用同一機制接住。

規則：
- 同產品線來源公司財報 beat 且 target 盤前 > `+1%`，Signal 4 至少 MEDIUM。
- beat / guidance 超預期幅度大，或來源股本身大漲 > `+5%`，Signal 4 可到
  MEDIUM-HIGH。
- 同產品線 peer 不可 Stage 1 直接刪除，除非有硬負面或 OKX live data 不可用。

> 校準範例(**非規範**)：某次記憶體/儲存龍頭財報強,同 memory/storage read-through 的 peer
> 即使無自身新聞,也應進 Stage 2 / Stage 3.5(對應 SKILL.md §2.3 與 INV-10)。

### Basket / Proxy Decoupling

當使用「BTC 弱 → crypto proxies fade」或「半導體昨天弱 → 今天續弱」這類
broad thesis 時，必須先確認 basket 是否真的跟著 proxy。

檢查方式：
- 取 proxy：BTC、QQQ、SOXL、sector ETF 或最相關大盤因子
- 取 basket：同主題所有 OKX 標的
- 算每檔 current vs reference close 與 high vs reference close

判斷：
- 若 basket 內至少 2 檔 current `>= +2%` 或 high `>= +3%`，標記
  `decoupling: yes`
- 若至少 3 檔同向走強，Signal 4 加 `+1.0`
- 若 decoupling 成立，broad thesis 不得用來整組 reject

> 校準範例(**非規範**)：proxy(如 BTC)沒漲,但同 `theme_tag`(如 fintech/crypto-adjacent)
> 多檔 live 成員同向上攻 → 主題可能是 fintech / risk-on / equity beta 而非 proxy beta。
> basket 成員一律對 live universe 動態取得(INV-7)。

### Sector Breadth Spillover

若**同一 `theme_tag` 至少 3 檔 live 成員** session high `>= +3%`，該板塊啟動
`sector_breadth_upgrade`。成員一律對 live universe 動態取得,**不依賴封閉清單**;
沒被下列範例列到的板塊(如核能、量子、生技、稀土),只要 live 成員觸發門檻同樣建桶。

> 範例題材(**非窮舉**):半導體、AI 軟體/cloud、memory/storage、AI infra/optical、
> fintech/crypto-adjacent、ETF/market proxy …。具體個股代號僅供說明。

處理方式：
- 板塊 leader、今日 fresh mover、高 beta proxy 必須互相比較
- 不可把所有成分股停在 watch only
- 無個股催化但 breadth 強者可到 MEDIUM-HIGH
- 有個股硬催化者可到 HIGH

### Same-Theme Freshness Ranking

同一題材內，選「今天才動」的，不選「昨天已噴完」的。

必填欄位：
- `prior_day_move_pct`
- `today_current_move_pct`
- `today_high_move_pct`
- `current_distance_from_high_pct`
- `move_phase`

排序：
1. `today_fresh_mover`
2. `two_day_continuation` 且仍貼近高點
3. `laggard_reversal`
4. `yesterday_exhausted`

> 校準範例(**非規範**)：同題材兩檔,若 A 的主升段在昨天、今天只小漲,而 B 今天才剛
> 發動並貼近高點,則 B(`today_fresh_mover`)必須排在 A(`yesterday_exhausted`)前面(INV-9)。

### 板塊暴跌後系統性反彈

前一日板塊大跌不一定是今天的負面訊號；可能代表隔日 forced-selling rebound。

觸發條件：
- 同一板塊昨日平均跌幅明顯，或 ETF / 3x ETF 昨日跌超過 `-5%` / `-10%`
- 今日至少 3 檔同板塊標的站上 `sodUtc0`
- 領漲不只一檔，且 laggard 開始補漲

處理方式：
- 建立 `sector_rebound_candidate` bucket。
- 對**該 `theme_tag` 的 live 成員**(及其 ETF/proxy)動態重查,不依賴封閉清單。
- 板塊反彈本身最高通常 `MEDIUM-HIGH`，但可以讓無明確個股新聞的股票進入
  Stage 2 / Stage 3.5 驗證。

> 校準範例(**非規範**)：前日某高 beta 板塊劇烈波動後,多檔成員隔日同步站回 sodUtc0;
> 這不是單一催化劑,而是板塊反彈模式(INV-10),前日弱勢不得當成純負面。

### Post-Crash Bounce Amplifier

若前一日板塊 / 3x ETF 崩跌，隔日宏觀轉正時反彈 beta 會被放大。

觸發條件：
- 板塊 proxy 前日跌幅 > `-8%`
- 今日 QQQ / SPY / 主要 macro context 轉正
- 個股在事件後 Signal 1 > `+1%`

處理方式：
- 把前日弱勢從「負面懲罰」改為「反彈潛力」
- 標記 `bounce_amplifier: medium/high`
- 讓該板塊的高 beta live 成員(及其 3x ETF proxy)進 Stage 2(動態取得,非封閉清單)

### Leveraged ETF as Sector Proxy

`SOXL` 這類 3x ETF 可作為板塊方向標的，但必須標注槓桿風險。

條件：
- `SOXL` 盤前 / 事件後 Signal 1 > `+3%`
- 半導體 breadth 支持
- OKX `1m/5m/15m/1h/1d` K 線完整

處理：
- 不因 ETF 身分自動排除
- 標記 `is_leveraged_etf: yes`
- 預設半倉
- TP1 提前到 `+2%`
- 優先 🅰️ 或 🅲️，避免 🅱️ 回檔型

---

## 訊號 5:技術設置查詢

### OKX 指令

```bash
# 取昨日收盤、近 20D 高、關鍵 EMA
okx market candles {SYMBOL}-USDT-SWAP --bar 1Dutc --limit 30
okx market indicator ema {SYMBOL}-USDT-SWAP --bar 1Dutc --params 20,50,200
okx market indicator rsi {SYMBOL}-USDT-SWAP --bar 1Dutc

# 4H 級別 — 看盤前是否已在突破中
okx market candles {SYMBOL}-USDT-SWAP --bar 4H --limit 20
okx market indicator rsi {SYMBOL}-USDT-SWAP --bar 4H
```

### 觸發條件

- 昨日收盤距 20D 高 ≤ 2% + RSI 50-70 → medium-high(臨界突破)
- 昨日剛突破 20D 高 + 今日盤前持穩 → medium(延伸動能)
- 強烈反轉 K(吞噬、十字啟明)+ 有催化新聞 → medium

⚠️ 技術設置**單獨**幾乎不足以推到 HIGH,必須配合訊號 1-3。

---

## 訊號 6:今日宏觀事件

### 經濟數據

```
web_search: "economic calendar {DATE}"
web_search: "US economic data {DATE}"
```

### 重點關注(高影響)

| 事件 | 公布時間(ET)| 影響 |
|------|------------|------|
| CPI(消費者物價指數)| 08:30 | 全市場巨震 |
| Core PCE | 08:30 | Fed 偏好指標 |
| NFP(非農就業)| 08:30(月首週五)| 巨震 |
| FOMC 利率決議 | 14:00(雙月)| 巨震 |
| FOMC Minutes | 14:00 | 中度影響 |
| Fed 主席 / 理事講話 | 不定 | 視內容 |

### 規則

- 今日 08:30 有 high-impact 數據 + 數據尚未公布 → 啟動 Macro Data Gate，
  禁止輸出 final picks，只能輸出 watchlist
- 今日 14:00 有 FOMC → 早盤 high 可保留,但中午後預測失效
- 今日無大事 → 個股訊號維持原信心

### Macro Data Gate

若 PCE / CPI / GDP / NFP / FOMC 等高影響事件尚未公布，且前日板塊被明顯壓制，
不要在 6-7am ET 鎖定答案。

處理方式：
- 6:00-7:30 ET：只做 early watchlist，不做 final picks
- 8:45 ET：事件後 15 分鐘，做第一次 full universe rescan
- 9:10 ET：做第二次 confirmation scan，才允許 final candidates

高影響宏觀日輸出：
- 數據前：`MACRO DATA GATE ACTIVE — NO FINAL PICKS BEFORE DATA`
- 8:45 後：Top 8-10 provisional candidates
- 9:10 後：0-3 final candidates 或 no trade

### Macro-Event Signal Reset

若高影響宏觀事件在預測時段公布，事件前與事件後要分開評分。

重置條件：
- 事件為 PCE / CPI / PPI / GDP / NFP / FOMC
- 事件前 Signal 1 為負或偏弱
- 事件後 30 分鐘內 Signal 1 轉為 `+1.5%` 以上
- 無個股硬負面

處理方式：
- 標記 `macro_reset_triggered: yes`
- 用事件後 Signal 1 重新排序
- 原本因事件前負值被 reject 的股票，必須 rollback / re-rank

> 校準範例(**非規範**)：某高影響數據(如 PCE)前為負、事件後 30 分內快速站上 +2% 的個股,
> 正確做法是用事件後 K 線重置 Signal 1,而非沿用事件前 reject(INV-3)。

---

## 整體 Workflow(總結)

```
台灣 19:00 / ET 06:00-07:00
↓
Phase 0: 時間意識 + 今日是否有 high-impact macro / BMO pending
↓
若 macro pending:
  → 只輸出 early watchlist
  → 不輸出 final picks
  → 指定 8:45 ET 重新掃描

台灣 20:45 / ET 08:45
↓
First Full Rescan: 全宇宙重新評分
  - 訊號 1:OKX post-event K-line
  - 訊號 2:earnings calendar BMO + AMC
  - 訊號 3:隔夜消息(主跑亞洲時段)
  - 訊號 4:Product-line peer + sector rebound
  - 訊號 5:OKX 技術 / K 線
  - 訊號 6:macro result bias
↓
輸出 Top 8-10 provisional candidates
↓
台灣 21:10 / ET 09:10
↓
Second Confirmation Scan:
  - 8:45→9:10 方向是否延續
  - 5m 量能是否增加
  - 是否靠近盤前高點
  - VWAP / midpoint 是否守住
  - QQQ / SPY 是否確認
↓
Final: 輸出 0-3 支 + 策略 + 規避條件，或 no trade
```

最後更新:2026/05/29(通用化重構:清單改為非窮舉範例、案例標為非規範、規則統一指向 SKILL.md §1 INV-*)
