import os, time
from fetch import fetch
NEW=['MSFT','NVDA','TSLA','AMZN','GOOGL','META','JPM','KO','XOM','JNJ']
START='2018-06-01'; END='2026-06-27'
os.makedirs('data', exist_ok=True)
for t in NEW:
    fn=f'data/{t}.csv'
    if os.path.exists(fn): print('cached',t); continue
    try:
        df=fetch(t,START,END); df.to_csv(fn)
        print('saved',t,len(df),df.index.min().date(),df.index.max().date())
    except Exception as e:
        print('FAIL',t,e)
    time.sleep(1)
