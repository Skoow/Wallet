"""Les 1 000 premières cryptos (classement par capitalisation, source CoinGecko, sans clé) -> data/crypto.json,
   avec une note /100 sur un barème propre aux cryptos :
     Taille 25 (rang)            · Liquidité 15 (volume du jour / capitalisation)
     Distance au plus haut 15    · Dilution 15 (jetons en circulation / maximum)
     Tendance face au bitcoin 15 (1 an) · Stabilité 15 (variation sur 30 jours)"""
import json, math, time, urllib.request, datetime as dt

UA = {'User-Agent': 'Portefeuille-Wallet/1.0 (github.com/Skoow/Wallet)', 'Accept': 'application/json'}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception as e:
            err = e; time.sleep(15 * (i + 1))
    raise err


def lin(pts, v):
    if v <= pts[0][0]: return pts[0][1]
    for i in range(1, len(pts)):
        if v <= pts[i][0]:
            a, b = pts[i - 1]; c, d = pts[i]
            return b + (d - b) * (v - a) / (c - a)
    return pts[-1][1]


def main():
    rows = []
    for page in range(1, 5):
        rows += get('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250'
                    f'&page={page}&sparkline=false&price_change_percentage=30d,1y')
        time.sleep(8)
    btc = next((r for r in rows if r.get('id') == 'bitcoin'), {})
    b1y = btc.get('price_change_percentage_1y_in_currency') or 0
    STABLE = {'usdt', 'usdc', 'dai', 'fdusd', 'usde', 'tusd', 'pyusd', 'usdd', 'frax', 'busd', 'usds', 'rlusd', 'usd1', 'gusd', 'usdp', 'eurc'}
    out = []
    for r in rows:
        if not r.get('current_price') or not r.get('market_cap_rank'): continue
        rk, mc, vol = r['market_cap_rank'], r.get('market_cap') or 0, r.get('total_volume') or 0
        athc = r.get('ath_change_percentage'); c30 = r.get('price_change_percentage_30d_in_currency'); c1y = r.get('price_change_percentage_1y_in_currency')
        circ, mx, tot = r.get('circulating_supply') or 0, r.get('max_supply'), r.get('total_supply')
        stable = r['symbol'].lower() in STABLE
        P = {}
        P['taille'] = lin([[1, 1], [10, .95], [50, .75], [100, .6], [300, .35], [1000, 0]], rk) * 25
        liq = vol / mc * 100 if mc else 0
        P['liquidite'] = lin([[0.2, 0], [1, .35], [3, .65], [8, .9], [15, 1]], liq) * 15
        P['plus_haut'] = lin([[-95, 0], [-80, .2], [-60, .45], [-40, .7], [-20, .9], [-5, 1]], athc) * 15 if athc is not None else 7
        ref = mx or tot
        dil = circ / ref * 100 if ref else None
        P['dilution'] = (lin([[10, 0], [30, .3], [60, .65], [85, .9], [100, 1]], dil) if dil is not None else .4) * 15
        P['tendance'] = lin([[-80, 0], [-40, .3], [0, .6], [40, .85], [100, 1]], (c1y or 0) - b1y) * 15 if c1y is not None else 6
        P['stabilite'] = lin([[0, 1], [10, .85], [25, .55], [45, .25], [70, 0]], abs(c30)) * 15 if c30 is not None else 6
        note = round(sum(P.values()))
        out.append({'id': r['id'], 's': r['symbol'].upper(), 'n': r['name'], 'r': rk, 'p': r['current_price'], 'mc': mc, 'v': vol,
                    'athc': None if athc is None else round(athc, 1), 'c30': None if c30 is None else round(c30, 1),
                    'c1y': None if c1y is None else round(c1y, 1), 'dil': None if dil is None else round(dil, 1),
                    'img': r.get('image'), 'note': None if stable else note, 'stable': stable or None,
                    'det': {k: round(v, 1) for k, v in P.items()}})
    json.dump({'maj': dt.datetime.now(dt.timezone.utc).isoformat(timespec='minutes'), 'btc_1y': round(b1y, 1), 'c': out},
              open('data/crypto.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(len(out), 'cryptos')


if __name__ == '__main__':
    main()
