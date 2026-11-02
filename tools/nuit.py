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
    todo = [r for r in L if (r[2] == 'TSX' or (r[4] or 0) >= 0.05 or r[5]) and cle_of(r[0], r[2]) not in deja]
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


PATCHF = os.environ.get('RUNNER_TEMP', '/tmp') + '/chiffres.json'


def chiffres():
    PATCH = {}
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
            ch['maj_auto'] = today; PATCH[u['cle']] = ch; nb += 1
        time.sleep(0.2)
    json.dump(PATCH, open(PATCHF, 'w', encoding='utf-8'), ensure_ascii=False)
    print(nb, 'sociétés à mettre à jour (appliqué à l\'enregistrement)')


def appliquer():
    """Applique les chiffres du soir sur la version la plus récente de univers.json (évite d'écraser les modifications du jour)."""
    if not os.path.exists(PATCHF):
        return
    PATCH = json.load(open(PATCHF, encoding='utf-8'))
    U = json.load(open(D + 'univers.json', encoding='utf-8'))
    for u in U:
        if u['cle'] in PATCH: u.update(PATCH[u['cle']])
    json.dump(U, open(D + 'univers.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(len(PATCH), 'sociétés mises à jour')


def derniers():
    """Dernier cours de chaque action qui a un historique dans data/h (chaque soir, par lots) -> data/h/derniers.json."""
    import maj
    cles = [f[:-5].replace('_', '/', 1) for f in sorted(os.listdir(D + 'h')) if f.endswith('.json') and f != 'derniers.json']
    sy = {maj.sym(c): c for c in cles if maj.sym(c)}
    q = yahoo.quotes(list(sy))
    out = {}
    for s_, (p, t) in q.items():
        if s_ in sy:
            out[sy[s_]] = [round(p, 4), dt.datetime.utcfromtimestamp(t).date().isoformat()]
    for s_, c in sy.items():  # repli un par un pour ceux que le lot n'a pas rendus
        if c in out: continue
        r = maj.quote(s_)
        if r: out[c] = [r[0], r[1]]
        time.sleep(0.1)
    json.dump({'at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'px': out},
              open(D + 'h/derniers.json', 'w', encoding='utf-8'), separators=(',', ':'))
    print(len(out), 'derniers cours sur', len(sy))

VALO = ['quarterlyPeRatio', 'quarterlyForwardPeRatio', 'quarterlyPsRatio', 'quarterlyPbRatio', 'quarterlyPegRatio',
        'quarterlyEnterprisesValueEBITDARatio', 'quarterlyMarketCap']
FOND = ['annualTotalRevenue', 'annualNetIncome', 'annualGrossProfit', 'annualOperatingIncome', 'annualEBIT', 'annualInterestExpense',
        'annualDilutedEPS', 'annualFreeCashFlow', 'annualOperatingCashFlow', 'annualCapitalExpenditure', 'annualStockBasedCompensation',
        'annualRepurchaseOfCapitalStock', 'annualTotalDebt', 'annualCashAndCashEquivalents', 'annualDilutedAverageShares']


def _med(a):
    a = sorted(x for x in a if x is not None and x > 0)
    if not a: return None
    m = len(a) // 2
    return a[m] if len(a) % 2 else (a[m - 1] + a[m]) / 2


def pro(limite=None):
    """Données « pro » par société -> data/pro.json : historique de valorisation (PER sur 5 ans), tendance des comptes,
       révisions des analystes, achats/ventes des dirigeants. Ne touche pas univers.json."""
    import maj
    U = json.load(open(D + 'univers.json', encoding='utf-8'))
    try: OUT = json.load(open(D + 'pro.json', encoding='utf-8'))
    except Exception: OUT = {}
    today = dt.date.today().isoformat(); n = 0
    for u in U:
        s = maj.sym(u['cle'])
        if not s or u['cle'].startswith('e/') or u.get('metal'):
            continue
        if limite and n >= limite: break
        try:
            o = {'maj': today}
            TS = yahoo.timeseries(s, VALO)
            pe = [x for d, x in TS.get('quarterlyPeRatio', []) if 0 < x < 200]
            if pe:
                o['per'] = {'actuel': round(pe[-1], 1), 'mediane5a': round(_med(pe), 1), 'min5a': round(min(pe), 1), 'max5a': round(max(pe), 1), 'n': len(pe),
                            'serie': [[d, round(x, 1)] for d, x in TS.get('quarterlyPeRatio', []) if 0 < x < 200]}
            fpe = [x for d, x in TS.get('quarterlyForwardPeRatio', []) if 0 < x < 200]
            if fpe: o['per_prevu_mediane5a'] = round(_med(fpe), 1)
            ps = [x for d, x in TS.get('quarterlyPsRatio', []) if 0 < x < 100]
            if ps: o['ps'] = {'actuel': round(ps[-1], 2), 'mediane5a': round(_med(ps), 2)}
            ev = [x for d, x in TS.get('quarterlyEnterprisesValueEBITDARatio', []) if 0 < x < 300]
            if ev: o['ev_ebitda'] = {'actuel': round(ev[-1], 1), 'mediane5a': round(_med(ev), 1)}
            peg = [x for d, x in TS.get('quarterlyPegRatio', []) if 0 < x < 20]
            if peg: o['peg'] = round(peg[-1], 2)
            f = yahoo.timeseries(s, FOND)
            yrs = {}
            for t, rows in f.items():
                for d, x in rows:
                    yrs.setdefault(d[:4], {})[t] = x
            comptes = []
            for y in sorted(yrs)[-5:]:
                r = yrs[y]; ca = r.get('annualTotalRevenue')
                if not ca: continue
                c = {'annee': y, 'ca_mds': round(ca / 1e9, 2)}
                def pc(k):
                    x = r.get(k); return round(x / ca * 100, 1) if x is not None else None
                c['marge_brute'] = pc('annualGrossProfit'); c['marge_op'] = pc('annualOperatingIncome'); c['marge_nette'] = pc('annualNetIncome')
                c['cash_libre'] = pc('annualFreeCashFlow'); c['capex'] = pc('annualCapitalExpenditure'); c['sbc'] = pc('annualStockBasedCompensation')
                if c['capex'] is not None: c['capex'] = abs(c['capex'])
                rb = r.get('annualRepurchaseOfCapitalStock'); c['rachats'] = round(abs(rb) / ca * 100, 1) if rb is not None else None
                eb, ie = r.get('annualEBIT'), r.get('annualInterestExpense')
                c['couverture_interets'] = round(eb / ie, 1) if eb and ie and ie > 0 else None
                de, ch = r.get('annualTotalDebt'), r.get('annualCashAndCashEquivalents')
                c['dette_nette_mds'] = round((de - (ch or 0)) / 1e9, 2) if de is not None else None
                c['bpa'] = r.get('annualDilutedEPS'); sh = r.get('annualDilutedAverageShares'); c['actions_m'] = round(sh / 1e6, 1) if sh else None
                comptes.append(c)
            if comptes: o['comptes'] = comptes
            q = yahoo.summary(s, 'earningsTrend,financialData,recommendationTrend,netSharePurchaseActivity,insiderTransactions,defaultKeyStatistics')
            if q:
                et = (q.get('earningsTrend') or {}).get('trend') or []
                cur = next((t for t in et if t.get('period') == '0y'), None); nxt = next((t for t in et if t.get('period') == '+1y'), None)
                rev = {}
                for lab, t in (('an', cur), ('an_suivant', nxt)):
                    if not t: continue
                    e = t.get('epsTrend') or {}; r_ = t.get('epsRevisions') or {}
                    now_, m3 = v(e, 'current'), v(e, '90daysAgo')
                    rev[lab] = {'bpa': now_, 'bpa_90j': m3, 'revision_90j_pct': round((now_ / m3 - 1) * 100, 1) if now_ and m3 else None,
                                'hausses_30j': v(r_, 'upLast30days'), 'baisses_30j': v(r_, 'downLast30days'),
                                'croissance': round(v(t, 'growth') * 100, 1) if v(t, 'growth') is not None else None}
                if rev: o['revisions'] = rev
                fd = q.get('financialData') or {}
                o['analystes'] = {'n': v(fd, 'numberOfAnalystOpinions'), 'cible_moyenne': v(fd, 'targetMeanPrice'), 'cible_basse': v(fd, 'targetLowPrice'),
                                  'cible_haute': v(fd, 'targetHighPrice'), 'avis': fd.get('recommendationKey'), 'cours': v(fd, 'currentPrice')}
                ns = q.get('netSharePurchaseActivity') or {}
                if ns: o['inities'] = {'periode': ns.get('period'), 'achats': v(ns, 'buyInfoShares'), 'ventes': v(ns, 'sellInfoShares'),
                                       'net': v(ns, 'netInfoShares'), 'net_pct': round(v(ns, 'netPercentInsiderShares') * 100, 2) if v(ns, 'netPercentInsiderShares') is not None else None,
                                       'part_inities_pct': round(v(ns, 'totalInsiderShares') / v(q.get('defaultKeyStatistics') or {}, 'sharesOutstanding') * 100, 2) if v(ns, 'totalInsiderShares') and v(q.get('defaultKeyStatistics') or {}, 'sharesOutstanding') else None}
                ks = q.get('defaultKeyStatistics') or {}
                o['bpa_12m'] = v(ks, 'trailingEps'); o['bpa_prevu'] = v(ks, 'forwardEps'); o['peg_yahoo'] = v(ks, 'pegRatio')
                o['short_pct'] = round(v(ks, 'shortPercentOfFloat') * 100, 1) if v(ks, 'shortPercentOfFloat') is not None else None
            if len(o) > 1:
                OUT[u['cle']] = o; n += 1
        except Exception as e:
            print(u['cle'], 'pro', e)
        time.sleep(0.4)
    json.dump(OUT, open(D + 'pro.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(n, 'sociétés pro')


if __name__ == '__main__':
    a = sys.argv[1]
    if a == 'tickers': tickers()
    elif a == 'histo': histo(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif a == 'chiffres': chiffres()
    elif a == 'derniers': derniers()
    elif a == 'appliquer': appliquer()
    elif a == 'pro': pro(int(sys.argv[2]) if len(sys.argv) > 2 else None)
