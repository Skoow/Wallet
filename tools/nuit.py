"""Travaux de nuit (GitHub Actions).

  python tools/nuit.py tickers  -> data/tickers.json : toutes les actions des bourses US (NYSE, Nasdaq, AMEX), de Toronto
                                   et des grandes bourses européennes (Paris, Amsterdam, Bruxelles, Lisbonne, Francfort, Londres,
                                   Zurich, Milan, Madrid, Stockholm, Oslo, Helsinki, Copenhague)
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
# bourses européennes : (bourse de la liste, pays de la société) -> code ; seulement les sociétés cotées chez elles
EUX = {('Euronext', 'FR'): 'EPA', ('Euronext', 'NL'): 'AMS', ('AMS', 'NL'): 'AMS', ('Euronext', 'BE'): 'EBR', ('Euronext', 'PT'): 'ELIS',
       ('XETRA', 'DE'): 'XETRA', ('LSE', 'GB'): 'LSE', ('SIX', 'CH'): 'SWX', ('Borsa Italiana', '*'): 'MIL', ('BME', 'ES'): 'BME',
       ('STO', 'SE'): 'STO', ('OSL', 'NO'): 'OSL', ('HEL', 'FI'): 'HEL', ('CPH', 'DK'): 'CPH'}
SUF = {'EPA': '.PA', 'AMS': '.AS', 'EBR': '.BR', 'ELIS': '.LS', 'XETRA': '.DE', 'LSE': '.L', 'SWX': '.SW', 'MIL': '.MI', 'BME': '.MC',
       'STO': '.ST', 'OSL': '.OL', 'HEL': '.HE', 'CPH': '.CO', 'TSX': '.TO', 'US': ''}
DEV = {'EPA': 'EUR', 'AMS': 'EUR', 'EBR': 'EUR', 'ELIS': 'EUR', 'XETRA': 'EUR', 'MIL': 'EUR', 'BME': 'EUR', 'HEL': 'EUR',
       'LSE': 'GBp', 'SWX': 'CHF', 'STO': 'SEK', 'OSL': 'NOK', 'CPH': 'DKK', 'TSX': 'CAD', 'US': 'USD'}
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
        if x['asset_type'] != 'Stock':
            continue
        t = x['ticker'].strip()
        if x['exchange'] == 'TSX':
            out['TSX:' + t] = [t, clean(x['name']), 'TSX', SEC.get(x['stock_sector'], ''), None, None, x['country'] or 'Canada']
            continue
        ex = EUX.get((x['exchange'], x['country_code'])) or EUX.get((x['exchange'], '*'))
        if not ex or not t or BAD.search(x['name']) or re.search(r'[\^/]', t):
            continue
        out[ex + ':' + t] = [t, clean(x['name']), ex, SEC.get(x['stock_sector'], ''), None, None, x['country'] or '']
    L = sorted(out.values(), key=lambda r: (-(r[4] or 0), r[0]))
    if len(L) > 3000:
        json.dump(L, open(D + 'tickers.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(len(L), 'tickers')


def cle_of(t, ex):
    t2 = t.lower().replace('.', '-').replace(' ', '-')
    return 's/' + t2 if ex == 'US' else 'a/' + ex.lower() + '-' + t2


def ysym(t, ex):
    return t.replace('.', '-').replace(' ', '-') + SUF.get(ex, '')


def fichier(cle):
    return D + 'h/' + cle.replace('/', '_') + '.json'


def histo(limite=None):
    os.makedirs(D + 'h', exist_ok=True)
    L = json.load(open(D + 'tickers.json', encoding='utf-8'))
    H0 = json.load(open(D + 'hebdo.json', encoding='utf-8'))
    d0 = dt.date.fromisoformat(H0[0]['debut']); n = len(H0[0]['prix'])
    weeks = [d0 + dt.timedelta(weeks=i) for i in range(n)]
    deja = {r['cle'] for r in json.load(open(D + 'prix.json', encoding='utf-8'))}
    t_fin = time.time() + float(os.environ.get('BUDGET_MIN', '250')) * 60
    AGE = {}
    def age(r):  # fichier absent = prioritaire ; sinon le plus ancien d'abord (date 'maj' écrite dans le fichier)
        c = cle_of(r[0], r[2])
        if c not in AGE:
            try: AGE[c] = dt.date.fromisoformat(json.load(open(fichier(c), encoding='utf-8')).get('maj', '2000-01-01')).toordinal()
            except Exception: AGE[c] = -1
        return AGE[c]
    todo = [r for r in L if (r[2] != 'US' or (r[4] or 0) >= 0.05 or r[5]) and cle_of(r[0], r[2]) not in deja]
    auj = dt.date.today().toordinal()
    todo = [r for r in todo if age(r) < 0 or auj - age(r) > 20]
    todo.sort(key=age)
    if limite: todo = todo[:limite]
    ok = 0
    for t, nom, ex, *_ in todo:
        if time.time() > t_fin:
            print('budget de temps atteint'); break
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
            spl = [[dt.datetime.utcfromtimestamp(int(x['date'])).date().isoformat(), round(x['numerator'] / x['denominator'], 6)]
                   for x in ((m.get('events') or {}).get('splits') or {}).values() if x.get('denominator')]
            dvs = sorted([dt.datetime.utcfromtimestamp(int(x['date'])).date().isoformat(), round(float(x['amount']), 6)]
                         for x in ((m.get('events') or {}).get('dividends') or {}).values() if x.get('amount'))[-60:]
            o = {'cle': cle, 'ticker': t, 'nom': nom, 'splits': sorted(spl), 'divs': dvs, 'devise': (m.get('meta') or {}).get('currency') or DEV.get(ex, 'USD'),
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
    for s_, (p, t, pc) in q.items():
        if s_ in sy:
            out[sy[s_]] = [round(p, 4), dt.datetime.utcfromtimestamp(t).date().isoformat()] + ([round(pc, 4)] if pc else [])
    for s_, c in sy.items():  # repli un par un pour ceux que le lot n'a pas rendus
        if c in out: continue
        r = maj.quote(s_)
        if r: out[c] = [r[0], r[1]] + ([r[3]] if r[3] else [])
        time.sleep(0.1)
    json.dump({'at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'px': out},
              open(D + 'h/derniers.json', 'w', encoding='utf-8'), separators=(',', ':'))
    print(len(out), 'derniers cours sur', len(sy))

VALO = ['quarterlyPeRatio', 'quarterlyForwardPeRatio', 'quarterlyPsRatio', 'quarterlyPbRatio', 'quarterlyPegRatio',
        'quarterlyEnterprisesValueEBITDARatio', 'quarterlyMarketCap']
FOND = ['annualTotalRevenue', 'annualNetIncome', 'annualGrossProfit', 'annualOperatingIncome', 'annualEBIT', 'annualInterestExpense',
        'annualDilutedEPS', 'annualFreeCashFlow', 'annualOperatingCashFlow', 'annualCapitalExpenditure', 'annualStockBasedCompensation',
        'annualRepurchaseOfCapitalStock', 'annualTotalDebt', 'annualCashAndCashEquivalents', 'annualDilutedAverageShares',
        'annualInvestedCapital', 'annualTaxRateForCalcs', 'annualStockholdersEquity', 'annualEBITDA']


def _med(a):
    a = sorted(x for x in a if x is not None and x > 0)
    if not a: return None
    m = len(a) // 2
    return a[m] if len(a) % 2 else (a[m - 1] + a[m]) / 2


SEC_UA = 'Portefeuille-Wallet/1.0 (github.com/Skoow/Wallet)'
_CIK = None


def sec_comptes(ticker):
    """Comptes annuels officiels (rapports 10-K déposés à la SEC, base XBRL « companyfacts ») pour une société américaine."""
    global _CIK
    try:
        if _CIK is None:
            req = urllib.request.Request('https://www.sec.gov/files/company_tickers.json', headers={'User-Agent': SEC_UA})
            _CIK = {v['ticker'].upper(): int(v['cik_str']) for v in json.load(urllib.request.urlopen(req, timeout=30)).values()}
        cik = _CIK.get(ticker.upper().replace('-', '.')) or _CIK.get(ticker.upper())
        if not cik: return None
        req = urllib.request.Request(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json', headers={'User-Agent': SEC_UA})
        F = json.load(urllib.request.urlopen(req, timeout=40)).get('facts', {}).get('us-gaap', {})
    except Exception as e:
        print(ticker, 'SEC', e); return None
    def serie(*tags, unit='USD'):
        for t in tags:
            u = ((F.get(t) or {}).get('units') or {}).get(unit) or []
            o = {}
            for x in u:
                if x.get('form') in ('10-K', '10-K/A') and x.get('fp') == 'FY' and x.get('fy') and x.get('start') and x.get('end'):
                    d0, d1 = dt.date.fromisoformat(x['start']), dt.date.fromisoformat(x['end'])
                    if 330 <= (d1 - d0).days <= 380: o[d1.year] = x['val']
            if o: return o
        return {}
    ca = serie('Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet')
    if len(ca) < 2: return None
    ni = serie('NetIncomeLoss'); op = serie('OperatingIncomeLoss'); ocf = serie('NetCashProvidedByUsedInOperatingActivities')
    cx = serie('PaymentsToAcquirePropertyPlantAndEquipment'); sbc = serie('ShareBasedCompensation', 'AllocatedShareBasedCompensationExpense')
    rb = serie('PaymentsForRepurchaseOfCommonStock'); gp = serie('GrossProfit')
    eps = serie('EarningsPerShareDiluted', unit='USD/shares'); sh = serie('WeightedAverageNumberOfDilutedSharesOutstanding', unit='shares')
    out = []
    for y in sorted(ca)[-5:]:
        c = ca[y]
        if not c: continue
        pc = lambda d: round(d[y] / c * 100, 1) if y in d and d[y] is not None else None
        fcf = (ocf[y] - cx.get(y, 0)) if y in ocf else None
        out.append({'annee': str(y), 'ca_mds': round(c / 1e9, 2), 'marge_brute': pc(gp), 'marge_op': pc(op), 'marge_nette': pc(ni),
                    'cash_libre': round(fcf / c * 100, 1) if fcf is not None else None, 'capex': pc(cx), 'sbc': pc(sbc), 'rachats': pc(rb),
                    'bpa': eps.get(y), 'actions_m': round(sh[y] / 1e6, 1) if y in sh else None})
    return out if len(out) >= 2 else None


def pro_un(s, us_ticker=None):
    """Toutes les données « pro » d'une société (symbole Yahoo). Retourne un dict, ou None."""
    today = dt.date.today().isoformat()
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
        icap, tax = r.get('annualInvestedCapital'), r.get('annualTaxRateForCalcs')
        if eb is not None and icap and icap > 0:
            c['roic'] = round(eb * (1 - (tax if tax is not None and 0 <= tax < 0.6 else 0.21)) / icap * 100, 1)
        eq = r.get('annualStockholdersEquity'); nib = r.get('annualNetIncome')
        if eq and eq > 0 and nib is not None: c['roe'] = round(nib / eq * 100, 1)
        ebd = r.get('annualEBITDA')
        if ebd and ebd > 0 and de is not None: c['dette_ebitda'] = round((de - (ch or 0)) / ebd, 2)
        c['bpa'] = r.get('annualDilutedEPS'); sh = r.get('annualDilutedAverageShares'); c['actions_m'] = round(sh / 1e6, 1) if sh else None
        comptes.append(c)
    if comptes: o['comptes'] = comptes
    q = yahoo.summary(s, 'earningsTrend,financialData,recommendationTrend,netSharePurchaseActivity,defaultKeyStatistics,assetProfile,price,summaryDetail')
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
        ap = q.get('assetProfile') or {}; prc = q.get('price') or {}; sd = q.get('summaryDetail') or {}; fd = q.get('financialData') or {}
        o['profil'] = {k: x for k, x in (('secteur', ap.get('sector')), ('industrie', ap.get('industry')), ('pays', ap.get('country')),
                                          ('employes', ap.get('fullTimeEmployees')), ('site', ap.get('website'))) if x}
        cap = v(prc, 'marketCap') or v(sd, 'marketCap')
        if cap: o['capi_mds'] = round(cap / 1e9, 2)
        if prc.get('currency'): o['devise'] = prc.get('currency')
        rat = {}
        for k2, src, f in (('marge_brute', 'grossMargins', 100), ('marge_nette', 'profitMargins', 100), ('roe', 'returnOnEquity', 100),
                           ('croissance_ca_1a', 'revenueGrowth', 100)):
            x = v(fd, src)
            if x is not None: rat[k2] = round(x * f, 1)
        fcf, rev = v(fd, 'freeCashflow'), v(fd, 'totalRevenue')
        if fcf and rev: rat['cash_libre'] = round(fcf / rev * 100, 1)
        if fcf and cap: rat['rendement_cash'] = round(fcf / cap * 100, 1)
        de, ca_, eb = v(fd, 'totalDebt'), v(fd, 'totalCash'), v(fd, 'ebitda')
        if de is not None and ca_ is not None and eb and eb > 0: rat['dette_ebitda'] = round((de - ca_) / eb, 2)
        fpe = v(ks, 'forwardPE') or v(sd, 'forwardPE')
        if fpe and fpe > 0: rat['per_prevu'] = round(fpe, 1)
        if rat: o['ratios'] = rat
    if us_ticker:
        sc = sec_comptes(us_ticker)
        if sc:
            ya = {c['annee']: c for c in o.get('comptes', [])}
            for c in sc:  # on garde la couverture des intérêts et la dette nette de Yahoo quand la SEC ne les donne pas
                y = ya.get(c['annee']) or {}
                for k in ('couverture_interets', 'dette_nette_mds', 'roic', 'roe', 'dette_ebitda', 'marge_brute'):
                    if c.get(k) is None and y.get(k) is not None: c[k] = y[k]
            o['comptes'] = sc; o['source_comptes'] = 'SEC (rapports annuels 10-K officiels)'
    if 'comptes' in o and 'source_comptes' not in o: o['source_comptes'] = 'Yahoo Finance'
    return o if len(o) > 1 else None


