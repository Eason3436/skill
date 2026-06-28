import requests, time, pandas as pd
from datetime import datetime, timezone

H = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

def _ts(d):
    return int(datetime.strptime(d,'%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp())

def fetch(ticker, start, end):
    p1, p2 = _ts(start), _ts(end)
    url = (f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}'
           f'?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit&includeAdjustedClose=true')
    for attempt in range(4):
        try:
            r = requests.get(url, headers=H, timeout=30)
            if r.status_code == 200:
                break
        except Exception as e:
            pass
        time.sleep(2*(attempt+1))
    else:
        raise RuntimeError(f'fetch failed {ticker}')
    j = r.json()['chart']['result'][0]
    ts = j['timestamp']
    q = j['indicators']['quote'][0]
    adj = j['indicators'].get('adjclose',[{}])[0].get('adjclose')
    df = pd.DataFrame({
        'Open':q['open'],'High':q['high'],'Low':q['low'],
        'Close':q['close'],'Volume':q['volume'],
        'AdjClose': adj if adj else q['close'],
    }, index=pd.to_datetime(ts, unit='s').normalize())
    df.index.name='Date'
    return df.dropna()

if __name__=='__main__':
    df = fetch('SPY','2023-01-01','2023-04-01')
    print('rows',len(df)); print(df.head(2)); print(df.tail(2))
