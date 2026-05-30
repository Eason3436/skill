---
name: us-stock-mover-predictor
description: >
  美股當日漲幅預測器(OKX stock-token / TradFi SWAP 全清單版 — 盤前模式)。當使用者問
  「今天哪支美股會漲」「美股盤前看誰」「待會兒開盤該買哪支」「盤前異動」
  「今晚美股有什麼機會」「預測美股」「OKX 美股永續 今天該追哪支」
  「掃一下開盤前」或任何「預測即將開盤的美股當日是否漲 3%+」需求時觸發。

  本 skill **不是事後統整**(那個是 us-stock-mover-scanner)。
  本 skill **預測未來** — 在美股開盤前 30-90 分鐘做機率判斷:
  哪 2-3 支標的盤中(09:30–16:00 ET)觸及 +3% 漲幅的機會最高。

  範圍鎖定 OKX `instCategory=3` 的 stock-token / ETF / pre-market SWAP 全清單
  (數量以 OKX public instruments 實際回傳為準,不寫死)。
  使用情境是台灣使用者晚上 7-9 點(=ET 早上 7-9 點)查詢,
  美股將於 ET 09:30 開盤。即使使用者只說「看一下盤前」「今晚美股」也觸發。
---

# US Stock Mover Predictor (OKX Stock-Token SWAP — Pre-market Mode)

本文件分成三層,**閱讀與套用優先序由上而下**:

1. **§0 通用化準則(Generalization Doctrine)** — 規則必須怎麼寫、怎麼讀的元規則。
2. **§1 核心不變量(Core Invariants, INV-1 … INV-19)** — 唯一的規範來源。
   每條原則只寫一次,帶齊可觀測條件、數值門檻、必填欄位、必用措辭。
3. **§2 動態 universe 與題材分類 / §3 執行機制 / §4 訊號與輸出** — 操作層,
   負責「執行」不變量,不重述規則,只引用 `INV-*`。

最後是 **附錄 A:校準案例(非規範)** — 所有帶個股名稱與日期的歷史案例集中於此,
僅作為「這條不變量長什麼樣」的說明,**永遠不是觸發條件本身**。

---

## §0 通用化準則(Generalization Doctrine)

這一節的位階高於本文件其他任何敘述。它的存在,是為了解決一個反覆出現的失敗模式:
**「為了某一天某一隻股票打了補丁,隔天換一隻股票或換個日期,規則就失效。」**

### 0.1 規則的錨點

每一條規則都必須錨定在**可觀測訊號**上,絕不錨定在個股代號或日期上。

- ✅ 正確錨點(可重複套用到任何標的):
  `catalyst_lifecycle_stage`、`same_catalyst_prior_reaction_pct`、`memory_age_trading_days`、
  `remaining_room_pct_to_target_3pct`、`risk_reward_ratio`、`basket_decoupling_count`、
  `move_phase`、`high_to_current_pullback_pct`、`sector_breadth_count`、VWAP / 結構狀態。
- ❌ 錯誤錨點(只能命中一次,必然腐爛):
  「因為這是 QCOM」「因為日期接近 5/27」「因為 BTC 弱所以 crypto 全砍」
  「半導體只看清單上這 12 檔」。

判斷句的標準形:`若 {可觀測條件 + 數值門檻} → {動作}`。個股名稱與日期只能出現在
「例如」之後,而且只能在**附錄 A**,並標明「非規範」。

### 0.2 動態優先於寫死

- universe、題材/板塊成員、product-line peer、basket、breadth 計數,
  **一律從 live OKX `instCategory=3` 清單動態推導**(§2)。
- 任何列在文件裡的個股清單,一律是**非窮舉範例(non-exhaustive examples)**,
  用來示範分類邏輯,**不是封閉名單**。一個沒被列進範例的板塊爆發(例如核能、量子、
  生技、稀土)也必須能被同一條動態規則接住。
- 任何數量(universe 檔數)、任何日期快照,都不可當成規則常數;一律以 live 回傳為準。

### 0.3 加規則前,先強化既有不變量

遇到新的失敗案例時,**預設動作是「找出它屬於哪一條 INV-*,並強化那一條」**,
而不是新增一個版本段落。只有當失敗模式無法歸入任何現有不變量時,才新增 INV。

- 禁止:每次失敗就 append 一個 `vX.Y` 段落,導致同一道理散落 4-5 處。
- 必做:把新案例寫進**附錄 A**,連結到對應的 INV 編號;若該案例揭露了門檻不準,
  就調整那條 INV 的門檻(數值是可調參數,允許保留與微調)。

### 0.4 數值門檻 vs 過度擬合(重要區分)

- **數值門檻不是過度擬合**(例:R:R ≥ 1.5、room ≥ +2.0%、gap > +8% 降階、停損 -2%)。
  這些是跨標的通用的調參,**保留**。
- **過度擬合 = 把「個股 + 日期」當成規則**。這才是要消滅的東西。
- 因此本次重構:保留所有數值,消滅所有「以 ticker/日期為觸發」的寫法。

### 0.5 怎麼讀這份文件

- `§1 INV-*` 是規範。衝突時以 INV 為準。
- `§2–§4` 是操作層,只能引用 INV,不得新增與 INV 衝突的規則。
- **附錄 A 的案例不可當規則。** 模型若在現場想「這是不是 META?」就是錯的;
  正確問法是「`catalyst_lifecycle_stage` 是什麼?`market_already_paid` 是什麼?」。

---

## §1 核心不變量(Core Invariants)

每條不變量 = 可觀測條件 + 數值門檻 + 必填欄位 + 必用措辭。這是唯一規範來源。

### INV-1 漏斗紀律(Staged Funnel Discipline)

不得直接跳到 2-3 支。必用分階漏斗,深度逐階加深:

- Stage 1:全 OKX `instCategory=3` live universe,淺掃,每檔恰好出現一次。
- Stage 2:最佳 20 名,中度研究。
- Stage 3:最佳 7 名,深度研究。
- Stage 3.5:對 Stage 3 全員做 OKX 多時框 K 線驗證。
- Final:Stage 3.5 後輸出 0-3 支保守候選,或 no trade。

誠實標記:
- 若 Stage 2 < 20 或 Stage 3 < 7 → 標 `insufficient_candidates: yes`,說明哪些濾網砍掉名額,
  並把整份報告標為 `reduced_funnel`。
- 不得把 `{live_count} → 20 → 7 → 3` 悄悄改寫成 `30 → 15 → 5 → 3`。
- Final 可為 0/1/2/3;單支或零支也合法,但必須完成完整漏斗 + §1 全部稽核。

### INV-2 多時點掃描閘門(Multi-Timepoint Scan Gate)

早盤單一時點不是最終答案。標準時點(ET):

- `early_watchlist_scan`:06:00–07:30。只產 watchlist,**不鎖 final**。
- `first_full_rescan`:08:45,或高影響事件時間 + 15 分鐘。重掃**全 universe**,
  用事件後 / 當前 K 線重算 Signal 1,輸出 `top_8_to_10_candidates`(provisional)。
- `second_confirmation_scan`:09:10。最終盤前確認閘門。
- `market_open`:09:30(命中判定起點)。
- `after 10:30`:predictor 不再給新盤前進場,交給 scanner(`after_10:30_scanner_only`)。

actionability by mode:
- 在 first_full_rescan 前:`preliminary_watchlist_only`。
- first ↔ 09:10 之間:`top_8_to_10_candidates`,非 final。
- 09:10 起:Stage 3.5 + Missed Winner Sweep + Final Review 後才允許 final 0-3。

09:10 確認必查:`direction_persistence`、`volume_acceleration`、`premarket_high_proximity`、
`vwap_midpoint_status`、`qqq_spy_confirmation`、`momentum_leadership_status`。
**08:45 強、09:10 從高點回落者必須降級**,即使第一次掃描看起來很強(盤前衰竭剔除點)。

必用措辭(first_full_rescan 前):
`No final picks yet: key macro / event data is still pending. Produce watchlist only and rerun at {required_first_rescan_time_et}, then confirm at 09:10 ET.`

### INV-3 宏觀資料閘門 + 事件後重置(Macro Data Gate & Reset)

這是「事件前延遲」與「事件後重置」兩件事,分開處理。

**事件前(Gate):** 全部成立時 `macro_data_gate_active: yes`:
- 高影響事件 pending:CPI / PCE / PPI / GDP / NFP / FOMC / 明顯市場級 Fed 事件。
- 事件時間落在開盤前或盤中。
- 前一日相關板塊明顯被壓:板塊 3x ETF / proxy ≤ `-8%`,或 QQQ / 寬基 ≤ `-2%`,
  或 ≥ 3 檔相關名稱明顯翻黑。