def pro(limite=None):
    """Données « pro » -> data/pro.json pour les sociétés suivies (chaque nuit),
       puis data/p/<clé>.json pour toutes les autres actions de la recherche, par roulement (les plus anciennes d'abord)."""
    import maj
    U = json.load(open(D + 'univers.json', encoding='utf-8'))
    try: OUT = json.load(open(D + 'pro.json', encoding='utf-8'))
    except Exception: OUT = {}
    n = 0
    for u in U:
        s = maj.sym(u['cle'])
        if not s or u['cle'].startswith('e/') or u.get('metal'):
            continue
        try:
            o = pro_un(s, u.get('ticker') if u['cle'].startswith('s/') else None)
            if o: OUT[u['cle']] = o; n += 1
        except Exception as e:
            print(u['cle'], 'pro', e)
        time.sleep(0.3)
    json.dump(OUT, open(D + 'pro.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(n, 'sociétés suivies')
    # roulement sur toutes les autres actions
    os.makedirs(D + 'p', exist_ok=True)
    t_fin = time.time() + float(os.environ.get('BUDGET_MIN', '90')) * 60
    suivies = {u['cle'] for u in U}
    L = [r for r in json.load(open(D + 'tickers.json', encoding='utf-8')) if cle_of(r[0], r[2]) not in suivies]
    def age(c):
        try: return dt.date.fromisoformat(json.load(open(D + 'p/' + c.replace('/', '_') + '.json', encoding='utf-8')).get('maj', '2000-01-01')).toordinal()
        except Exception: return -1
    auj = dt.date.today().toordinal()
    todo = [(age(cle_of(r[0], r[2])), -(r[4] or 0), r) for r in L]
    todo = [x for x in todo if x[0] < 0 or auj - x[0] > 30]
    todo.sort(key=lambda x: (x[0], x[1]))
    import threading
    from concurrent.futures import ThreadPoolExecutor
    lock = threading.Lock(); cpt = [0]
    def un(r):
        if time.time() > t_fin or (limite and cpt[0] >= limite): return
        c = cle_of(r[0], r[2])
        try:
            o = pro_un(ysym(r[0], r[2]), r[0] if r[2] == 'US' else None)
            json.dump(o or {'maj': dt.date.today().isoformat(), 'vide': True}, open(D + 'p/' + c.replace('/', '_') + '.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            with lock: cpt[0] += 1
        except Exception as e:
            print(c, 'pro', e)
        time.sleep(0.2)
    with ThreadPoolExecutor(max_workers=int(os.environ.get('PRO_FILS', '4'))) as ex:
        list(ex.map(un, [r for _, _, r in todo]))
    print(cpt[0], 'autres actions mises à jour,', max(0, len(todo) - cpt[0]), 'en attente')

def splits():
    """Divisions d'actions des 10 dernières années pour les actions suivies -> data/splits.json
       (la page corrige les quantités et prix des achats faits avant une division)."""
    import maj
    out, DV = {}, {}
    for r in json.load(open(D + 'prix.json', encoding='utf-8')):
        s = maj.sym(r['cle'])
        if not s or r['cle'][:2] in ('c/', 'm/', 'x/', 'e/'): continue
        try:
            m = yahoo.chart(s, '10y', '3mo')
            sp = ((m or {}).get('events') or {}).get('splits') or {}
            L = sorted([dt.datetime.utcfromtimestamp(int(x['date'])).date().isoformat(), round(x['numerator'] / x['denominator'], 6)] for x in sp.values() if x.get('denominator'))
            if L: out[r['cle']] = L
            dv = ((m or {}).get('events') or {}).get('dividends') or {}
            Ld = sorted([dt.datetime.utcfromtimestamp(int(x['date'])).date().isoformat(), round(float(x['amount']), 6)] for x in dv.values() if x.get('amount'))
            if Ld: DV[r['cle']] = Ld[-40:]
        except Exception as e:
            print(r['cle'], 'splits', e)
        time.sleep(0.15)
    json.dump(out, open(D + 'splits.json', 'w', encoding='utf-8'), separators=(',', ':'))
    json.dump(DV, open(D + 'divs.json', 'w', encoding='utf-8'), separators=(',', ':'))
    print(len(out), 'actions avec divisions,', len(DV), 'avec dividendes')


if __name__ == '__main__':
    a = sys.argv[1]
    if a == 'tickers': tickers()
    elif a == 'histo': histo(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif a == 'chiffres': chiffres()
    elif a == 'derniers': derniers()
    elif a == 'appliquer': appliquer()
    elif a == 'splits': splits()
    elif a == 'pro': pro(int(sys.argv[2]) if len(sys.argv) > 2 else None)
