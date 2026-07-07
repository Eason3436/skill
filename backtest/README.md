# TSM Bollinger 均值回歸策略回測（OKX）

「下軌買入、上軌賣出、不設止損」的布林通道策略，回測 OKX `TSM-USDT-SWAP`
（tokenized 美股 TSM 永續合約），週期 2H(±2.5) 與 3/4/6/8/12H(±2)。

## 結果
見 [`REPORT.md`](./REPORT.md)（含各週期收益、最大回徹與交易明細）與
[`results.json`](./results.json)（機器可讀）。

## 重現步驟
```bash
pip install pandas numpy
python fetch_okx.py TSM-USDT-SWAP 1H   # 抓取上市以來全部 1H K 線
PYTHONPATH=. python report.py           # 重採樣、回測、輸出 REPORT.md / results.json
```

## 檔案
- `fetch_okx.py` — OKX 歷史 K 線抓取（分頁，經 curl）。
- `engine.py` — 重採樣 + 布林通道回測引擎（`CONFIG` 定義各週期與軌道倍數）。
- `report.py` — 產生 `REPORT.md` 與 `results.json`。
- `data_TSM-USDT-SWAP_1H.json` — 快取的原始 1H 資料。

## 方法重點
- OKX 無原生 3H / 8H K 線，故以 1H 為基礎重採樣（對齊 UTC，已與原生 2H 校驗一致）。
- 布林：中軌 SMA(20)，上/下軌 = 中軌 ± k×std(20, population)。
- 只做多、每次全額、無槓桿、未計手續費/資金費率/滑點；最大回徹取權益曲線 mark-to-market 最深回落。
- 該合約 2026-03 才上市，樣本僅約 4 個月，統計意義有限。