- 事件前 Signal 1 弱 / 雜訊 / 被壓。

動作:輸出 `MACRO DATA GATE ACTIVE — NO FINAL PICKS BEFORE DATA`;
Stage 1 照跑(coverage),但用 `macro_pending_watchlist`,**不得 final**;
受影響板塊名稱即使盤前弱也要留在 watchlist;`required_rerun_time_et` 通常為事件公布 + 30 分鐘。

**事件後(Reset):** 把事件前後視為兩個 regime。每筆 Signal 1 標 `pre_event` / `post_event`。
- 事件前 Signal 1 為負,但事件後 30 分內轉 `>= +1.5%`(或 `>= +1.0%` 且屬板塊反彈 bucket)
  → `macro_reset_triggered: yes`,用事件後 K 線重建 Signal 1,原本的事件前 reject 必須 rollback / re-rank。
- 宏觀重置不抹去個股硬負面(降評、指引下修、訴訟、政策風險);個股負面保留。

必填:`macro_event_present/name/time_et`、`pre_event_signal_1`、`post_event_signal_1_30m`、
`macro_reset_triggered`、`post_event_reassessment_result`。
必用措辭:`Macro reset: pre-event weakness was not a final reject; Signal 1 was rebuilt from post-event price action.`

### INV-4 催化劑生命週期與新鮮度(Catalyst Lifecycle & Freshness)

Signal 3 不是「正面標題 = 看多」。先分類生命週期,再判斷市場是否已反應。同一催化不得當兩次新 alpha。

必填(每個 Stage 2+ 催化):`catalyst_lifecycle_stage`(rumor_leak / first_confirmation /
formal_execution / post_reaction_day2 / repeated_headline / binary_event_pending /
binary_event_resolved / analyst_repricing / sector_sympathy / unknown)、
`market_already_paid`、`new_information_delta`、`tradable_edge_remaining`、
`catalyst_first_seen_time`、`same_catalyst_prior_reaction_pct`、`surprise_factor`、
`staleness_penalty`、`buy_the_rumor_sell_the_news_risk`、`prior_reaction_attribution`。

降權門檻(可觀測):
- 同一催化在過去 24h 已推動 `> +2%` → Signal 3 轉中性/偏負(除非有第二個明確新催化)。
- 前一交易日同催化已推 `> +3%` → 今天 0 fresh credit / 至少降一級;若價格同時從高點衰退 → watch_only / reject。
- 今天只是「正式上線 / 正式公布 / 活動開始 / 重複轉載」,市場昨天已知
  → `surprise_factor: none`、`buy_the_rumor_sell_the_news_risk: high`、視為 `formal_execution` 或 `repeated_headline`。
- `new_information_delta: none` → 不論標題多正面,**封頂 MEDIUM**。
- `prior_reaction_attribution: uncertain` → 封頂 `MEDIUM-HIGH` 直到開盤後確認。

歸因檢查:不可假設昨天的漲幅是今天這條催化造成的。比對前日股價、盤後/盤前、首見時間、
同儕/ETF 同窗移動、大盤同窗移動,得 `same_catalyst_confirmed / probable / market_or_sector_move / uncertain`。

必用措辭:`Lifecycle downgrade: this is {stage}; market_already_paid={...}; tradable_edge_remaining={...}.`

### INV-5 硬催化重定價例外(Hard-Catalyst Repricing Exception)

「漲多/延伸」不等於該降階。當 gap 由**硬基本面重定價**驅動時,不得只因 `>= +8%` 就降。

硬重定價催化:財報 `beat_raise`(營收 + EPS + 上調全年/次季指引)、大型新/續約政府或企業合約、
確認新指引的分析師上修/重申、多家獨立機構在報告後確認。

分類:`extension_type: earnings_repricing_gap`、`hard_catalyst_present: yes`、
`gap_extension_penalty_allowed: no, unless live structure or entry gates fail`。

規則:
- 硬重定價 gap 若價格貼近高點、VWAP/midpoint 守住、量能確認、entry gates 過 → 可維持 `HIGH` / `MEDIUM-HIGH`。
- 進場仍需 INV-11 gates;若 +3% 已被吃掉或 R:R 不足 → `prediction_valid_but_no_new_entry`,**不是 REJECT**。
- 若報告混雜、指引弱、從高點衰退、或 R:R < `1.5` → 才可套延伸懲罰。

必用措辭:`Hard catalyst override: this is earnings/guidance repricing, not unsupported extension; rate prediction separately from entry actionability.`

### INV-6 動能領漲例外(Momentum-Leadership Exception)

「延伸」只有在**結構確認轉壞**時才看空,不可因「漲多」自動降階或 REJECT。

維持 `momentum_leadership`(可留 `MEDIUM-HIGH`/`HIGH`)需全部成立:
QQQ/SPY 順風;在/貼近高點未衰退;`1m`/`5m` 為 HH/HL 或 flat-high;價格在 VWAP/midpoint 上方;
量能穩定/增加;且 `remaining_room_pct_to_target_3pct >= +0.8%` 且 `risk_reward_ratio >= 1.5`
(或為開盤後 Strategy C 動能續攻且有明確 stop)。

延伸**才**算看空(任一成立):從高點衰退/失守 VWAP/做 lower highs;`remaining_room < +0.8%`;
`R:R < 1.5`;量能 blowoff/出貨;QQQ/SPY 或直接板塊 ETF 衝突;催化已 stale/已付且無第二催化。
此時才套 INV-11 的 `already_realized` / `fading_premarket` / `hit_by_gap_not_tradeable` / `watch_only`。

動能領漲的正確歸宿通常是 **Strategy C 確認**,而非拒絕。
必用措辭:`Momentum leadership override: extension is supported by risk-on tape and live structure; do not downgrade solely for being up.`

### INV-7 寬論述不可一刀切整組 + 籃子脫鉤(Broad-Thesis Veto Ban & Basket Decoupling)

寬論述(「BTC 弱」「crypto fade」「China headline risk」「板塊昨天弱」)**不可**在未逐檔確認下
否決整組,也不可否決有自身催化的個股。

逐檔確認(reject 前必跑):current vs ref close、day high vs ref close、相對板塊 proxy 強度、
自身催化 vs 寬 proxy 催化、是否脫鉤。

個股催化覆寫:若個股有產品/監管/合作/分析師/公司事件等自身催化,且 current `>= +2%`
或 session high `>= +3%` → `company_specific_catalyst_override: yes`,寬 proxy 弱不得作為主要 reject 理由;
至少進 Stage 2,除非有直接負面 / K 線失敗 / entry-gate 失敗。

Basket 脫鉤檢查(使用寬 proxy 論述時必附矩陣):取 proxy(BTC/QQQ/SOXL/相關因子)與
該題材**所有 live OKX 成員**,算各成員 current / high vs ref。
- 若 ≥ 2 成員 current `>= +2%` 或 high `>= +3%` → `decoupling: yes`,寬論述不得 reject 該組,須 re-run Stage 2。
- `sector_thesis_confidence`:≥ 2 成員牴觸 → `weak`。`weak` 時不得 reject current `>= +2%` 或 high `>= +3%` 的個股。
- Basket 自身強度即 Signal 4:兩檔確認 `+0.5`;三檔以上確認且至少一檔有 fresh 自身催化 `+1.0`。

必用措辭:`Sector thesis override: broad {sector} thesis conflicts with ticker-level strength; rechecking individually.`

### INV-8 失敗記憶有效期(Failure-Memory Shelf-Life)

失敗記憶是「防止重複同一個失敗 setup」的護欄,**不是跨日永久黑名單**。
記憶必須綁定 `memory_date + memory_catalyst_key`,以可觀測的 age 與 pattern 衰減。

必填:`memory_date`、`memory_ticker`、`memory_catalyst_key`、`today_catalyst_key`、
`same_failure_pattern`、`memory_age_trading_days`、`memory_action: apply | weaken | ignore`。

依 age + pattern(可觀測,與是哪隻股票無關):
- `0–1 交易日` 且同催化/同型態 → `apply`(封頂 `MEDIUM-HIGH`,source 弱時 `MEDIUM`;不給盤前買點)。
- `2 交易日` 且相似 setup → `weaken`(最多降一級,當 caution note)。
- `> 2 交易日`,或不同催化/不同 tape/不同 K 線結構 → `ignore`(不得封頂、不得擋 Stage 2,僅 caution)。
- 永不得僅因「前一天失敗過」就 reject。

