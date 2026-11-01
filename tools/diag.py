import urllib.request, time, json
def t(url, ua):
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': ua}), timeout=20) as r:
            b = r.read(); print(r.status, len(b), round(time.time()-t0, 2), ua[:20], url[:90])
    except Exception as e:
        print('ERR', e, round(time.time()-t0, 2), ua[:20], url[:90])
for ua in ['Mozilla/5.0 (portefeuille web app)', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36']:
    for u in ['https://query1.finance.yahoo.com/v8/finance/chart/MA?range=5d&interval=1d',
              'https://query1.finance.yahoo.com/v8/finance/chart/CL?range=max&interval=1mo',
              'https://query2.finance.yahoo.com/v8/finance/chart/CL?range=max&interval=1mo',
              'https://query1.finance.yahoo.com/v8/finance/chart/CL?range=2y&interval=1wk']:
        t(u, ua)
