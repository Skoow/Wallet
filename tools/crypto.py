"""Les 1 000 premières cryptos (classement par capitalisation, source CoinGecko, sans clé) -> data/crypto.json,
   avec une note /100 sur un barème propre aux cryptos :
     Taille 12 · Liquidité 8 · Dilution 12 · Ancienneté 8 · Développement 8 (code, GitHub) · Marchés et notoriété 8
     Plus haut 8 · Face au bitcoin 8 · Stabilité 8
     Fondamentaux 12 (frais payés par les utilisateurs et argent déposé, rapportés à la capitalisation ; DefiLlama)
     Usage 12 (infrastructure / DeFi / autre ; les memecoins n'ont rien)
   Les fiches détaillées (âge, code, communauté) sont relues par roulement, 120 par passage, gardées dans data/crypto_info.json."""
import os, json, math, time, urllib.request, datetime as dt

UA = {'User-Agent': 'Portefeuille-Wallet/1.0 (github.com/Skoow/Wallet)', 'Accept': 'application/json'}


def get(url, tries=4, pause=15):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception as e:
            err = e; time.sleep(pause * (i + 1))
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
    t_fin = time.time() + 12 * 60  # 12 minutes au plus pour les fiches détaillées (l'API gratuite limite le débit)
    for i in todo[:int(__import__('os').environ.get('CG_INFO', '120'))]:
        if time.time() > t_fin: print('fiches : budget de temps atteint'); break
        if now - (INFO.get(i) or {}).get('t', 0) < 6 * 86400: continue
        try:
            d = get(f'https://api.coingecko.com/api/v3/coins/{i}?localization=false&tickers=true&market_data=false&community_data=false&developer_data=false&sparkline=false', tries=2, pause=20)
            dv = d.get('developer_data') or {}; cm = d.get('community_data') or {}
            INFO[i] = {'t': int(time.time()), 'gen': d.get('genesis_date'), 'cat': (d.get('categories') or [])[:3], 'algo': d.get('hashing_algorithm'),
                       'commits4w': dv.get('commit_count_4_weeks'), 'contrib': dv.get('pull_request_contributors'), 'stars': dv.get('stars'),
                       'tw': cm.get('twitter_followers'), 'tg': cm.get('telegram_channel_user_count'),
                       'places': len({(t.get('market') or {}).get('identifier') for t in d.get('tickers') or []}),
                       'web': ((d.get('links') or {}).get('homepage') or [None])[0],
                       'gh': next((u for u in (((d.get('links') or {}).get('repos_url') or {}).get('github') or []) if 'github.com/' in u), None)}
        except Exception as e:
            print(i, 'info', e)
        time.sleep(2.6)
    # activité du code : API GitHub (le jeton du dépôt permet 1 000 appels par heure)
    tok = __import__('os').environ.get('GITHUB_TOKEN')
    hdr = {'User-Agent': UA['User-Agent'], 'Accept': 'application/vnd.github+json', **({'Authorization': 'Bearer ' + tok} if tok else {})}
    depuis = (dt.datetime.utcnow() - dt.timedelta(days=28)).strftime('%Y-%m-%dT%H:%M:%SZ')
    n = 0
    for i in sorted(INFO, key=lambda k: INFO[k].get('ght', 0)):
        x = INFO[i]; g = x.get('gh')
        if not g or now - x.get('ght', 0) < 6 * 86400 or n >= 300 or time.time() > t_fin + 8 * 60: continue
        parts = g.rstrip('/').split('github.com/')[-1].split('/')
        try:
            if len(parts) >= 2:
                rq = urllib.request.Request(f'https://api.github.com/repos/{parts[0]}/{parts[1]}/commits?since={depuis}&per_page=100', headers=hdr)
                with urllib.request.urlopen(rq, timeout=20) as r: x['commits4w'] = len(json.load(r))
                rq = urllib.request.Request(f'https://api.github.com/repos/{parts[0]}/{parts[1]}', headers=hdr)
                with urllib.request.urlopen(rq, timeout=20) as r: j = json.load(r); x['stars'] = j.get('stargazers_count')
            else:  # organisation : on prend son dépôt le plus récemment modifié
                rq = urllib.request.Request(f'https://api.github.com/orgs/{parts[0]}/repos?sort=pushed&per_page=1', headers=hdr)
                with urllib.request.urlopen(rq, timeout=20) as r: L = json.load(r)
                if L:
                    rq = urllib.request.Request(f'https://api.github.com/repos/{L[0]["full_name"]}/commits?since={depuis}&per_page=100', headers=hdr)
                    with urllib.request.urlopen(rq, timeout=20) as r: x['commits4w'] = len(json.load(r))
                    x['stars'] = L[0].get('stargazers_count')
        except Exception as e:
            x['commits4w'] = x.get('commits4w')
        x['ght'] = int(time.time()); n += 1
    print(n, 'dépôts de code relus')
    json.dump(INFO, open('data/crypto_info.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    # fondamentaux : frais payés par les utilisateurs et argent déposé (DefiLlama, gratuit, sans clé)
    FEES, TVL, G = {}, {}, {}
    try:
        for x in get('https://api.llama.fi/protocols'):
            g = x.get('gecko_id')
            if not g: continue
            for k in (x.get('slug'), x.get('name'), x.get('parentProtocol')):
                if k: G[str(k).lower()] = g
            if x.get('tvl'): TVL[g] = TVL.get(g, 0) + x['tvl']
        for x in get('https://api.llama.fi/v2/chains'):
            g = x.get('gecko_id')
            if g and x.get('tvl'): TVL[g] = max(TVL.get(g, 0), x['tvl'])
            if g and x.get('name'): G[x['name'].lower()] = g
    except Exception as e: print('tvl', e)
    try:
        for x in get('https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true').get('protocols') or []:
            g = x.get('gecko_id') or next((G[str(k).lower()] for k in (x.get('slug'), x.get('name'), x.get('parentProtocol'), x.get('displayName')) if k and str(k).lower() in G), None)
            if g and x.get('total30d'): FEES[g] = FEES.get(g, 0) + x['total30d']
    except Exception as e: print('fees', e)
    print(len(FEES), 'avec frais ;', len(TVL), 'avec dépôts')
    MEME = ('meme', 'dog-themed', 'cat-themed', 'frog-themed', 'pump.fun')
    out = []
    today = dt.date.today()
    # Troisième source (CoinMarketCap) si une clé gratuite est fournie (secret CMC_KEY)
    CMC = {}
    if os.environ.get('CMC_KEY'):
        try:
            rq = urllib.request.Request('https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest?limit=1500&convert=USD',
                                        headers={'X-CMC_PRO_API_KEY': os.environ['CMC_KEY'], 'Accept': 'application/json'})
            with urllib.request.urlopen(rq, timeout=40) as rr:
                for x in json.load(rr).get('data') or []:
                    q = (x.get('quote') or {}).get('USD') or {}
                    if q.get('price'): CMC.setdefault(str(x.get('symbol', '')).upper(), []).append((str(x.get('name', '')).lower(), x.get('cmc_rank') or 9999, q['price'], q.get('market_cap'), x.get('slug')))
        except Exception as e:
            print('CoinMarketCap indisponible :', e)
    # Deuxième source indépendante (CoinPaprika) pour recouper cours et capitalisation
    PAP = {}
    try:
        for x in get('https://api.coinpaprika.com/v1/tickers?quotes=USD', tries=2, pause=10) or []:
            q = (x.get('quotes') or {}).get('USD') or {}
            if q.get('price'): PAP.setdefault(str(x.get('symbol', '')).upper(), []).append((str(x.get('name', '')).lower(), x.get('rank') or 9999, q['price'], q.get('market_cap')))
    except Exception as e:
        print('CoinPaprika indisponible :', e)
    for r in rows:
        if not r.get('current_price') or not r.get('market_cap_rank'): continue
        rk, mc, vol = r['market_cap_rank'], r.get('market_cap') or 0, r.get('total_volume') or 0
        athc = r.get('ath_change_percentage'); c7 = r.get('price_change_percentage_7d_in_currency'); c30 = r.get('price_change_percentage_30d_in_currency')
        c200 = r.get('price_change_percentage_200d_in_currency'); c1y = r.get('price_change_percentage_1y_in_currency')
        circ, mx, tot, fdv = r.get('circulating_supply') or 0, r.get('max_supply'), r.get('total_supply'), r.get('fully_diluted_valuation')
        stable = r['symbol'].lower() in STABLE or (0.97 <= r['current_price'] <= 1.03 and abs(c30 or 0) < 2 and abs(c1y or 0) < 5) or (1.0 <= r['current_price'] <= 1.25 and 'eur' in (r['symbol'] + r['name']).lower() and abs(c30 or 0) < 3)
        inf = INFO.get(r['id']) or {}
        P = {}
        P['taille'] = lin([[1, 1], [10, .95], [50, .75], [100, .6], [300, .35], [1000, 0]], rk) * 12
        liq = vol / mc * 100 if mc else 0
        P['liquidite'] = (lin([[0.2, 0], [1, .35], [3, .65], [8, .9], [15, 1]], liq) if liq <= 60 else .3) * 8  # volume > 60 % de la capitalisation : suspect
        ref = mx or tot
        dil = circ / ref * 100 if ref else None
        dfd = mc / fdv * 100 if fdv else None
        dv = [x for x in ((lin([[10, 0], [30, .3], [60, .65], [85, .9], [100, 1]], dil) if dil is not None else None),
                          (lin([[10, 0], [40, .4], [70, .75], [95, 1]], dfd) if dfd is not None else None)) if x is not None]
        P['dilution'] = (sum(dv) / len(dv) if dv else .4) * 12
        # ancienneté : date de création, sinon la plus ancienne date connue (plus haut ou plus bas historique)
        d0 = None
        for k in (inf.get('gen'), r.get('atl_date'), r.get('ath_date')):
            try:
                x = dt.date.fromisoformat(str(k)[:10])
                d0 = x if d0 is None or x < d0 else d0
            except Exception: pass
        age = (today - d0).days / 365.25 if d0 else None
        P['anciennete'] = lin([[0, 0], [1, .2], [3, .55], [5, .8], [8, 1]], age) * 8 if age is not None else 3
        cmt = inf.get('commits4w')
        P['developpement'] = (lin([[0, .1], [5, .4], [20, .7], [60, .9], [100, 1]], cmt) if cmt is not None else .35) * 8
        pl, tw = inf.get('places'), inf.get('stars')
        cv = [x for x in ((lin([[1, 0], [5, .4], [20, .75], [60, 1]], pl) if pl else None), (lin([[0, 0], [100, .3], [1000, .6], [10000, 1]], tw) if tw else None)) if x is not None]
        P['communaute'] = (sum(cv) / len(cv) if cv else .4) * 8
        P['plus_haut'] = lin([[-95, 0], [-80, .2], [-60, .45], [-40, .7], [-20, .9], [-5, 1]], athc) * 8 if athc is not None else 3
        P['tendance'] = (lin([[-80, 0], [-40, .3], [0, .6], [40, .85], [100, 1]], (c1y or 0) - b1y) * .7 + (lin([[-50, 0], [0, .6], [50, 1]], c200) if c200 is not None else .5) * .3) * 8 if c1y is not None else 3
        sv = [x for x in ((lin([[0, 1], [10, .85], [25, .55], [45, .25], [70, 0]], abs(c30)) if c30 is not None else None),
                          (lin([[0, 1], [5, .8], [12, .45], [25, 0]], abs(c7)) if c7 is not None else None)) if x is not None]
        P['stabilite'] = (sum(sv) / len(sv) if sv else .4) * 8
        fees, tvl = FEES.get(r['id']), TVL.get(r['id'])
        fv = []
        if fees and mc: fv.append(lin([[0.1, 0], [1, .4], [3, .7], [8, .9], [15, 1]], fees * 12 / mc * 100))  # frais annuels en % de la capitalisation
        if tvl and mc: fv.append(lin([[1, 0], [10, .35], [30, .65], [80, .9], [150, 1]], tvl / mc * 100))
        P['fondamentaux'] = (sum(fv) / len(fv) if fv else .2) * 12
        cats = [c.lower() for c in inf.get('cat') or []]
        meme = any(any(m in c for m in MEME) for c in cats)
        P['usage'] = (0 if meme else 1 if any(k in c for c in cats for k in ('layer 1', 'smart contract', 'oracle', 'infrastructure', 'layer 2', 'store of value')) else .8 if any(k in c for c in cats for k in ('defi', 'decentralized exchange', 'lending', 'liquid staking', 'real world', 'payment')) else .5) * 12
        note = round(sum(P.values()))
        x2 = None
        C2 = PAP.get(r['symbol'].upper()) or []
        if C2:
            C2 = sorted(C2, key=lambda c: (c[0] != r['name'].lower(), abs((c[1] or 9999) - rk)))
            c2 = C2[0]
            ec = abs(c2[2] / r['current_price'] - 1) * 100 if r['current_price'] else None
            if ec is not None and ec < 25: x2 = {'p': c2[2], 'mc': c2[3], 'ec': round(ec, 2)}
        x3 = None
        C3 = CMC.get(r['symbol'].upper()) or []
        if C3:
            c3 = sorted(C3, key=lambda c: (c[0] != r['name'].lower(), abs((c[1] or 9999) - rk)))[0]
            e3 = abs(c3[2] / r['current_price'] - 1) * 100 if r['current_price'] else None
            if e3 is not None and e3 < 25: x3 = {'p': c3[2], 'mc': c3[3], 'ec': round(e3, 2), 'slug': c3[4]}
        srcs = ['CoinGecko'] + (['CoinMarketCap'] if x3 else []) + (['CoinPaprika'] if x2 else []) + (['DefiLlama'] if (fees or tvl) else []) + (['GitHub'] if cmt is not None else [])
        out.append({'id': r['id'], 's': r['symbol'].upper(), 'n': r['name'], 'r': rk, 'p': r['current_price'], 'mc': mc, 'v': vol,
                    'athc': None if athc is None else round(athc, 1), 'c7': None if c7 is None else round(c7, 1), 'c30': None if c30 is None else round(c30, 1),
                    'c200': None if c200 is None else round(c200, 1), 'c1y': None if c1y is None else round(c1y, 1),
                    'dil': None if dil is None else round(dil, 1), 'dfd': None if dfd is None else round(dfd, 1), 'age': None if age is None else round(age, 1),
                    'cmt': cmt, 'pl': pl, 'tw': inf.get('stars'), 'fees': round(fees * 12) if fees else None, 'tvl': round(tvl) if tvl else None, 'meme': meme or None, 'cat': inf.get('cat'), 'liq': round(liq, 1),
                    'img': r.get('image'), 'note': None if stable else note, 'stable': stable or None,
                    'det': {k: round(v, 1) for k, v in P.items()}, 'x2': x2, 'x3': x3, 'src': srcs})
    json.dump({'maj': dt.datetime.now(dt.timezone.utc).isoformat(timespec='minutes'), 'btc_1y': round(b1y, 1), 'c': out},
              open('data/crypto.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(len(out), 'cryptos')


if __name__ == '__main__':
    main()