必用措辭:`Failure memory check: prior failure is {same/different} catalyst; memory action = {apply/weaken/ignore}.`
`memory_action=ignore` 時:`Failure memory expired or different pattern: do not let old failure override today's tape.`

### INV-9 同題材新鮮度排序(Same-Theme Freshness Ranking)

同一題材內,選「今天才動」的,不選「昨天已噴完」的。

必填:`prior_day_move_pct`、`today_current_move_pct`、`today_high_move_pct`、
`current_distance_from_high_pct`、`move_phase`(yesterday_exhausted / today_fresh_mover /
two_day_continuation / laggard_reversal / unknown)、`freshness_rank`。

排序:`today_fresh_mover` > `two_day_continuation`(且仍貼近高點且 R:R 有效) > `laggard_reversal` > `yesterday_exhausted`。
- `today_fresh_mover` 不得因同題材另一檔昨天動過就被打成 `already_priced_in`。
- `yesterday_exhausted` 且 `today_day_high_hit_pct < +3%` 不得贏過通過 K 線/entry gates 的 `today_fresh_mover`。

必用措辭:`Priced-in rotation check: {A} was yesterday's move; {B} is today's fresh mover.`

### INV-10 板塊廣度外溢升級(Sector Breadth Spillover)

板塊全面噴出時,Signal 4 必須**系統性**升級成員,而非把每檔留在孤立 `watch only`。
板塊成員由 §2 動態題材分類取得(**非寫死清單**)。

觸發(任一):同題材 ≥ 3 個 live 成員 session high `>= +3%`;或板塊 ETF/proxy 確認且 ≥ 2 大成員 current `>= +2%`;
或板塊 leader 有硬催化且直接同儕同向。

動作:建 `sector_breadth_upgrade` bucket;合格成員進 Stage 2(除非直接負面/壞 K 線/無 OKX 資料/不可能的 entry gates);
在 Stage 3 比較 leader、最新 fresh mover、最高 beta proxy、laggard。
breadth 本身通常封頂 `MEDIUM-HIGH`;成員有自身硬催化可達 `HIGH`。

板塊反彈/崩跌後反彈(同一機制的子型態):
- 板塊 ETF/proxy 前日 ≤ `-5%`(2x/3x ≤ `-10%`)且今日 ≥ 3 成員站上 `sodUtc0`
  → `sector_rebound_candidate` bucket;前日弱勢不得當純 reject。
- 板塊 proxy 前日 ≤ `-8%` 且今日 macro/QQQ 轉正、個股事件後 Signal 1 `> +1%`
  → 把前日弱勢從 `-1` 懲罰改為 `+0.5` 反彈溢價,`bounce_amplifier: medium/high`,promote 至 Stage 2;
  封頂 `MEDIUM-HIGH`,除非另有直接催化或極強 K 線確認。

### INV-11 預測 vs 可交易性切分(Prediction vs Tradeability Split)

「會不會觸 +3%(相對昨收)」與「現在進場還賺不賺得到」是兩件事。一檔可以 `did_hit_plus_3: yes`
同時 `currently_actionable_long: no`。

每個 Stage 3.5 與 final 必拆:
- `prediction`:觸及 `+3%` vs `reference_close` 的機率與狀態。
- `tradeable_entry`:`candidate_entry_price`、剩餘空間、stop、`reasonable_day_ceiling`、R:R、gate 結果。

跳空消耗閘門:
```text
target_3pct_price = reference_close * 1.03
remaining_room_pct = (target_3pct_price - candidate_entry_price) / candidate_entry_price * 100
```
- `room_sufficient`:`remaining_room_pct >= +2.0%` → 可正常選策略。
- `room_limited`:`+0.8% <= remaining_room_pct < +2.0%` → 只准 Strategy C、半倉、TP1 設為 `target_3pct_price`。
- `already_realized`:`remaining_room_pct < +0.8%` 或現價/開盤已 ≥ `target_3pct_price` → 禁新多單,`tradeable_entry: NONE`。

R:R 硬門檻:
```text
risk_reward_ratio = (reasonable_day_ceiling - candidate_entry_price) / (candidate_entry_price - stop_price)
```
- `risk_reward_ratio` 最低 `1.5`;不足一律不給新倉,即使預測會命中。
- `reasonable_day_ceiling` 用 ATR、前日波幅、盤前延伸、上方阻力、當前 K 線估算;不可假設「從進場價還會再 +3%」。未知則降為 `confirmation_only`/`watch_only`。

跳空命中移除:開盤後 15 分鐘最高價 ≥ `target_3pct_price` → `gap_hit: yes`;無 fresh 第二催化或 R:R < 1.5 → `hit_by_gap_not_tradeable`,移出新多清單(可列「預測命中/不可追」或「管理既有部位」)。

必用措辭:`Gap-consumption gate: prediction may be correct, but the +3% move is already consumed; no new long entry.`

### INV-12 進場時機可執行性(Entry Timing Executability)

final / watch-only actionable / Strategy C 候選都必含可照表執行的 `entry_timing_plan`:
`strategy`(A_aggressive_open / B_pullback / C_momentum_confirmation / wait_only / no_new_entry)、
`current_session_time_et`、`next_decision_time_et`、`valid_entry_window_et`、`trigger_condition`、
`trigger_price`、`limit_price_ceiling`、`stop_price`、`target_3pct_price`、`remaining_room_pct_to_target_3pct`、
`risk_reward_ratio`、`order_type`、`cancel_if`、`do_not_chase_above`、`recheck_if_missed`、
`new_position_action`、`existing_position_action`、`position_size`。任何欄位未知 → `wait_only`/`no_new_entry`,不得編造。

時間窗(ET):
- `09:30–09:35`:僅 Strategy A。需 HIGH、fresh 重磅催化、09:10 確認、無盤前衰竭、無 gap 消耗、R:R ≥ 1.5;`limit_only`,預設不下市價單。
- `09:35–10:00`:僅 Strategy B 回檔。需回踩計畫支撐、守 VWAP/midpoint、未開盤區間失敗。
- `10:00–10:30`:Strategy C 動能確認。需站上開盤區間高/守住、守 VWAP、量能確認、R:R ≥ 1.5。
- `after 10:30`:不再給 fresh 盤前進場 → `after_10:30_scanner_only`。

不追價:每筆必含 `do_not_chase_above`。A:`min(open_price * 1.005, R:R 仍 ≥ 1.5 之最高價)`;
B:回檔區上緣,沒回檔就放棄;C:確認後 opening-range high 上方最多 `+0.5%` 且 R:R 仍 ≥ 1.5。
超過則 `new_position_action: no_new_entry`。

觸發/取消成對:每個 trigger 必有配對 cancel(失守 VWAP、跌回區間兩根 5m、支撐破、第一根 5m 收破開盤/VWAP、同族群或 QQQ 轉弱)。
錯過處理:不自動追高;用新價重算剩餘空間與 R:R;R:R < 1.5 或剩餘 < +0.8% → `missed_entry_no_chase`。
新倉 vs 既有:`new_position_action`(buy/wait/no_new_entry) 與 `existing_position_action`(hold/trim/move_stop/exit) 分開。

必用措辭:`Missed entry rule: do not chase; recalculate R:R from the new price before considering any new plan.`

### INV-13 盤前衰竭與開盤流動性出貨(Pre-Market Exhaustion & Opening Liquidity)

最強盤前候選應在接近開盤時仍在吸籌。太早做高、之後走低者可能已耗盡動能。

盤前衰竭(每個 Stage 3.5 計算 `premarket_high_time_et`、`minutes_from_high_to_open`、
`pullback_from_premarket_high_to_open_pct`、`last_30m_premarket_trend`、`opening_range_failure_risk`):
- 盤前高 > 20 分鐘前形成且最後 20-30 分鐘 lower highs → `pre_market_exhaustion_flag: yes`。
- 盤前高 > 25-30 分鐘前形成、開盤在其下且續跌 → Signal 1 降一級。
- 從盤前高回檔 > `1.0%` 且仍在 VWAP/midpoint 下 → 最高 `confirmation_only`。
- 回檔 > `2.0%` 且 1m/5m lower highs → `fading_premarket` / `already_priced_in`,非 healthy_pullback。
- `pre_market_exhaustion_flag: yes` 不得當開盤追高,需 opening-range / VWAP reclaim。

