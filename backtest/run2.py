import pandas as pd, numpy as np
from engine import load, STRATS, backtest, stats, monthly
pd.set_option('display.width',220)

TICKERS=['MSFT','NVDA','TSLA','AMZN','GOOGL','META','JPM','KO','XOM','JNJ']
START='2019-01-01'

rows=[]; dd_matrix={}; cagr_matrix={}; mstore={}
for t in TICKERS:
    df=load(t)
    for name,fn in STRATS.items():
        r=backtest(df,fn(df),start=START); st=stats(r); m=monthly(r); mstore[(t,name)]=m
        rows.append({'Asset':t,'Strategy':name,'AvgMo%':round(m.mean()*100,2),
            'CAGR%':round(st['CAGR']*100,1),'Sharpe':round(st['Sharpe'],2),
            'MaxDD%':round(st['MaxDD']*100,1),'WorstMo%':round(m.min()*100,1),
            'TotalRet%':round(st['TotalRet']*100,0)})
        dd_matrix[(t,name)]=round(st['MaxDD']*100,1)
        cagr_matrix[(t,name)]=round(st['CAGR']*100,1)
S=pd.DataFrame(rows)
S.to_csv('summary_us.csv',index=False)

print("="*130); print("最大回撤矩陣 MaxDD% (列=股票, 欄=策略)  2019-01..2026-06"); print("="*130)
DD=pd.DataFrame(dd_matrix,index=[0]).T.unstack().droplevel(0,axis=1)
DD=pd.DataFrame({n:{t:dd_matrix[(t,n)] for t in TICKERS} for n in STRATS})
print(DD.to_string())
print("\n"+"="*130); print("年化報酬矩陣 CAGR%"); print("="*130)
CG=pd.DataFrame({n:{t:cagr_matrix[(t,n)] for t in TICKERS} for n in STRATS})
print(CG.to_string())

DD.to_csv('maxdd_matrix_us.csv'); CG.to_csv('cagr_matrix_us.csv')
allm=pd.DataFrame({f"{t}|{n}":mstore[(t,n)] for (t,n) in mstore})
allm.index=allm.index.strftime('%Y-%m'); (allm*100).round(2).to_csv('monthly_returns_us.csv')
print("\nsaved summary_us.csv, maxdd_matrix_us.csv, cagr_matrix_us.csv, monthly_returns_us.csv")
