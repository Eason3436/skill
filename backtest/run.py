import pandas as pd, numpy as np
from engine import load, STRATS, backtest, stats, monthly
pd.set_option('display.width',200)

TICKERS=['SPY','QQQ','AAPL','BTC-USD']
START='2019-01-01'

summary=[]
monthly_store={}
for t in TICKERS:
    df=load(t)
    for name,fn in STRATS.items():
        pos=fn(df)
        r=backtest(df,pos,start=START)
        st=stats(r)
        if not st: continue
        m=monthly(r)
        summary.append({'Asset':t,'Strategy':name,
            'CAGR%':round(st['CAGR']*100,1),
            'AvgMonthly%':round(m.mean()*100,2),
            'BestMo%':round(m.max()*100,1),'WorstMo%':round(m.min()*100,1),
            '%PosMonths':round((m>0).mean()*100,0),
            'Sharpe':round(st['Sharpe'],2),'MaxDD%':round(st['MaxDD']*100,1),
            'TotalRet%':round(st['TotalRet']*100,0)})
        monthly_store[(t,name)]=m

S=pd.DataFrame(summary)
S.to_csv('summary.csv',index=False)
print("="*120)
print("SUMMARY  (2019-01 .. 2026-06, next-open exec, 0.05% cost, long/flat)")
print("="*120)
for t in TICKERS:
    print(f"\n### {t}")
    print(S[S.Asset==t].drop(columns='Asset').to_string(index=False))

# Save full monthly table for SPY as example
print("\n\n"+"="*120)
print("MONTHLY RETURNS % — SPY (per strategy, by year)")
print("="*120)
for name in STRATS:
    m=monthly_store[('SPY',name)]
    yr=(1+m).groupby(m.index.year).prod()-1
    print(f"\n{name}: annual % ->", {int(k):round(v*100,1) for k,v in yr.items()})

# Build a combined monthly CSV for all
allm=pd.DataFrame({f"{t}|{n}":monthly_store[(t,n)] for (t,n) in monthly_store})
allm.index=allm.index.strftime('%Y-%m')
(allm*100).round(2).to_csv('monthly_returns_pct.csv')
print("\nSaved: summary.csv, monthly_returns_pct.csv")