開盤流動性出貨(大戶等 09:30 流動性出貨給散戶):`open_liquidity_sell_risk`、
`first_5m_open_reaction`、`opening_range_status`、`opening_volume_interpretation`。
- 開盤跌破盤前高 + 失守第一根 5m 低 + 無法 reclaim VWAP/midpoint → `open_liquidity_sell_risk: high`。
- 大幅盤前後第一根 5m 收紅且催化 stale/execution-only → `watch_only`/`reject`。
- high risk 僅在乾淨 reclaim VWAP + 開盤區間高 + 量能後才可 actionable;盤前模式無法觀察時 → `confirmation_only`。

回檔硬門檻:`high_to_current_pullback_pct <= -3%` → 不得 `pre_open_actionable`;
`<= -5%` → 最高 `confirmation_needed`;`<= -8%` → `fading_premarket`/`already_priced_in`/`blowoff_risk`;
現價低於盤前高 `> 5%` 且在 VWAP/midpoint 下 → 不優於 `fading_premarket`。

### INV-14 OKX-only 即時資料 + provider 完整性 + coverage 誠實

即時價格、盤前漲幅、ticker、量能、K 線**只用 OKX public market-data 端點**。
新聞/財報/分析師/宏觀行事曆/公司事件可用 web search。

端點:`/api/v5/public/instruments?instType=SWAP`(filter instCategory==3 & state==live)、
`/api/v5/market/ticker`、`/api/v5/market/candles`、`/api/v5/market/history-candles`。
Stage 3.5 必查 `1m/5m/15m/1h/1d`;若 `15m`/`1h`/`1d` 任一缺 → 最終不得優於 `confirmation_needed`。

憑證:不用 API key 取公開行情(除非被限流);永不讀任何交易所交易密鑰;永不下單;全部視為唯讀。
provider 合規:Stage 3.5 `kline_provider` 必為 `OKX public` 或 `unavailable`。
若用 Binance/Yahoo/StockAnalysis/broker/web 片段/「ticker 推算」當 K 線 → `provider_violation: yes`、
`price_action_verdict: insufficient_data`、`actionability: reject`,並 rollback / no-trade,不得繞過。
OKX 不支援或請求失敗 → `okx_live_data: unavailable`、`kline_data_quality: unavailable`;
可研究新聞但不得 final buy。**legacy 抑制**:任何「Binance-only / Binance 30 / binance_perp_list」僅供歷史比較,不用於即時行情。

coverage 分離計數:`universe_count`、`okx_live_supported_count`、`okx_unavailable_count`、`web_fallback_watch_only_count`。
不得在部分 symbol 無 OKX instrument 時宣稱完整 K 線 coverage;不支援/已下市的波動標的須明列為盲區。

### INV-15 價格欄位語意 + 時間戳一致性(Price-Field Semantics & Timestamp Consistency)

絕不把盤中高/盤前高/session high 當成現價。每筆行情陳述標明欄位:
`current_price`、`current_change_pct`、`session_high`、`session_high_change_pct`、
`high_to_current_pullback_pct`、`timestamp`、`data_window`(premarket/regular/postmarket/24h)。

兩個問題分開答:`did_hit_plus_3`(曾否觸 +3%)與 `currently_actionable_long`(現在還能否做多)。
- 可 `did_hit_plus_3: yes` 且 `currently_actionable_long: no`。
- 「up +X%」中的 X 必為 `current_change_pct`;用高點時寫「session high was +X%」。
- final 必基於 `currently_actionable_long`,不只 `did_hit_plus_3`。

時間戳:盡量用同一 batch 的 OKX 資料;不同來源/時段不得混算;latest candle 與 ticker 時間差大 →
`timestamp_alignment: mixed` 並降一級;對齊未知 → 最終不得優於 `confirmation_needed`。
必用措辭:`{TICKER}: did_hit_plus_3=yes, currently_actionable_long=no. 曾觸 +3% 但已從高點衰退,非追多候選。`

### INV-16 稽核迴路(Rollback / Sweeps / Rejected-Leader / Final-Review)

final 前必跑下列稽核;發現更好/被漏的名稱要顯式 rollback,不得悄悄改 final。

- **Rollback:** Stage 2/3/3.5 發現先前假設錯/過時/被更好資料牴觸 → 輸出 `Rollback Notice`
  (rollback_from_stage / reason / affected_tickers / action_taken),並重列受影響階段。
- **Intraday Hit Sweep:** 對全 universe 算 `day_high_hit_pct = (day_high - ref_close)/ref_close*100`;
  任何 `>= +3%` 但不在 Stage 2 的,必 rollback 或給硬 reject 理由;final pick `< +3%` 而多個被拒名稱 `>= +3%` → 重排。
- **Missed Winner Sweep:** 列 current `>= +2.5%`、session high `>= +3%`、`day_high_hit >= +3%`(即使已衰退)、
  product-line peer、macro-reset 後 Signal 1 > +1.5%、open-premium 仍 > sodUtc0、leveraged ETF > +3%、
  被延伸降階的硬催化、被寬論述拒絕的自身催化、basket ≥ 2 成員強的;與 Stage 2/3/final 對比。
  比 swept 名稱在 current 與 actionability 同時更弱的 final pick 必降級/替換。此 sweep 是補漏,不是追每支綠票。
- **Rejected Leader Challenge:** final 前列 current move / session-high move / 08:45→09:10(或 open→current)
  persistence 三項最強的五檔;任一被拒/watch-only 在兩項上勝過某 final pick → 重開 Stage 3.5,或給硬理由
  (直接負面/壞 K 線/R:R 失敗/gap 已消耗/無 OKX K 線)。
- **Final Review Agent(對抗式紅隊,即使 Stage 3.5 已過仍必跑):** 對每個 final 候選查 19 項完整性:
  live_data / price_semantics / catalyst / source_recency(INV-19:每則來源發布時間在 freshness window 內、非舊文)/
  negative_news / event_calendar / peer_and_market / tradeability /
  momentum_leadership / priced_in_rotation / failure_memory / sector_thesis / coverage / entry_timing /
  output / hard_catalyst_extension / company_specific_override / basket_decoupling / sector_breadth_upgrade。
  verdict:`pass` / `conditional_pass`(只能 confirmation_only) / `fail`(移除→rollback/降級,無人過 → no trade)。
  缺資料不可猜,標記並降一級,最終不得優於 `confirmation_only`。Audit 段必出現在 Final Candidates 之前。

### INV-17 保守無交易優先(Conservative No-Trade Priority)

訊號弱、盤前不明、催化不夠、宏觀風險高、或全部候選 R:R 差時,輸出:
`NO TRADE / NO HIGH-CONVICTION SETUP TODAY`。
不得為填滿模板硬湊 2-3 支。**保守優先於活躍。** 若無任何 Stage 3 名稱達 `HIGH`/`MEDIUM-HIGH`,優先 no trade。

### INV-18 評級語氣與 session 模式(Rating Honesty & Session Gate)

- 永遠帶機率與信心區間。禁止語氣:「今天一定」「保證會漲」「閉眼買」。必帶風險揭露;盈虧自負。
- session gate:`query_time_et < 09:30` → 盤前預測模式;`>= 09:30` → `pre_market_prediction_mode: disabled`、
  `post_open_validation_mode: enabled`,不得用「盤前買點/開盤前會買」語言;final 必拆 `prediction_test_result`
  與 `currently_actionable_long`。盤後查詢改用 scanner(us-stock-mover-scanner)。
- HIGH 評級證據閘門(全部成立):催化具體/新鮮/實質;lifecycle 為 first_confirmation/analyst_repricing/
  實質新的已決事件(非單純 formal_execution/repeated_headline/post_reaction_day2);surprise high/medium;
  new_information_delta material;tradable_edge strong/moderate;同催化前反應未已 > +2%(除非有第二催化);
  source 強/可接受;同儕/ETF 支持;盤前動能穩定非單筆 spike;無同日二元事件主導;負面搜尋無實質牴觸;有合理保守進場與 stop。
- 單一來源 → 最高 `MEDIUM-HIGH`;單一來源且涉 China 政策/出口管制/訴訟/監管/未證實供應鏈 → 最高 `MEDIUM`。
- gap 延伸:盤前 > `+8%` → 最高 `MEDIUM-HIGH`(除非催化品質與同儕確認都強);> `+15%` → 不給盤前買點,只允許開盤後確認。
- 兩日催化鏈:昨天同催化已 > `+3%` → 今天先降一級;若今天盤前從早高衰退 → 最終只能 `confirmation_only`/`watch_only`/`reject`。

