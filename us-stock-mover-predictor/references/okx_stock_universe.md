# OKX Stock-Token / TradFi SWAP Universe

Primary universe source for `us-stock-mover-predictor` v9.7+.

Use OKX public instruments first:

```text
GET https://www.okx.com/api/v5/public/instruments?instType=SWAP
filter: instCategory == "3" and state == "live"
```

If live discovery fails, use this static fallback. Snapshot time:
2026-05-29, OKX public instruments returned 62 live `instCategory=3` SWAPs.

Do not fall back to the old Binance 30-name list unless the user explicitly asks
for a legacy comparison.

## Coverage Rules

- `universe_source: okx_live_instCategory_3` when live discovery succeeds.
- `universe_source: static_fallback` when using this file.
- Every listed instrument must appear exactly once in Stage 1.
- Final buy eligibility requires OKX public ticker and OKX K-lines.
- `pre_market` ruleType names are lower-comparability / lower-liquidity and
  should usually be capped unless K-lines and news are unusually strong.
- Unknown or ambiguous stock-token identities require a quick web/news identity
  check before Stage 2 scoring.

## Current OKX Universe Snapshot

| # | Ticker | OKX instId | ruleType | Sector bucket | Notes |
|---:|---|---|---|---|---|
| 1 | AAOI | AAOI-USDT-SWAP | normal | Optical / AI infrastructure | Applied Optoelectronics; high beta |
| 2 | AAPL | AAPL-USDT-SWAP | normal | Mega-cap tech | Apple |
| 3 | AMAT | AMAT-USDT-SWAP | normal | Semicap equipment | Applied Materials |
| 4 | AMD | AMD-USDT-SWAP | normal | Semiconductors / AI | AMD |
| 5 | AMZN | AMZN-USDT-SWAP | normal | Mega-cap tech / cloud | Amazon |
| 6 | ANTHROPIC | ANTHROPIC-USDT-SWAP | pre_market | Pre-IPO AI | Lower comparability; verify news |
| 7 | ARM | ARM-USDT-SWAP | normal | Semiconductors / IP | Arm Holdings |
| 8 | AVGO | AVGO-USDT-SWAP | normal | Semiconductors / AI | Broadcom |
| 9 | BE | BE-USDT-SWAP | normal | Energy / fuel cells | Bloom Energy |
| 10 | BMNR | BMNR-USDT-SWAP | normal | Crypto treasury / high beta | Verify catalyst; high beta |
| 11 | CBRS | CBRS-USDT-SWAP | normal | Crypto-adjacent / high beta | Verify identity and liquidity |
| 12 | COHR | COHR-USDT-SWAP | normal | Optical / AI infrastructure | Coherent |
| 13 | COIN | COIN-USDT-SWAP | normal | Crypto exchange | Coinbase |
| 14 | COST | COST-USDT-SWAP | normal | Consumer staples / retail | Costco |
| 15 | CRCL | CRCL-USDT-SWAP | normal | Stablecoin / crypto-adjacent | Circle |
| 16 | CRWD | CRWD-USDT-SWAP | normal | Cybersecurity | CrowdStrike |
| 17 | CRWV | CRWV-USDT-SWAP | normal | AI cloud infrastructure | CoreWeave |
| 18 | CSCO | CSCO-USDT-SWAP | normal | Networking | Cisco |
| 19 | DELL | DELL-USDT-SWAP | normal | AI servers / hardware | Dell |
| 20 | DRAM | DRAM-USDT-SWAP | normal | Memory / thematic | Verify identity before scoring |
| 21 | EWJ | EWJ-USDT-SWAP | normal | ETF / Japan | iShares MSCI Japan ETF proxy |
| 22 | EWY | EWY-USDT-SWAP | normal | ETF / Korea | iShares MSCI Korea ETF proxy |
| 23 | GEV | GEV-USDT-SWAP | normal | Energy infrastructure | GE Vernova |
| 24 | GLW | GLW-USDT-SWAP | normal | Glass / optical supply chain | Corning |
| 25 | GME | GME-USDT-SWAP | normal | Meme / retail high beta | GameStop |
| 26 | GOOGL | GOOGL-USDT-SWAP | normal | Mega-cap tech / AI | Alphabet |
| 27 | HIMS | HIMS-USDT-SWAP | normal | Digital health | Hims & Hers |
| 28 | HOOD | HOOD-USDT-SWAP | normal | Fintech / crypto-adjacent | Robinhood |
| 29 | IBM | IBM-USDT-SWAP | normal | Enterprise tech / AI | IBM |
| 30 | INFQ | INFQ-USDT-SWAP | normal | AI / pre-IPO or thematic | Verify identity before scoring |
| 31 | INTC | INTC-USDT-SWAP | normal | Semiconductors | Intel |
| 32 | IWM | IWM-USDT-SWAP | normal | ETF / small caps | Russell 2000 ETF proxy |
| 33 | LITE | LITE-USDT-SWAP | normal | Optical / semiconductors | Lumentum |
| 34 | LLY | LLY-USDT-SWAP | normal | Pharma / obesity | Eli Lilly |
| 35 | META | META-USDT-SWAP | normal | Mega-cap tech / AI | Meta |
| 36 | MRVL | MRVL-USDT-SWAP | normal | Semiconductors / data center | Marvell |
| 37 | MSFT | MSFT-USDT-SWAP | normal | Mega-cap tech / cloud | Microsoft |
| 38 | MSTR | MSTR-USDT-SWAP | normal | BTC proxy / software | Strategy |
| 39 | MU | MU-USDT-SWAP | normal | Memory / HBM | Micron |
| 40 | NBIS | NBIS-USDT-SWAP | normal | AI cloud / infrastructure | Nebius |
| 41 | NFLX | NFLX-USDT-SWAP | normal | Streaming / media | Netflix |
| 42 | NOK | NOK-USDT-SWAP | normal | Telecom equipment | Nokia |
| 43 | NVDA | NVDA-USDT-SWAP | normal | AI chips | Nvidia |
| 44 | OPENAI | OPENAI-USDT-SWAP | pre_market | Pre-IPO AI | Lower comparability; verify news |
| 45 | ORCL | ORCL-USDT-SWAP | normal | Cloud / AI infrastructure | Oracle |
| 46 | PLTR | PLTR-USDT-SWAP | normal | AI / defense software | Palantir |
| 47 | QCOM | QCOM-USDT-SWAP | normal | Semiconductors / mobile | Qualcomm |
| 48 | QQQ | QQQ-USDT-SWAP | normal | ETF / Nasdaq 100 | Market proxy |
| 49 | RKLB | RKLB-USDT-SWAP | normal | Space / defense | Rocket Lab |
| 50 | SHLD | SHLD-USDT-SWAP | normal | Defense / AI thematic | Verify identity before scoring |
| 51 | SNDK | SNDK-USDT-SWAP | normal | Storage / memory | SanDisk |
| 52 | SOXL | SOXL-USDT-SWAP | normal | Leveraged ETF / semis | 3x semiconductor proxy |
| 53 | SPACEX | SPACEX-USDT-SWAP | pre_market | Pre-IPO space | Lower comparability; verify news |
| 54 | SPY | SPY-USDT-SWAP | normal | ETF / S&P 500 | Market proxy |
| 55 | TSLA | TSLA-USDT-SWAP | normal | EV / mega-cap tech | Tesla |
| 56 | TSM | TSM-USDT-SWAP | normal | Semiconductors / foundry | TSMC ADR proxy |
| 57 | URNM | URNM-USDT-SWAP | normal | ETF / uranium | Uranium ETF proxy |
| 58 | USAR | USAR-USDT-SWAP | normal | Rare earth / materials | USA Rare Earth |
| 59 | USO | USO-USDT-SWAP | normal | ETF / oil | Oil ETF proxy |
| 60 | VRT | VRT-USDT-SWAP | normal | AI data center power/cooling | Vertiv |
| 61 | WDC | WDC-USDT-SWAP | normal | Storage / memory | Western Digital |
| 62 | XLE | XLE-USDT-SWAP | normal | ETF / energy | Energy sector ETF proxy |

