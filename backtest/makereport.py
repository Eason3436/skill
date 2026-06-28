import pandas as pd
from engine import load, STRATS, backtest, stats, monthly

TICKERS=['SPY','QQQ','AAPL','BTC-USD']
START='2019-01-01'
SRC={
 'Buy&Hold':'基準(被動持有)',
 'SMA 50/200 (Golden Cross)':'黃金交叉,backtrader/各大教學 repo 經典',
 'SMA 10/20 (backtesting.py)':'backtesting.py 官方 README 範例 SmaCross',
 'RSI(2) MeanRev (Connors)':'Larry Connors RSI(2),freqtrade/quantsoftware 常見',
 'Bollinger MeanRev':'布林通道均值回歸,各量化教學 repo 經典',
 'MACD Crossover':'MACD 金叉/死叉,TA 教學 repo 經典',
 'Donchian Breakout (Turtle)':'海龜交易法 Donchian 突破',
}

rows=[]
mstore={}
for t in TICKERS:
    df=load(t)
    for name,fn in STRATS.items():
        r=backtest(df,fn(df),start=START)
        st=stats(r); m=monthly(r); mstore[(t,name)]=m
        rows.append([t,name,SRC[name],round(m.mean()*100,2),round(st['CAGR']*100,1),
                     round(st['Sharpe'],2),round(st['MaxDD']*100,1),
                     round((m>0).mean()*100),round(m.max()*100,1),round(m.min()*100,1)])
S=pd.DataFrame(rows,columns=['標的','策略','開源來源','平均月收益%','年化CAGR%','Sharpe','最大回撤%','獲利月份%','最佳月%','最差月%'])

L=[]
L.append("# 開源交易策略回測報告\n")
L.append("> 自行下載真實歷史價格(Yahoo Finance 調整後資料),自行回測產出。**非過去績效保證,僅供研究。**\n")
L.append("## 方法\n")
L.append("- **期間**:2019-01-01 ~ 2026-06-26(約 7.5 年,含 2020 崩盤、2022 熊市、2023-25 多頭)\n")
L.append("- **標的**:SPY(標普500 ETF)、QQQ(那斯達克100 ETF)、AAPL(蘋果)、BTC-USD(比特幣)\n")
L.append("- **執行假設**:當日收盤產生訊號 → **隔日開盤成交**(避免前視偏誤);每次換倉計 **0.05% 交易成本**;多單/空手(long/flat)\n")
L.append("- **資料筆數**:每檔約 2000+ 交易日,真實 OHLCV\n")
L.append("- **策略來源**:GitHub 上最廣為流傳的開源策略標準版本(`backtesting.py`、`freqtrade`、`backtrader` 範例等),由我重新實作並回測\n\n")
L.append("## 總表(各標的 × 各策略)\n")
for t in TICKERS:
    L.append(f"\n### {t}\n")
    sub=S[S['標的']==t].drop(columns='標的')
    L.append(sub.to_markdown(index=False))
    L.append("\n")

L.append("\n## 各策略「平均月收益」排名(跨全部標的彙整)\n")
agg=S.groupby('策略').agg(平均月收益=('平均月收益%','mean'),平均CAGR=('年化CAGR%','mean'),平均Sharpe=('Sharpe','mean')).round(2).sort_values('平均月收益',ascending=False)
L.append(agg.to_markdown())
L.append("\n")

# yearly breakdown for SPY & BTC
for t in ['SPY','BTC-USD']:
    L.append(f"\n## {t} — 各策略逐年報酬 %\n")
    yr_rows=[]
    for name in STRATS:
        m=mstore[(t,name)]
        yr=(1+m).groupby(m.index.year).prod()-1
        d={'策略':name}; d.update({int(k):round(v*100,1) for k,v in yr.items()})
        yr_rows.append(d)
    L.append(pd.DataFrame(yr_rows).to_markdown(index=False))
    L.append("\n")

L.append("\n## 重點觀察\n")
L.append("1. **被動 Buy & Hold 在 Sharpe 與總報酬上多數情況贏過技術策略** — 這是學術界與實務界反覆驗證的結論,扣成本後尤其明顯。\n")
L.append("2. 技術策略真正的價值在**降低回撤**:例如 Donchian 海龜法在 SPY 最大回撤只有 -8.9%(vs 持有 -33.7%),RSI(2) 回撤更小,代價是報酬大幅縮水。\n")
L.append("3. **均值回歸類(RSI(2)、布林)在強趨勢標的(QQQ/AAPL/BTC)表現差**,因為常常太早出場、錯過大段趨勢。\n")
L.append("4. **趨勢類(MACD、Donchian)在 AAPL/BTC 等高波動趨勢標的表現較好**,MACD 在 AAPL 甚至 Sharpe 1.23。\n")
L.append("5. 沒有任何策略在所有標的都最佳 — 策略與標的特性需匹配。\n")
L.append("\n## 檔案\n- `summary.csv` — 完整總表\n- `monthly_returns_pct.csv` — 每月收益明細(每策略每標的)\n- `fetch.py` / `getdata.py` / `engine.py` / `run.py` — 抓資料與回測程式碼,可重現\n")
L.append("\n## 免責\n回測使用真實歷史資料但屬理想化假設(成交於開盤價、固定低成本、未計滑價/借券/稅),實盤結果會更差。過去績效不代表未來。本報告僅供研究教育用途,非投資建議。\n")

open('REPORT.md','w').write("\n".join(L))
S.to_csv('summary.csv',index=False)
allm=pd.DataFrame({f"{t}|{n}":mstore[(t,n)] for (t,n) in mstore})
allm.index=allm.index.strftime('%Y-%m')
(allm*100).round(2).to_csv('monthly_returns_pct.csv')
print("report written, lines:", len(L))