### INV-19 來源時效閘門(Source Recency Gate)

這條防的是**和 INV-4 不同**的失誤:INV-4 假設催化日期正確、只判斷市場是否已消化;
INV-19 防的是「**AI 撈到舊報導 / 過時財報,誤當成今天的新消息**」與「**日期算錯去搜了錯誤日期**」。

**日期錨點必須由程式決定:** 先跑 `scripts/clock.py`(§4.1),取得正確的 `trading_day_target`、
`news_search_date`、`yesterday_date`、`freshness_window_start_et`,以及已填好日期的搜尋字串。
AI **不得手算**台北→UTC→ET / 夏令冬令,也不得自行猜測 `{DATE}`(手算 DST 出錯就會搜到舊資料)。

**每一則支持催化的來源必填:** `source_published_at`(該文/該則的實際發布時間)、
`source_recency: fresh | stale_or_undated`、`recency_basis: article_date | scheduled_event_date`。

規則(可觀測):
- 只有 `source_published_at >= freshness_window_start_et`(預設 = `yesterday_date 00:00 ET`,即涵蓋
  昨晚盤後 + 隔夜 + 今晨)的來源,才能算**今天的 fresh catalyst**。
- 無法確認發布時間、或早於視窗 → `source_recency: stale_or_undated`:只能當背景,**不得支持 HIGH**,
  也不得拿來當「今天的新催化」推升評級;若整個 bullish thesis 只靠這種來源 → 最高 `MEDIUM`,且須明寫風險。
- **搜尋查詢一律帶 `news_search_date` / `yesterday_date`**(用 clock.py 吐出的字串);禁止無日期的
  「{TICKER} stock news」這類查詢(會把幾個月前的舊文排在前面)。
- 排程型事件(今日財報 / 經濟數據 / FDA / investor day)例外:以**事件日**判定時效,不以文章發布日判定;
  但仍須確認該事件確實落在 `trading_day_target`(或其盤前/盤後窗),而非過去已發生的同類事件。
- 若同一催化的最新可信來源其實是數日前的舊聞被重新轉載 → 套 INV-4 的 `repeated_headline` / `market_already_paid`。

必用措辭:`Source recency: {fresh|stale_or_undated}; published {source_published_at}; freshness window from {freshness_window_start_et}.`

---

## §2 動態 universe 與題材分類(Dynamic Universe & Theme Classification)

### 2.1 建立 universe(live 優先)

1. 從 OKX live `instCategory=3` instruments 建全 universe(`universe_source: okx_live_instCategory_3`)。
   實作上跑 `scripts/stage1_scan.py`(它同時完成列舉 + Stage 1 數據,見 §3.2)。
2. live 失敗才用靜態 fallback `references/okx_stock_universe.md`(`universe_source: static_fallback`)。
3. universe 大小**以 live 回傳為準,不寫死數字**;`okx_universe_count` 由 live 填。
4. Stage 1 每檔恰好出現一次;final buy 資格需 OKX ticker + K 線;pre-IPO / web-only 可 `watch only`,不可 final buy。
5. 寬基 ETF(SPY/QQQ/IWM/XLE 等)與槓桿 ETF(SOXL 等)必須當 ETF proxy 候選納入,不得默默排除。

### 2.2 題材/板塊分類(動態,範例非窮舉)

**分類是動態的:** 對 live universe 每一檔,依其業務指派一個或多個 `theme_tag`
(例:`mega_cap_ai_cloud`、`semiconductors`、`memory_storage`、`ai_infra_optical`、
`fintech_crypto_adjacent`、`etf_market_proxy`、`leveraged_etf`、`energy`、`biotech`、
`space_defense`、`materials_rare_earth`、`pre_ipo` …)。題材清單與成員都會隨 live universe 變動。

> 範例題材桶(**非窮舉、非封閉**,僅示範分類粒度;新題材爆發時用同一機制動態建桶):
> AI/mega-cap、AI chips/semis、memory/storage、AI infra/optical/data center、
> fintech/crypto-adjacent、ETF/market proxy、pre-IPO、其他高 beta/事件名。
> 完整當期範例見 `references/okx_stock_universe.md` 的 Suggested Buckets,該清單同樣是 fallback 範例。

INV-7/INV-9/INV-10 的 basket、freshness、breadth 計數**一律對「live universe 中帶相同 theme_tag 的成員」計算**,
不得限於任何寫死清單。沒被範例列到的板塊,只要 live 成員觸發門檻,同樣建桶升級。

### 2.3 Product-line read-through(機制 + 範例)

機制(通用):若 A 公司財報/指引重定價了某條產品鏈的近期需求/定價/利潤,則同產品鏈的 B 直接 peer
即使無自身新聞也可能強動。必填 `product_line_group`、`peer_catalyst_source`、`peer_catalyst_strength`、
`read_through_strength`、`direct_product_line_peer`。

評分:直接同產品線 peer 且來源 beat/guide-up 有實質 read-through → Signal 4 至少 `MEDIUM`;
來源大 beat 或上調且 target 盤前 > `+1%` → 可 `MEDIUM-HIGH`;
來源 beat/指引超預期 `> +10%` 或來源股本身 > `+5%` → 直接同產品線 peer 不得 Stage 1 直接刪(除非無 live data 或硬負面)。
AMC 同產品線 read-through:來源 beat 幅度 `> +5%` vs 共識,直接 peer Signal 4 `+1.0`/至少 `MEDIUM`,寬經濟 peer `+0.5`;
來源股自身 `<= -1.5%` 盤前則降一檔,但不歸零(除非指引/反應明顯否定 read-through)。

> read-through 對應由 `theme_tag` + 產品鏈關係動態推導。**範例映射(非窮舉)**:記憶體龍頭 beat → 重查同
> memory/storage 與相關 semis;AI 晶片龍頭 beat / AI capex → 重查 AI chips 與 foundry;雲端 capex 強 → 重查 AI 供應鏈;
> 加密交易/幣價突破 → 重查 fintech/crypto-adjacent。具體個股範例見附錄 A,僅供說明。

---

## §3 執行機制(Operating the Invariants)

操作層只「執行」§1,不重述規則。每個欄位/門檻都對應一條 INV。

### 3.1 強制執行順序

1. 建 live universe(§2.1);失敗用 fallback。
   **Stage 1 的全清單掃描必須先執行 `scripts/stage1_scan.py`**(見 §3.2),
   Stage 1 的價格/漲幅數字只能來自該腳本輸出,不得由模型憑記憶填寫或腦補。
2. 判 `scan_mode`(INV-2)。
3. 判 `macro_data_gate_active`(INV-3)。
4. gate active 且在 first_full_rescan 前 → Stage 1 coverage + `macro_pending_watchlist`,停在 final 前。
5. first_full_rescan → 重掃全 universe,輸出 provisional `top_8_to_10_candidates`。
6. first ↔ 09:10 之間 → 不出 final,指示 09:10 重跑。
7. 09:10 起 → Stage 1/2/3/3.5 + Intraday Hit Sweep + Missed Winner Sweep + Rejected Leader Challenge + Final Review。
8. 輸出 0-3 final 或 no trade。

不得跳過安靜 ticker;不得不列每檔就總結板塊;不列出每列就不得宣稱完整 coverage。

### 3.2 Stage 1:全 universe 淺掃(數據由程式保證,非 AI 自律)

**強制:先跑 `scripts/stage1_scan.py`。** 此腳本用 OKX public API 一次列舉全部 live
`instCategory=3` 標的,並算好每支的 `current_vs_sodUtc0_pct`、`high24h_vs_sodUtc0_pct`、
`high_to_current_pct`、24h 量能。它的存在是為了根治「60+ 支太多 → AI 偷懶或腦補」:
- AI **不得新增、刪除、合併**腳本輸出的任何一列(覆蓋率由程式保證,不是 AI 自己宣稱)。
- Stage 1 的**價格與漲幅數字只能來自腳本**;AI 不得憑記憶或印象填數字。
- 腳本標 `unavailable` 的標的是資料盲區,只能 watch、不得 final buy,也不得假裝有數據。
- 腳本失敗(`universe_source: UNAVAILABLE`)才改用 `references/okx_stock_universe.md`
  靜態 fallback,並明確標 `static_fallback`;同樣不得腦補數字。
- 注意 `high24h` 含前一日,只是 session high 的粗略代理;真正盤前/盤中 session high 需對
  漏斗存活者(20→7)另抓 candles 驗證(INV-15)。