## Suggested Sector Buckets (`theme_tag` 範例 — 非窮舉、非封閉)

> ⚠️ 這是 **fallback 快照範例**,只示範 `theme_tag` 分類粒度。實際分類一律對 **live OKX
> universe** 動態指派(見 `SKILL.md §2.2`);新進 universe 的標的、或沒被列到的新題材
> (核能、量子、生技、稀土 …),都用同一機制動態建桶,**不得把下列清單當成封閉名單**。

- AI / mega-cap tech: AAPL, AMZN, GOOGL, META, MSFT, NFLX, ORCL, IBM
- AI chips / semiconductors: NVDA, AMD, AVGO, QCOM, INTC, ARM, MRVL, AMAT, TSM
- Memory / storage: MU, SNDK, WDC, DRAM
- AI infrastructure / optical / data center: CRWV, NBIS, VRT, DELL, COHR, AAOI,
  LITE, GLW
- Crypto-adjacent / high beta: COIN, HOOD, CRCL, MSTR, BMNR, CBRS
- ETFs / market proxies: SPY, QQQ, IWM, SOXL, XLE, USO, URNM, EWJ, EWY
- Pre-market / pre-IPO: OPENAI, SPACEX, ANTHROPIC
- Other high beta / event names: PLTR, RKLB, GME, HIMS, USAR, GEV, BE, LLY,
  COST, CSCO, NOK

## OKX Public API Examples

```text
GET https://www.okx.com/api/v5/public/instruments?instType=SWAP
GET https://www.okx.com/api/v5/market/ticker?instId=NVDA-USDT-SWAP
GET https://www.okx.com/api/v5/market/candles?instId=NVDA-USDT-SWAP&bar=1m&limit=120
GET https://www.okx.com/api/v5/market/candles?instId=NVDA-USDT-SWAP&bar=5m&limit=120
GET https://www.okx.com/api/v5/market/candles?instId=NVDA-USDT-SWAP&bar=15m&limit=120
GET https://www.okx.com/api/v5/market/candles?instId=NVDA-USDT-SWAP&bar=1H&limit=120
GET https://www.okx.com/api/v5/market/candles?instId=NVDA-USDT-SWAP&bar=1Dutc&limit=30
```
