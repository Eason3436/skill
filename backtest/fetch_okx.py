import requests, time, json, sys

INST = "XAUT-USDT"
BAR = "30m"
OUT = "xaut_30m.json"  

sess = requests.Session()
base = "https://www.okx.com/api/v5/market/history-candles"

def fetch_page(after=None):
    p = {"instId": INST, "bar": BAR, "limit": "100"}
    if after is not None:
        p["after"] = str(after)
    for attempt in range(5):
        try:
            r = sess.get(base, params=p, timeout=30).json()
            if r.get("code") == "0":
                return r["data"]
            time.sleep(0.5)
        except Exception as e:
            time.sleep(1)
    return []

all_rows = {}
after = None
# stop when we reach this far back or no more data
STOP_TS = time.time() * 1000 - 3.2 * 365 * 24 * 3600 * 1000  # ~3.2 years
req = 0
while True:
    data = fetch_page(after)
    req += 1
    if not data:
        break
    for c in data:
        ts = int(c[0])
        all_rows[ts] = [float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])]  # o,h,l,c,vol
    oldest = int(data[-1][0])
    after = oldest
    if oldest < STOP_TS:
        break
    if req % 25 == 0:
        print(f"req={req} rows={len(all_rows)} oldest={time.strftime('%Y-%m-%d',time.gmtime(oldest/1000))}", flush=True)
    time.sleep(0.08)

rows = sorted(all_rows.items())
out = [[ts] + v for ts, v in rows]
json.dump(out, open(OUT, "w"))
print("TOTAL rows:", len(out))
print("range:", time.strftime('%Y-%m-%d', time.gmtime(out[0][0]/1000)), "->", time.strftime('%Y-%m-%d', time.gmtime(out[-1][0]/1000)))