AI 在腳本輸出的真實數據上,補完每檔的判斷欄(catalyst/sector/decision 等)。完整列(含判斷欄):
`# | Ticker | OKX instId | OKX live data | sodUtc0/prev close | Current price |
Current vs sodUtc0 % | Session high vs sodUtc0 % | Catalyst found? | Sector/product-line impulse |
Macro gate/reset | Earnings premium | ETF proxy | Reversal bucket | Initial risk | Stage 1 score | Stage 1 decision`。

規則:每檔算 `current_vs_sodUtc0_pct` 與 `session_high_vs_sodUtc0_pct`(不只看 24h);
current `>= +2%` 不得無理由 reject;session high `>= +3%` 不得消失(標 hit_but_faded/watch/advance/reject + 理由);
decision 用 advance/watch only/reject;選 20 advance(不足則說明);
保留 ≥ 3 個名額給 `sector_rebound_candidate`/`reversal_bucket`(INV-10);
gate active 時用 `macro_pending_watchlist`(INV-3);槓桿 ETF Signal 1 > +3% 須納入或明確以 K 線/風險理由拒絕。

### 3.3 Stage 2:Top 20 中度研究

**數據面先跑 `scripts/sweep_breadth.py`**:它從 OKX 算好漲幅榜、Missed Winner / Intraday Hit
Sweep 候選清單(current ≥ +2.5% / high ≥ +3%)、以及各題材 breadth / basket decoupling 成員計數
(INV-7 / INV-10 / INV-16)。AI 不得遺漏腳本列出的任何 sweep 候選,也不得在 decoupling=YES 時
用寬論述整組 reject。**催化、新聞、lifecycle、負面搜尋等判讀仍由 AI 做**(腳本不碰)。

每檔一列含(對應 INV):Ticker、instId、live data、current/high vs sodUtc0、prior day move、`move_phase`(INV-9)、
Catalyst、`Lifecycle`(INV-4)、Freshness/surprise、Product-line peer(§2.3)、Sector rebound/breadth(INV-10)、
`Sector thesis confidence`(INV-7)、Macro reset(INV-3)、Earnings open premium、ETF proxy、Reversal bucket、
`Momentum leadership`(INV-6)、Same-tier rank、`Failure memory action`(INV-8)、Prior same-catalyst reaction(INV-4)、
Source depth、Negative search、Peer/ETF confirmation、Event risk、Tradeability、Score、Decision。
選 7 advance(不足則說明);每個 advance 必附「為何贏過次佳被拒/watch 名稱」。

### 3.4 Stage 3:Top 7 深度研究

對每檔輸出 Markdown 子段,涵蓋:current_move + `momentum_leadership_status` + `extension_interpretation`(INV-6);
catalyst_quality + `hard_catalyst_present`/`extension_type`/`gap_extension_penalty_allowed`/
`company_specific_catalyst_override`(INV-5/7) + 完整 lifecycle 欄位(INV-4)
+ 每則來源的 `source_published_at`/`source_recency`/`recency_basis`(INV-19);
move_phase + freshness(INV-9);negative_search;peer_confirmation + `basket_proxy_decoupling`/breadth(INV-7/10);
`failure_memory_check` 全欄位(INV-8);product_line_peer_check(§2.3);macro_event_signal_reset(INV-3);
post_earnings_open_premium;leveraged_etf_proxy_check;reversal_bucket;earnings_and_event_risk;
technical_and_tradeability + `remaining_room_pct_to_target_3pct`/`risk_reward_ratio`/`extension_penalty`(INV-6/11);
bear_case / why_it_can_still_work / confirmation_needed / invalid_if;`stage_3_decision`。

### 3.5 Stage 3.5:OKX 多時框 K 線驗證(Stage 3 全員,final 前必做)

**強制:先跑 `scripts/stage35_kline.py {7 支 ticker}`。** 此腳本對每支抓 OKX `1m/5m/15m/1h/1d`
真實 K 線,算好 price_semantics(reference_close/target_3pct/current/day_high/`did_hit_plus_3`/
high_to_current_pullback)、各時框結構與量能啟發式標籤、timestamp_alignment、缺時框上限。
- K 線數字、結構、量能、did_hit_plus_3 **只能來自腳本**;AI 不得編造或修改。
- 結構/量能標籤是**客觀啟發式輸入**,AI 仍須結合催化、VWAP、R:R 做最終 verdict(非腳本決定)。
- 任一時框 `unavailable`(尤其 15m/1h/1d)→ 最終不得優於 `confirmation_needed`(腳本會標 cap)。
- `okx_live_data: unavailable` 的標的不得 final buy,不得腦補。

資料:`1m/5m/15m/1h/1d` + 現價 + 盤前高/時間/低 + 近似 VWAP/midpoint + 距高 + 最後 20-30 分盤前趨勢 + 量能。
輸出涵蓋:session_mode、kline_provider/provider_violation(INV-14)、timestamp_alignment(INV-15)、
price_semantics(reference_close/target_3pct_price/current/session_high/pullback/`did_hit_plus_3`/`gap_hit`/
`currently_actionable_long`,INV-15)、multi_timeframe_structure(INV-13:exhaustion/opening_range_failure/
1m/5m/15m/1h/1d 結構/volume)、priced_in_filter(INV-9/11:move_phase/freshness/`gap_consumption_status`/
`risk_reward_ratio`/`risk_reward_gate`/`tradeable_entry`/entry_timing 全欄位/lifecycle/hard_catalyst/decoupling/breadth)、
opening_liquidity_check(INV-13)、`price_action_verdict`、`actionability`、`prediction_test_result`、
required_confirmation_after_open、invalid_if。

verdict 規範:
- `continuation_confirmed`(可 final):守 VWAP/midpoint;1m/5m/15m 非看空且 ≥ 2 個 HH/HL;1h 非 topping/深延伸;
  1d 未過度延伸入阻力;量能確認;peer/basket 支持;surprise≠none;tradable_edge≠weak/none;
  無 `pre_market_exhaustion_flag`;有盤後資料時 `open_liquidity_sell_risk`≠high;延伸時 `extension_interpretation`=momentum_leadership;
  INV-11 gates 過(剩餘空間未消耗、R:R ≥ 1.5)。
- `healthy_pullback`(需開盤後 reclaim 確認才可 final):回檔守支撐、量縮、reclaim VWAP 或做高低點、15m 非 LH/LL、1h/1d 無高延伸風險、催化夠新。
- `confirmation_needed` / `already_priced_in` / `already_realized` / `hit_by_gap_not_tradeable` /
  `fading_premarket` / `blowoff_risk` / `insufficient_data`:依 INV-4/6/9/11/13 條件判定,**皆不得 final buy**。
- 盤前買點只在 `continuation_confirmed` 允許;`healthy_pullback` 需開盤後 reclaim/hold。
- 硬失敗門檻彙總(全部對應上述 INV,逐一執行):session_high ≥ +3% 但 current < +3% 標 did_hit 不稱 +3% gain;
  `remaining_room < +0.8%`→already_realized+NONE;`R:R < 1.5`→fail+NONE;缺 entry_timing 的 final→降 watch_only;
  價超 `do_not_chase_above`→no_new_entry;窗已過→missed_entry_no_chase;`gap_hit` 無第二催化→hit_by_gap/already_realized/watch;
  momentum leader 不得標 bearish_extension 除非顯示具體看空結構;`move_phase=today_fresh_mover` 不因他股昨日動而打 priced_in;
  `failure_memory_action=apply` 需同催化同型態;`sector_thesis_confidence=weak` 不得拒 current≥+2%/high≥+3%;
  無 OKX data→排除 final;`high_to_current_pullback` -3%/-5%/-8% 門檻(INV-13);`pre_market_exhaustion_flag`/
  `open_liquidity_sell_risk=high`→不得追/watch;single source / gap >+8%/>+15% / 兩日催化鏈(INV-18)。

### 3.6 輸出格式(final 報告骨架)

依序輸出:Scan Mode/Timing Gate → Macro Data Gate → First Full Rescan → Second Confirmation Scan →
Hit vs Actionability Summary → Intraday Hit Sweep → Missed Winner Sweep → Rejected Leader Challenge →
Final Review Agent Audit → Final Candidates(僅 `final_picks_allowed_now: yes` 時)→ Single-Pick/Thin-Candidate Audit → No-Trade Condition。

