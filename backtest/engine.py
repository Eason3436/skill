import numpy as np, pandas as pd

def load(t):
    df=pd.read_csv(f'data/{t}.csv', index_col='Date', parse_dates=True)
    return df

# ---------- indicators ----------
def sma(s,n): return s.rolling(n).mean()
def ema(s,n): return s.ewm(span=n, adjust=False).mean()
def rsi(s,n=14):
    d=s.diff()
    up=d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs=up/dn.replace(0,np.nan)
    return 100-100/(1+rs)
def atr(df,n=14):
    h,l,c=df['High'],df['Low'],df['Close']
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

# ---------- strategies: return target position series in {0,1} or {-1,0,1} ----------
# Use AdjClose for signals on equities (corporate actions); price series 'C'
def s_buyhold(df):
    return pd.Series(1.0, index=df.index)

def s_sma_cross(df, fast=50, slow=200):   # Golden Cross (classic backtrader/backtesting.py)
    c=df['AdjClose']
    pos=(sma(c,fast)>sma(c,slow)).astype(float)
    return pos

def s_sma_cross_fast(df, fast=10, slow=20):  # backtesting.py SmaCross example
    c=df['AdjClose']
    return (sma(c,fast)>sma(c,slow)).astype(float)

def s_rsi2(df, low=10, high=70, trend=200):  # Larry Connors RSI(2) mean reversion
    c=df['AdjClose']; r=rsi(c,2); ma=sma(c,trend)
    pos=pd.Series(np.nan,index=df.index)
    pos[(c>ma)&(r<low)]=1.0      # enter long
    pos[(r>high)]=0.0            # exit
    pos=pos.ffill().fillna(0.0)
    return pos

def s_bbands(df, n=20, k=2.0):   # Bollinger Band mean reversion (long when below lower, exit at mid)
    c=df['AdjClose']; m=sma(c,n); sd=c.rolling(n).std()
    lower=m-k*sd
    pos=pd.Series(np.nan,index=df.index)
    pos[c<lower]=1.0
    pos[c>=m]=0.0
    return pos.ffill().fillna(0.0)

def s_macd(df, f=12, sl=26, sig=9):  # MACD crossover, long/flat
    c=df['AdjClose']
    macd=ema(c,f)-ema(c,sl); signal=ema(macd,sig)
    return (macd>signal).astype(float)

def s_donchian(df, n=20):   # Turtle-style Donchian breakout (long/flat, 20 high entry, 10 low exit)
    c=df['AdjClose']
    hh=c.rolling(n).max().shift(1); ll=c.rolling(n//2).min().shift(1)
    pos=pd.Series(np.nan,index=df.index)
    pos[c>hh]=1.0
    pos[c<ll]=0.0
    return pos.ffill().fillna(0.0)

STRATS={
 'Buy&Hold':s_buyhold,
 'SMA 50/200 (Golden Cross)':s_sma_cross,
 'SMA 10/20 (backtesting.py)':s_sma_cross_fast,
 'RSI(2) MeanRev (Connors)':s_rsi2,
 'Bollinger MeanRev':s_bbands,
 'MACD Crossover':s_macd,
 'Donchian Breakout (Turtle)':s_donchian,
}

# ---------- backtest: signal at close -> execute next open, cost per turnover ----------
def backtest(df, pos, cost=0.0005, start='2019-01-01'):
    px=df['Open']  # execute at open
    # next-bar execution: position decided at close of t applies from open t+1
    pos=pos.shift(1).fillna(0.0)
    open_ret=px.pct_change().fillna(0.0)
    # but holding overnight close-to-close better; use AdjClose returns held while in position from next day
    ret=df['AdjClose'].pct_change().fillna(0.0)
    strat_ret=pos*ret
    turn=pos.diff().abs().fillna(0.0)
    strat_ret=strat_ret - turn*cost
    strat_ret=strat_ret[strat_ret.index>=start]
    return strat_ret

def stats(r):
    if len(r)==0 or r.std()==0: return {}
    eq=(1+r).cumprod()
    yrs=len(r)/252
    cagr=eq.iloc[-1]**(1/yrs)-1
    sharpe=r.mean()/r.std()*np.sqrt(252)
    dd=(eq/eq.cummax()-1).min()
    return {'CAGR':cagr,'Sharpe':sharpe,'MaxDD':dd,'TotalRet':eq.iloc[-1]-1}

def monthly(r):
    return (1+r).resample('ME').prod()-1
