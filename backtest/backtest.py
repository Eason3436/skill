import json, time, math

DATA = "xaut_30m.json"
raw = json.load(open(DATA))  # [ts,o,h,l,c,vol] sorted asc, 30m

PERIOD = 20          # Bollinger MA length (standard)
FEE = 0.001          # 0.1% per side, applied for "net" column

def resample(rows, minutes):
    """Aggregate 30m rows into `minutes`-minute buckets aligned to epoch."""
    step = minutes * 60 * 1000
    buckets = {}
    order = []
    for ts, o, h, l, c, v in rows:
        b = ts - (ts % step)
        if b not in buckets:
            buckets[b] = [o, h, l, c, v]
            order.append(b)
        else:
            bk = buckets[b]
            bk[1] = max(bk[1], h)
            bk[2] = min(bk[2], l)
            bk[3] = c
            bk[4] += v
    return [[b] + buckets[b] for b in order]  # ts,o,h,l,c,v

def backtest(candles, k):
    closes = [c[4] for c in candles]
    n = len(closes)
    cash = 1.0
    pos = 0.0        # units held (in equity terms: 1.0 = fully invested)
    entry = None
    eq_curve = []
    trades = []
    peak = 1.0
    maxdd = 0.0
    invested = False
    for i in range(n):
        c = closes[i]
        # mark-to-market equity
        if invested:
            equity = pos * c
        else:
            equity = cash
        # bands need PERIOD closes
        if i >= PERIOD - 1:
            window = closes[i - PERIOD + 1:i + 1]
            mid = sum(window) / PERIOD
            var = sum((x - mid) ** 2 for x in window) / PERIOD
            sd = math.sqrt(var)
            upper = mid + k * sd
            lower = mid - k * sd
            if not invested and c <= lower:
                # buy at close
                pos = cash / c
                entry = c
                invested = True
                equity = pos * c
            elif invested and c >= upper:
                # sell at close
                cash = pos * c
                trades.append((entry, c))
                invested = False
                pos = 0.0
                entry = None
                equity = cash
        eq_curve.append(equity)
        if equity > peak:
            peak = equity
        dd = (equity - peak) / peak
        if dd < maxdd:
            maxdd = dd
    # if still holding at end, mark to last close (already in equity)
    final = eq_curve[-1] if eq_curve else 1.0
    total_ret = final - 1.0

    # net (with fees): recompute pnl per trade + open trade
    net = 1.0
    for e, x in trades:
        net *= (x / e) * (1 - FEE) ** 2
    if invested and entry:
        net *= (closes[-1] / entry) * (1 - FEE)
    net_ret = net - 1.0

    wins = sum(1 for e, x in trades if x > e)
    return {
        "bars": n,
        "trades": len(trades),
        "open_at_end": invested,
        "win_rate": (wins / len(trades) * 100) if trades else 0.0,
        "total_ret": total_ret * 100,
        "net_ret": net_ret * 100,
        "maxdd": maxdd * 100,
    }

configs = [
    ("30m", 30, 2.5),
    ("1h",  60, 2.5),
    ("2h",  120, 2.5),
    ("3h",  180, 2.0),
    ("4h",  240, 2.0),
    ("6h",  360, 2.0),
    ("8h",  480, 2.0),
    ("12h", 720, 2.0),
]

start = time.strftime('%Y-%m-%d', time.gmtime(raw[0][0] / 1000))
end = time.strftime('%Y-%m-%d', time.gmtime(raw[-1][0] / 1000))
print(f"XAUT-USDT (OKX)  |  {start} -> {end}  |  Bollinger(period={PERIOD}), long-only, NO stop loss")
print(f"Rule: BUY at close<=lower band, SELL at close>=upper band. Max DD = mark-to-market (open position included).\n")
hdr = f"{'TF':>4} {'k':>4} {'bars':>6} {'trades':>7} {'win%':>6} {'return%':>9} {'net%(0.1f)':>10} {'maxDD%':>8} {'open?':>6}"
print(hdr)
print("-" * len(hdr))
for name, mins, k in configs:
    cd = raw if mins == 30 else resample(raw, mins)
    r = backtest(cd, k)
    print(f"{name:>4} {k:>4} {r['bars']:>6} {r['trades']:>7} {r['win_rate']:>6.1f} "
          f"{r['total_ret']:>9.2f} {r['net_ret']:>10.2f} {r['maxdd']:>8.2f} {str(r['open_at_end']):>6}")