Final Candidates 每支(Pick)必含:probability_band、stage_3_5_verdict、actionability、current/session_high/pullback、
`did_hit_plus_3`、target_3pct_price、`gap_hit`、`currently_actionable_long`、move_phase、failure_memory_action、
sector_thesis_confidence、prediction(touch_plus_3_probability/prediction_status)、tradeable_entry(全 INV-11 欄位)、
entry_timing_plan(全 INV-12 欄位)、why_it_qualified、risk_reasons、conservative_entry_plan、invalid_if。

`final_candidate_count` 為 0 或 1,或 Stage 2 < 20 / Stage 3 < 7 時,必出 Single-Pick/Thin-Candidate Audit
(single_pick_reason / why_not_two_or_three / funnel_status / stage 計數 / 至少前五被拒替代方案表)。

定稿前自查(全部對應 INV):scan mode 顯式;`final_picks_allowed_now: no` 時無 Final Candidates;
macro gate 前只 watchlist;first↔09:10 標 provisional;每檔在 Stage 1 恰一次;Stage 2/3 只含上階晉級(除非 rollback);
Stage 3.5 含全 Stage 3 與五時框或標 unavailable;兩個 Sweep 與 Final Review 在 Final Candidates 前;
day_high ≥ +3% 者皆 Stage 2+ 研究/rollback/硬 reject;同題材含 move_phase 且不讓 exhausted 贏 fresh;
failure memory 含 date/key/age/action 且非永久黑名單;寬論述 reject 經逐檔與脫鉤檢查;coverage 三分離;
current > +2.5% 或 hit +3% 者皆已研究/rechecked;板塊反彈在 ≥ 3 綠時檢查;每 final 有 Final Review pass/conditional_pass;
provider_violation: no 且 kline_provider: OKX public;盤中查詢用 regular_session_validation;
no sentence 用 session high 當 current;final 含 target/room/gap_consumption/ceiling/R:R/gate 且過門檻;
final 含完整 entry_timing_plan;不在窗內不得「buy now」;gap_hit 無第二催化標 hit_by_gap_not_tradeable;
同分競爭出 Same-Tier Structural Tiebreaker;不得僅因延伸 reject momentum leader;
final 排除 already_priced_in/fading_premarket/blowoff_risk/confirmation_needed/insufficient_data;
無 HIGH/MEDIUM-HIGH 時優先 no trade(INV-17)。

---

## §4 訊號矩陣、機率分級與進場(User-Facing Layer)

**核心理念:預測 ≠ 統整。預測給機率,不給保證。**(INV-18)

### 4.1 Phase 0:時間意識

```
台灣 19:00–21:00 (UTC+8) → UTC 11:00–13:00 → ET 夏令 07:00–09:00(主場景) / 冬令 06:00–08:00
```
美股關鍵時點(ET):04:00 盤前開始;08:30 常見經濟數據;09:30 開盤(命中起點);16:00 收盤(命中終點)。
命中視窗 09:30–16:00 ET = 台北 21:30 至次日 04:00。

**強制先跑 `scripts/clock.py`** 取得時間錨點:它把台北→UTC→ET(自動處理夏令/冬令)、
`minutes_until_open`、`trading_day_target`、`news_search_date`、`yesterday_date`、
`freshness_window_start_et` 算死,並吐出**已填好正確日期的搜尋字串**。AI 不得手算日期或自猜
`{DATE}`(手算 DST 出錯 → 搜到錯誤日期 → 撈到舊資料,正是 INV-19 要防的)。

每份報告開頭必輸出 `[PREDICTION_TIME_CONTEXT]`(query_time_local/et、minutes_until_open、
trading_day_target、session_now、news_search_date、prediction_window),數值取自 clock.py。

特殊情境:盤中(台北 21:00–04:00)→ 轉 scanner;盤後 → 看是否已有財報結果;週末 → 預測週一但訊號鮮度差需告知。
Web search 一律用 clock.py 吐出的**已填日期**字串(premarket movers {news_search_date}、
earnings after the close {yesterday_date} 等);禁止無日期查詢(如「{TICKER} stock news」,會把舊文排前面);
不搜「stock price today」(尚未發生)。每則來源須核對發布時間並標 `source_recency`(INV-19)。

### 4.2 六大訊號(可預測性由高到低)

| # | 訊號 | 取得 | 主要 INV |
|---|------|------|---------|
| 1 | 盤前異動 ≥ +2% | OKX 24h chg + web 盤前報價 | INV-15(欄位語意) |
| 2 | 昨晚盤後/今早盤前財報 | web earnings calendar | INV-5 / INV-18(BMO pending) |
| 3 | 隔夜重大消息 | web search 含時區 | INV-4(新鮮度) |
| 4 | 同類股延伸動能 / product-line | OKX + §2.3 | INV-9 / INV-10 |
| 5 | 技術臨界突破 | OKX 指標 | — |
| 6 | 今日經濟事件 / Fed | web calendar | INV-3 |

⚠️ OKX 24h chg 含「昨日全天 + 昨晚盤後 + 今晨盤前」,**不是今早盤前漲幅**;盤前漲幅另查 web(INV-15)。
訊號 1:盤前 ≥ +2% high / ≥ +1% medium / < +1% 無觸發。訊號 5:距 20D 高 ≤ 2% + RSI 50-70 → medium-high;
RSI > 80 負分降階;流動性差(OKX 24h vol < $5M)降階。訊號 6 為全市場層級,high-impact 事件 → 個股信心降一階(並見 INV-3)。

### 4.3 機率分級

| 等級 | 條件 | 經驗命中率 |
|------|------|------|
| HIGH | 任一強訊號組合(4.3.1) | ~60-75% |
| MEDIUM-HIGH | 訊號 1 ≥ +1% AND ≥ 1 其他訊號 | ~40-50% |
| MEDIUM | 1-2 訊號但盤前未顯著啟動 | ~25-35% |
| LOW | 僅 1 弱訊號 / 技術 only | ~10-20% |
| 無觸發 | 全未觸發 | <10%(基準率 8-12%) |

#### 4.3.1 強訊號組合(任一觸發即 HIGH)
- **A 盤前已啟動:** 訊號 1 ≥ +2%(觸 +3% 僅剩 1% 路程)。
- **B 重磅催化:** sell-side 目標價單次 +50%+ 上修 / 同日 ≥ 2 家頂級券商升評同檔 /
  今早 BMO 財報已公布且 beat+指引上調(等公布,別搶跑) / 昨晚 AMC beat + 重大合約/收購 /
  重大產品突破(新藥批准、製程突破、大型政府合約)。
- **C 雙訊號疊加:** 訊號 1(+1.5%+) AND 訊號 3(任一隔夜利多)。
- **D 同類股強烈擴散:** 昨日同題材龍頭 ≥ +15% AND 本檔昨日 < 龍頭一半 AND 盤前已 +1%(INV-9/INV-10)。

> HIGH 的目的是「抓到強訊號」,不是「保守不漏判」。寧可 3 個 HIGH 命中 2 個,也不要全標 MEDIUM 無法行動。

#### 4.3.2 機率降階
**強制降 LOW(無條件淘汰,即使其他訊號強):**
- 訊號 1 反向(盤前 ≤ -1%):市場已用真金白銀否決故事,權重大於任何基本面催化。
  例外:高影響 macro pending / 事件後 Signal Reset(INV-3)/ 盤後開盤溢價 / 盤前流動性不足消化 → 不可直接淘汰,
  放 `reversal_bucket` 等 08:45/09:10 重評;若 OKX K 線顯示重新站回 `sodUtc0` 且 current ≥ +1.5% 或 high ≥ +3% → rollback。
- 同類股大跌:QQQ 盤前 ≤ -2% 且個股已跟跌 → 淘汰。

**降一階:** 訊號 6 high-impact 且結果未知;RSI > 80;訊號 2 為 BMO 未公布(標 `event_pending`,不可 HIGH);
流動性差;昨收跌破 50 日均線。**升一階:** 訊號 1+2+3 全觸發;隔夜 sell-side 重磅上修(目標價 +50%+)。

> 延伸/籃子/失敗記憶相關的降升,一律以 INV-5/6/7/8 為準(可觀測條件,非個股),不在此重述。

### 4.4 進場策略(skill 主動指定,不讓使用者三選一)

先過 INV-11 跳空消耗閘門與 R:R 硬門檻,再依訊號強度指定單一策略(詳見 `references/entry_exit_playbook.md`):

