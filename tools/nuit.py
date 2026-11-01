"""Travaux de nuit (GitHub Actions).

  python tools/nuit.py tickers  -> data/tickers.json : toutes les actions des bourses US (NYSE, Nasdaq, AMEX) et de Toronto
  python tools/nuit.py histo    -> data/h/<cle>.json : historique mensuel (depuis 2006) et hebdomadaire (2 ans)
                                   de chaque action de plus de 2 Md$ et de Toronto, chargé par la page quand on l'ajoute
  python tools/nuit.py derniers -> data/h/derniers.json : dernier cours de toutes ces actions (chaque soir)
  python tools/nuit.py chiffres -> data/univers.json : capitalisation, PER prévu, date des résultats chaque nuit ;
                                   marges, ROE, cash, dette après chaque publication de résultats (source Yahoo, marquée « auto »)
"""
import csv, io, json, os, re, sys, time, datetime as dt, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yahoo

D = 'data/'
SEC = {'Technology': 'Technologie', 'Health Care': 'Santé', 'Finance': 'Finance', 'Financials': 'Finance', 'Industrials': 'Industrie',
       'Consumer Discretionary': 'Consommation discrétionnaire', 'Consumer Staples': 'Consommation de base', 'Energy': 'Énergie',
       'Basic Materials': 'Matériaux', 'Materials': 'Matériaux', 'Utilities': 'Services publics', 'Real Estate': 'Immobilier',
       'Telecommunications': 'Communication', 'Communication Services': 'Communication', 'Information Technology': 'Technologie'}
BAD = re.compile(r'\b(Warrants?|Rights?|Units?|Preferred|Notes?|Debentures?|Depositary Shares? Each|Subordinated|Fixed-to|Trust Preferred)\b', re.I)


