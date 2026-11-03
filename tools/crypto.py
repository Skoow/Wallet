"""Les 1 000 premières cryptos (classement par capitalisation, source CoinGecko, sans clé) -> data/crypto.json,
   avec une note /100 sur un barème propre aux cryptos :
     Taille 15 (rang)                       · Liquidité 10 (volume / capitalisation)
     Dilution 15 (en circulation / maximum, et capitalisation / valeur totale diluée)
     Ancienneté 10 (années d'existence)     · Développement 10 (activité du code ces 4 dernières semaines)
     Communauté et marchés 10 (nombre de places de cotation, suiveurs) · Distance au plus haut 10
     Face au bitcoin 10 (1 an)              · Stabilité 10 (variations sur 7 et 30 jours)
   Les fiches détaillées (âge, code, communauté) sont relues par roulement, 120 par passage, gardées dans data/crypto_info.json."""
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
                    f'&page={page}&sparkline=false&price_change_percentage=7d,30d,200d,1y')
        time.sleep(8)
    btc = next((r for r in rows if r.get('id') == 'bitcoin'), {})
    b1y = btc.get('price_change_percentage_1y_in_currency') or 0
    STABLE = {'usdt', 'usdc', 'dai', 'fdusd', 'usde', 'tusd', 'pyusd', 'usdd', 'frax', 'busd', 'usds', 'rlusd', 'usd1', 'gusd', 'usdp', 'eurc'}
    # fiches détaillées, par roulement (les plus anciennes d'abord)
    try: INFO = json.load(open('data/crypto_info.json', encoding='utf-8'))
    except Exception: INFO = {}
    now = time.time()
    todo = sorted([r['id'] for r in rows], key=lambda i: (INFO.get(i) or {}).get('t', 0))
    for i in todo[:int(__import__('os').environ.get('CG_INFO', '120'))]:
        if now - (INFO.get(i) or {}).get('t', 0) < 6 * 86400: continue
        try:
            d = get(f'https://api.coingecko.com/api/v3/coins/{i}?localization=false&tickers=true&market_data=false&community_data=true&developer_data=true&sparkline=false', tries=2)
            dv = d.get('developer_data') or {}; cm = d.get('community_data') or {}
            INFO[i] = {'t': int(time.time()), 'gen': d.get('genesis_date'), 'cat': (d.get('categories') or [])[:3], 'algo': d.get('hashing_algorithm'),
                       'commits4w': dv.get('commit_count_4_weeks'), 'contrib': dv.get('pull_request_contributors'), 'stars': dv.get('stars'),
                       'tw': cm.get('twitter_followers'), 'tg': cm.get('telegram_channel_user_count'),
                       'places': len({(t.get('market') or {}).get('identifier') for t in d.get('tickers') or []}),
                       'web': ((d.get('links') or {}).get('homepage') or [None])[0]}
        except Exception as e:
            print(i, 'info', e)
        time.sleep(2.6)
    json.dump(INFO, open('data/crypto_info.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    out = []
    today = dt.date.today()
    for r in rows:
        if not r.get('current_price') or not r.get('market_cap_rank'): continue
        rk, mc, vol = r['market_cap_rank'], r.get('market_cap') or 0, r.get('total_volume') or 0
        athc = r.get('ath_change_percentage'); c7 = r.get('price_change_percentage_7d_in_currency'); c30 = r.get('price_change_percentage_30d_in_currency')
        c200 = r.get('price_change_percentage_200d_in_currency'); c1y = r.get('price_change_percentage_1y_in_currency')
        circ, mx, tot, fdv = r.get('circulating_supply') or 0, r.get('max_supply'), r.get('total_supply'), r.get('fully_diluted_valuation')
        stable = r['symbol'].lower() in STABLE or (0.97 <= r['current_price'] <= 1.03 and abs(c30 or 0) < 2 and abs(c1y or 0) < 5) or (1.0 <= r['current_price'] <= 1.25 and 'eur' in (r['symbol'] + r['name']).lower() and abs(c30 or 0) < 3)
        inf = INFO.get(r['id']) or {}
        P = {}
        P['taille'] = lin([[1, 1], [10, .95], [50, .75], [100, .6], [300, .35], [1000, 0]], rk) * 15
        liq = vol / mc * 100 if mc else 0
        P['liquidite'] = lin([[0.2, 0], [1, .35], [3, .65], [8, .9], [15, 1]], liq) * 10
        ref = mx or tot
        dil = circ / ref * 100 if ref else None
        dfd = mc / fdv * 100 if fdv else None
        dv = [x for x in ((lin([[10, 0], [30, .3], [60, .65], [85, .9], [100, 1]], dil) if dil is not None else None),
                          (lin([[10, 0], [40, .4], [70, .75], [95, 1]], dfd) if dfd is not None else None)) if x is not None]
        P['dilution'] = (sum(dv) / len(dv) if dv else .4) * 15
        # ancienneté : date de création, sinon la plus ancienne date connue (plus haut ou plus bas historique)
        d0 = None
        for k in (inf.get('gen'), r.get('atl_date'), r.get('ath_date')):
            try:
                x = dt.date.fromisoformat(str(k)[:10])
                d0 = x if d0 is None or x < d0 else d0
            except Exception: pass
        age = (today - d0).days / 365.25 if d0 else None
        P['anciennete'] = lin([[0, 0], [1, .2], [3, .55], [5, .8], [8, 1]], age) * 10 if age is not None else 4
        cmt = inf.get('commits4w')
        P['developpement'] = (lin([[0, .1], [5, .4], [20, .7], [60, .9], [150, 1]], cmt) if cmt is not None else .35) * 10
        pl, tw = inf.get('places'), inf.get('tw')
        cv = [x for x in ((lin([[1, 0], [5, .4], [20, .75], [60, 1]], pl) if pl else None), (lin([[0, 0], [10e3, .3], [100e3, .6], [1e6, 1]], tw) if tw else None)) if x is not None]
        P['communaute'] = (sum(cv) / len(cv) if cv else .4) * 10
        P['plus_haut'] = lin([[-95, 0], [-80, .2], [-60, .45], [-40, .7], [-20, .9], [-5, 1]], athc) * 10 if athc is not None else 4
        P['tendance'] = (lin([[-80, 0], [-40, .3], [0, .6], [40, .85], [100, 1]], (c1y or 0) - b1y) * .7 + (lin([[-50, 0], [0, .6], [50, 1]], c200) if c200 is not None else .5) * .3) * 10 if c1y is not None else 4
        sv = [x for x in ((lin([[0, 1], [10, .85], [25, .55], [45, .25], [70, 0]], abs(c30)) if c30 is not None else None),
                          (lin([[0, 1], [5, .8], [12, .45], [25, 0]], abs(c7)) if c7 is not None else None)) if x is not None]
        P['stabilite'] = (sum(sv) / len(sv) if sv else .4) * 10
        note = round(sum(P.values()))
        out.append({'id': r['id'], 's': r['symbol'].upper(), 'n': r['name'], 'r': rk, 'p': r['current_price'], 'mc': mc, 'v': vol,
                    'athc': None if athc is None else round(athc, 1), 'c7': None if c7 is None else round(c7, 1), 'c30': None if c30 is None else round(c30, 1),
                    'c200': None if c200 is None else round(c200, 1), 'c1y': None if c1y is None else round(c1y, 1),
                    'dil': None if dil is None else round(dil, 1), 'dfd': None if dfd is None else round(dfd, 1), 'age': None if age is None else round(age, 1),
                    'cmt': cmt, 'pl': pl, 'tw': tw, 'cat': inf.get('cat'), 'liq': round(liq, 1),
                    'img': r.get('image'), 'note': None if stable else note, 'stable': stable or None,
                    'det': {k: round(v, 1) for k, v in P.items()}})
    json.dump({'maj': dt.datetime.now(dt.timezone.utc).isoformat(timespec='minutes'), 'btc_1y': round(b1y, 1), 'c': out},
              open('data/crypto.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(len(out), 'cryptos')


if __name__ == '__main__':
    main()