| 訊號狀況 | 推薦策略 |
|---------|---------|
| HIGH + 盤前 ≥ +3% + 重磅催化 | 🅰️ 追高(0-5 分,limit 上限 open×1.005) |
| HIGH + 盤前 +1%~+3% | 🅱️ 回檔(5-30 分,prev_close×1.005~1.015) |
| HIGH + 盤前 < +1%(催化待釋放) | 🅲️ 動能確認(30-60 分,站上開盤 30m 高 + 量能) |
| MEDIUM-HIGH | 🅲️ 動能確認 |
| MEDIUM | 🅲️ 動能確認 + 半倉 |

出場(三層階梯):TP1 entry×1.03 出 50%、TP2 entry×1.05 出 30%、TP3 移動停利出 20%;
Hard Stop entry×0.98(-2%);時間停利 11:00 出 1/3、14:00 出 1/2、15:30 全出。
槓桿 ETF:預設半倉、TP1 提前 +2%、不做 🅱️、失守 VWAP 或回落 -3% 不追、明寫 ETF leverage risk(INV-10 / INV-14)。

### 4.5 最終輸出 Pick 模板(用 §3.6 骨架,加使用者層欄位)

每支 Pick 在 §3.6 必填欄位外,附:訊號明細(signal_1~6 active)、catalyst summary(3-5 句)、
進場計畫(三策略說明 + 本標的單一推薦 + 理由)、出場計畫(TP/Stop/時間停利)、
規避條件(開盤 30 分未站上 prev_close×1.02 / BMO miss / QQQ 開盤 -1%+ / 個股特定)、
雙模式部位計算(現貨 $1000、OKX 永續 $100 3x;新手 ≤ 3x;含 funding rate 提醒)。

報告尾 `[PREDICTION_HONESTY_CHECK]`:coverage(checked/universe,以 live 為準)、prediction_quality、
strongest_pick_probability、data_freshness、disclaimer(預測 ≠ 保證,HIGH 仍有 30-40% 失敗率,盈虧自負)。

---

## 反例(不要這樣做)

- ❌ 拿 OKX 24h chg 直接當「盤前漲幅」(INV-15)。
- ❌ 訊號 1 未啟動就給 HIGH;BMO 未公布就給 HIGH(INV-18)。
- ❌ 忽略今日 FOMC/CPI(INV-3)。
- ❌ 「今天 X 一定漲」語氣(INV-18)。
- ❌ 盤後查詢還用本 skill(改 scanner,INV-18)。
- ❌ **把某個股/某日期當成規則觸發條件**(§0)— 永遠改用可觀測條件 + INV 編號。
- ❌ **依賴寫死的板塊個股清單**(§0.2 / §2.2)— 永遠對 live universe 動態分類。

## 與統整版(us-stock-mover-scanner)的差異

| | scanner(統整) | predictor(本檔) |
|--|---|---|
| 使用時段 | 任何(主要盤後) | 開盤前 30-90 分鐘 |
| 主問題 | 過去 24h 誰漲了 3%+ | 待會兒誰會漲 3%+ |
| 數據 | OKX 已實現 chg | 盤前異動 + 行事曆 + 隔夜消息 |
| 結論 | 高信心(已發生) | 機率分級(尚未發生) |

## Scripts / References 索引

- `scripts/clock.py` — **時間/新聞時效錨點**(離線,免網路)。把台北→UTC→ET(夏令/冬令自動)、
  trading_day_target、news_search_date、yesterday_date、freshness_window、已填日期的搜尋字串算死。
  Phase 0 必先跑。用法:`python3 scripts/clock.py`(或 `--utc ...` 測試 / `--json`)。對應 INV-19。
- `scripts/stage1_scan.py` — **Stage 1 全清單掃描器**(程式保證覆蓋率與數字真實性)。
  一次列舉全部 live `instCategory=3` 標的並算好 current/high/量能;Stage 1 必先跑此腳本。
  用法:`python3 scripts/stage1_scan.py`(markdown)或 `--json`。僅用 OKX public API,免 key,唯讀。
- `scripts/stage35_kline.py` — **Stage 3.5 多時框 K 線抓取器**(數字真實性由程式保證)。
  對漏斗存活的 7 支抓 OKX `1m/5m/15m/1h/1d`,算好 price_semantics / 結構 / 量能 / 時間戳對齊;
  Stage 3.5 必先跑此腳本。用法:`python3 scripts/stage35_kline.py NVDA MU SOXL`(或 `--json`)。
- `scripts/sweep_breadth.py` — **漲幅榜 + Sweep + 板塊 breadth/decoupling 計數器**(INV-7/INV-10/INV-16)。
  程式列舉 Missed Winner / Intraday Hit Sweep 候選與各題材成員計數,防止 AI 漏算或一刀切。
  Stage 2 數據面 + 兩個 Sweep 必跑。用法:`python3 scripts/sweep_breadth.py`(或 `--json` / `--top N`)。
  注意:theme 分組為 references 範例的輔助計數(非權威),untagged 標的 AI 須動態分類。
- `references/okx_stock_universe.md` — OKX `instCategory=3` 靜態 **fallback** 範例(live 優先;清單與題材桶皆非封閉)。
- `references/premarket_signals.md` — 六大訊號搜尋手冊與隔夜消息模板(規則以 §1 INV-* 為準)。
- `references/entry_exit_playbook.md` — 進出場執行手冊(三策略、停損、雙模式部位)。

---

## 附錄 A:校準案例(**非規範,僅供說明**)

⚠️ **以下每個案例都不是規則,不是觸發條件。** 它們只示範「對應的 INV 在真實盤面長什麼樣」。
判斷現場標的時,**只看該 INV 的可觀測條件**(catalyst lifecycle、結構、R:R、decoupling 計數、move_phase…),
**與是哪一隻股票、哪一個日期完全無關**。若某案例顯示某條 INV 門檻不準,調整那條 INV 的門檻即可,
不要新增以個股/日期為錨的規則(§0.3)。

| 案例 | 對應 INV | 它示範的可觀測型態(規則的真正內容) |
|------|---------|-----------------------------------|
| 強訊號標的盤前 +6%+ 且券商目標價巨幅上修 | INV-18 §4.3.1 A+B | 訊號 1 ≥ +2% 疊加重磅 sell-side 上修 → HIGH;不是「因為是某記憶體股」。 |
| 財報 beat 但盤前已反向 ≤ -1% | §4.3.2 強制降 LOW | 盤前反向 = 市場用錢否決,權重 > 基本面;除非 INV-3 事件/流動性例外。 |
| 財報 beat_raise + 合約/機構確認、開盤後仍貼高 | INV-5 / INV-6 | `earnings_repricing_gap` + `hard_catalyst_present` → 不因 +8% 自動降;進場用 R:R 決定。 |
| 加密相鄰籃子多檔走強而 BTC 持平/偏弱 | INV-7 | basket decoupling:≥ 2 成員 current ≥ +2% / high ≥ +3% → 寬論述不得整組砍。 |
| 舊單一 China/單一新聞失敗,兩天後同股隨板塊 beta 上攻 | INV-8 | `memory_age > 2 交易日` 且不同催化/tape → `ignore`;不得永久黑名單。 |
| 同題材昨日主升段已完成 vs 今日另一檔才剛發動貼高 | INV-9 | `today_fresh_mover` 排序高於 `yesterday_exhausted`。 |
| 前一日板塊崩跌,隔日 macro 轉正多檔同步站回 sodUtc0 | INV-10 | breadth/反彈 bucket;`bounce_amplifier`;前日弱勢不當純 reject。 |
| 已知消息「正式上線」當天,前一日測試消息已推 +3%+,盤前高過早形成後回落 | INV-4 / INV-13 | `formal_execution` + `market_already_paid` + 盤前衰竭 → 降權禁追,等開盤後確認。 |
| 盤前僅小漲的 AMC beat_raise,開盤放量上攻 | INV-2 / INV-11 | `open_premium_candidate`,Strategy C 等 10:00-10:30 確認;regular-session liquidity premium。 |
| 事件前(PCE 等)為負、事件後 30 分轉 +2% | INV-3 | `macro_reset_triggered` → 用事件後 K 線重建 Signal 1,rollback 事件前 reject。 |
| 3x 板塊 ETF 盤前 > +3% 且板塊 breadth 支持 | INV-10 / INV-14 | 不因 ETF 身分排除;半倉、TP1 +2%、A/C 不 B。 |

> product-line read-through 的具體個股映射範例見 `references/premarket_signals.md`,同樣**非窮舉、非規範**;
> 實際 read-through 由 §2.3 機制 + live universe 的 `theme_tag` 動態推導。
