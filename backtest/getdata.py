import os, time
from fetch import fetch
import pandas as pd

TICKERS = ['SPY','QQQ','AAPL','BTC-USD']
START='2018-06-01'  # extra lead for indicator warmup
END='2026-06-27'
os.makedirs('data', exist_ok=True)

for t in TICKERS:
    fn=f'data/{t}.csv'
    if os.path.exists(fn):
        print('cached', t); continue
    df=fetch(t, START, END)
    df.to_csv(fn)
    print('saved', t, len(df), df.index.min().date(), df.index.max().date())
    time.sleep(1)