def raw(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': yahoo.UA}), timeout=60) as r:
        return r.read().decode('utf-8')


def clean(n):
    n = re.sub(r'\s+(Common Stock|Ordinary Shares|Class [A-C] (Common Stock|Ordinary Shares|Subordinate Voting Shares)|Common Shares|American Depositary Shares|Subordinate Voting Shares|Shares)\b.*$', '', n)
    n = re.sub(r',?\s+(Inc\.?|Incorporated|Corporation|Corp\.?|Ltd\.?|Limited|plc|N\.V\.|S\.A\.|Co\.|Company|Holdings?|Group)$', '', n.strip(), flags=re.I)
    return n.strip(' ,')


def tickers():
    out = {}
    base = 'https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/'
    for f in ('nyse/nyse_full_tickers.json', 'nasdaq/nasdaq_full_tickers.json', 'amex/amex_full_tickers.json'):
        for x in json.loads(raw(base + f)):
            t = x['symbol'].strip()
            if not t or re.search(r'[\^/ ]', t) or BAD.search(x['name']):
                continue
            try: c = round(float(x['marketCap'] or 0) / 1e9, 2)
            except Exception: c = 0
            try: p = float(x['lastsale'].replace('$', '').replace(',', ''))
            except Exception: p = None
            out['US:' + t] = [t, clean(x['name']), 'US', SEC.get(x['sector'], ''), c or None, p, x['country'] or '']
    for x in csv.DictReader(io.StringIO(raw('https://raw.githubusercontent.com/adanos-software/free-ticker-database/main/data/listings.csv'))):
        if x['exchange'] == 'TSX' and x['asset_type'] == 'Stock':
            t = x['ticker'].strip()
            out['TSX:' + t] = [t, clean(x['name']), 'TSX', SEC.get(x['stock_sector'], ''), None, None, x['country'] or 'Canada']
    L = sorted(out.values(), key=lambda r: (-(r[4] or 0), r[0]))
    if len(L) > 3000:
        json.dump(L, open(D + 'tickers.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(len(L), 'tickers')


def cle_of(t, ex):
    return ('a/tsx-' if ex == 'TSX' else 's/') + t.lower().replace('.', '-')


def ysym(t, ex):
    return t.replace('.', '-') + ('.TO' if ex == 'TSX' else '')


def fichier(cle):
    return D + 'h/' + cle.replace('/', '_') + '.json'


def histo(limite=None):
    os.makedirs(D + 'h', exist_ok=True)
    L = json.load(open(D + 'tickers.json', encoding='utf-8'))
    H0 = json.load(open(D + 'hebdo.json', encoding='utf-8'))
    d0 = dt.date.fromisoformat(H0[0]['debut']); n = len(H0[0]['prix'])
    weeks = [d0 + dt.timedelta(weeks=i) for i in range(n)]
    deja = {r['cle'] for r in json.load(open(D + 'prix.json', encoding='utf-8'))}
    todo = [r for r in L if (r[2] == 'TSX' or (r[4] or 0) >= 2) and cle_of(r[0], r[2]) not in deja]
    if limite: todo = todo[:limite]
    ok = 0
    for t, nom, ex, *_ in todo:
        cle = cle_of(t, ex)
        try:
            m = yahoo.chart(ysym(t, ex), 'depuis2006', '1mo')
            w = yahoo.chart(ysym(t, ex), '2y', '1wk')
            if not m or not m.get('timestamp'):
                continue
            mm = {}
            for ts, c in zip(m['timestamp'], m['indicators']['quote'][0]['close']):
                if c is None: continue
                d = dt.datetime.utcfromtimestamp(ts + 43200)
                if d.year >= 2006: mm[d.year * 12 + d.month - 1] = round(c, 4)
            last = m['meta'].get('regularMarketPrice')
            if mm and last:
                mm[max(mm)] = round(float(last), 4)
            if not mm: continue
            k0, k1 = min(mm), max(mm); pr = []; prev = None
            for k in range(k0, k1 + 1):
                prev = mm.get(k, prev); pr.append(prev)
            wk = {}
            if w and w.get('timestamp'):
                for ts, c in zip(w['timestamp'], w['indicators']['quote'][0]['close']):
                    if c is None: continue
                    d = dt.datetime.utcfromtimestamp(ts + 43200).date()
                    wk[d - dt.timedelta(days=d.weekday())] = round(c, 4)
                if last: wk[weeks[-1]] = round(float(last), 4) if max(wk) <= weeks[-1] else wk[max(wk)]
            hb = []; prev = None
            for d in weeks:
                prev = wk.get(d, prev); hb.append(prev)
            o = {'cle': cle, 'ticker': t, 'nom': nom, 'devise': 'CAD' if ex == 'TSX' else 'USD',
                 'debut': f'{k0 // 12}-{k0 % 12 + 1}', 'prix': pr, 'hdebut': weeks[0].isoformat(), 'hebdo': hb,
                 'maj': dt.date.today().isoformat()}
            json.dump(o, open(fichier(cle), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            ok += 1
        except Exception as e:
            print(t, e)
        time.sleep(0.15)
    print(ok, 'historiques sur', len(todo))


def v(d, *ks):
    for k in ks:
        d = (d or {}).get(k)
    if isinstance(d, dict):
        d = d.get('raw')
    return d


def chiffres():
    U = json.load(open(D + 'univers.json', encoding='utf-8'))
    import maj
    today = dt.date.today().isoformat(); nb = 0
    for u in U:
        s = maj.sym(u['cle'])
        if not s or u['cle'].startswith('e/'):
            continue
        r = yahoo.summary(s)
        if not r:
            continue
        ch = {}
        cap = v(r, 'summaryDetail', 'marketCap') or v(r, 'price', 'marketCap')
        if cap: ch['capi_mds'] = round(cap / 1e9, 2)
        fpe = v(r, 'defaultKeyStatistics', 'forwardPE') or v(r, 'summaryDetail', 'forwardPE')
        if fpe and fpe > 0: ch['per_prevu'] = round(fpe, 1)
        ed = (r.get('calendarEvents') or {}).get('earnings', {}).get('earningsDate') or []
        if ed and isinstance(ed[0], dict) and ed[0].get('raw'):
            ch['prochains_resultats'] = dt.datetime.utcfromtimestamp(ed[0]['raw']).date().isoformat()
        passe = u.get('prochains_resultats') and str(u['prochains_resultats'])[:10] <= today
        try:  # chiffre vérifié à la main sur 3 à 5 sources depuis moins de 100 jours : on n'y touche pas
            jj, mm_, aa = map(int, str(u.get('verifie', '')).split('/'))
            if (dt.date.today() - dt.date(aa, mm_, jj)).days < 100:
                passe = False
        except Exception:
            pass
        if passe:  # résultats publiés : on reprend les chiffres de l'exercice
            fd = r.get('financialData') or {}
            for k, src, f in (('marge_brute', 'grossMargins', 100), ('marge_nette', 'profitMargins', 100), ('roe', 'returnOnEquity', 100)):
                x = v(fd, src)
                if x is not None: ch[k] = round(x * f, 1)
            fcf, rev = v(fd, 'freeCashflow'), v(fd, 'totalRevenue')
            if fcf and rev: ch['cash_libre'] = round(fcf / rev * 100, 1)
            if fcf and cap: ch['rendement_cash'] = round(fcf / cap * 100, 1)
            de, ca, eb = v(fd, 'totalDebt'), v(fd, 'totalCash'), v(fd, 'ebitda')
            if de is not None and ca is not None and eb and eb > 0: ch['dette_ebitda'] = round((de - ca) / eb, 2)
        if ch:
            u.update(ch); u['maj_auto'] = today; nb += 1
        time.sleep(0.2)
    json.dump(U, open(D + 'univers.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(nb, 'sociétés mises à jour')


def derniers():
    """Dernier cours de chaque action qui a un historique dans data/h (chaque soir) -> data/h/derniers.json."""
    import maj
    out = {}
    for f in sorted(os.listdir(D + 'h')):
        if not f.endswith('.json') or f == 'derniers.json':
            continue
        cle = f[:-5].replace('_', '/', 1)
        q = maj.quote(maj.sym(cle) or '')
        if q:
            out[cle] = [q[0], q[1]]
        time.sleep(0.1)
    json.dump({'at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'px': out},
              open(D + 'h/derniers.json', 'w', encoding='utf-8'), separators=(',', ':'))
    print(len(out), 'derniers cours')


if __name__ == '__main__':
    a = sys.argv[1]
    if a == 'tickers': tickers()
    elif a == 'histo': histo(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif a == 'chiffres': chiffres()
    elif a == 'derniers': derniers()
