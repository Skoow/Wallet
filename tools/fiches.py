"""Fiches automatiques pour TOUTES les actions connues (data/tickers.json), sans clé ni secret.

    python tools/fiches.py [minutes] [cle1,cle2,...]

Pour chaque action, écrit data/f/<cle>.json :
  - ventes par pays : extraites du dernier rapport annuel (10-K / 20-F / 40-F) déposé à la SEC,
    lu sur la copie de Yahoo (données balisées XBRL « StatementGeographicalAxis ») ;
    sinon estimation par le pays du siège, signalée comme telle ;
  - vérification automatique : titres d'actualité récents (mots d'alerte : fraude, enquête, procès,
    faillite…), note de gouvernance ISS, achats/ventes des dirigeants, prochains résultats, liens des dépôts officiels.
Les alertes d'actualité sont gardées 12 mois d'une nuit à l'autre.
Ordre : actions du portefeuille conseillé et de la liste de base d'abord, puis les plus grosses ;
une fiche est refaite tous les 3 jours (FICHES_JOURS) ; le rapport annuel n'est relu que s'il a changé."""
import json, os, re, sys, time, html, datetime as dt, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yahoo, nuit

D = 'data/'
OUT = D + 'f/'
os.makedirs(OUT, exist_ok=True)
AUJ = dt.date.today()

# ---------- ventes par pays (XBRL du rapport annuel) ----------
EUR = set('GB DE FR IT ES NL IE CH SE BE DK NO FI AT PL PT LU GR CZ HU RO IL TR'.split())
ASI = set('CN JP KR TW IN SG HK AU NZ MY TH ID PH VN'.split())
CONCEPTS = ('Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'RevenueFromContractWithCustomerIncludingAssessedTax',
            'SalesRevenueNet', 'Revenue', 'RevenueFromContractsWithCustomers', 'OperatingRevenue')


def zone(m):
    """Zone d'un membre XBRL géographique : US, CA, EU, AS, AU(tres), AM (Amériques, agrégat), IN(ternational, agrégat)."""
    if m.startswith('country:'):
        c = m.split(':')[1]
        return 'US' if c == 'US' else 'CA' if c == 'CA' else 'EU' if c in EUR else 'AS' if c in ASI else 'AU'
    n = m.split(':')[-1].lower()
    if re.search(r'nonus|international|foreign|othercountr|restofworld|outsideunitedstates|outsideofunitedstates|nondomestic|outsideus', n): return 'IN'
    if re.search(r'unitedstates|domestic|^usmember', n): return 'US'
    if 'canada' in n: return 'CA'
    if re.search(r'emea|europe|unitedkingdom|germany|france|ireland|netherlands|switzerland', n): return 'EU'
    if re.search(r'asia|pacific|apac|china|japan|australia|taiwan|korea|india|singapore', n): return 'AS'
    if re.search(r'latinamerica|southamerica|middleeast|africa|brazil|mexico', n): return 'AU'
    if re.search(r'northamerica|americas', n): return 'AM'
    return None


def geo_xbrl(htm):
    ctx = {}
    for m in re.finditer(r'<xbrli:context\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</xbrli:context>', htm, re.S):
        cid, body = m.group(1), m.group(2)
        dims = re.findall(r'<xbrldi:explicitMember[^>]*dimension="([^"]+)"[^>]*>\s*([^<\s]+)\s*<', body)
        sd = re.search(r'<xbrli:startDate>([^<]+)<', body); ed = re.search(r'<xbrli:endDate>([^<]+)<', body)
        if not (sd and ed): continue
        try:
            d0, d1 = dt.date.fromisoformat(sd.group(1)[:10]), dt.date.fromisoformat(ed.group(1)[:10])
        except ValueError:
            continue
        if not 330 <= (d1 - d0).days <= 380: continue
        if not dims:
            ctx[cid] = (d1, None)
        elif len(dims) == 1 and dims[0][0].endswith('StatementGeographicalAxis'):
            ctx[cid] = (d1, dims[0][1])
    facts = {}
    for m in re.finditer(r'<ix:nonFraction\b([^>]*)>(.*?)</ix:nonFraction>', htm, re.S):
        a = m.group(1)
        nm = re.search(r'\bname="[^":]+:([^"]+)"', a); cr = re.search(r'\bcontextRef="([^"]+)"', a)
        if not (nm and cr) or nm.group(1) not in CONCEPTS or cr.group(1) not in ctx: continue
        txt = re.sub(r'<[^>]+>', '', m.group(2)).replace(',', '').strip()
        try: v = float(txt)
        except ValueError: continue
        sc = re.search(r'\bscale="(-?\d+)"', a)
        v *= 10 ** int(sc.group(1)) if sc else 1
        if re.search(r'\bsign="-"', a): v = -v
        d1, mem = ctx[cr.group(1)]
        facts.setdefault((nm.group(1), d1), {})[mem] = v
    best = None
    for (c, d1), mp in facts.items():
        geo = {k: v for k, v in mp.items() if k}
        if len(geo) < 2: continue
        key = (d1, len(geo))
        if not best or key > best[0]: best = (key, c, d1, mp)
    if not best: return None
    _, concept, d1, mp = best
    tot = mp.get(None) or 0
    Z = {}
    for k, v in mp.items():
        if k and v > 0:
            z = zone(k)
            if z: Z.setdefault(z, []).append((k, v))
    s = {z: sum(v for _, v in L) for z, L in Z.items()}
    if not tot: tot = sum(v for z, v in s.items() if z not in ('AM', 'IN')) or sum(s.values())
    if not tot: return None
    est = []
    out = {'États-Unis': s.get('US', 0), 'Canada': s.get('CA', 0), 'Europe': s.get('EU', 0), 'Asie': s.get('AS', 0), 'Autres': s.get('AU', 0)}
    if 'AM' in s:  # agrégat Amériques
        if 'US' in s:
            out['Autres'] += max(0, s['AM'] - s['US'] - s.get('CA', 0)); est.append('le reste des Amériques est classé en « reste du monde »')
        else:
            out['États-Unis'] += s['AM']; est.append('la zone Amériques est comptée comme États-Unis')
    reste = tot - sum(out.values())
    if reste > tot * 0.03:
        if 'IN' in s or reste > 0:
            out['Europe'] += reste * 0.5; out['Asie'] += reste * 0.35; out['Autres'] += reste * 0.15
            est.append('les ventes « hors États-Unis » non détaillées sont réparties à 50 % Europe, 35 % Asie, 15 % reste du monde')
    T = sum(out.values())
    if T <= 0: return None
    pc = {k: round(v / T * 100) for k, v in out.items()}
    d = 100 - sum(pc.values()); kmax = max(pc, key=pc.get); pc[kmax] += d
    mn = lambda v: f'{v / 1e6:,.0f}'.replace(',', ' ') + ' M'
    det = ', '.join(f'{k.split(":")[-1].replace("Member", "")} {mn(v)}' for z, L in Z.items() for k, v in L)
    return {'geo': pc, 'annee_geo': d1.isoformat(),
            'note_geo': f'Extrait automatiquement du rapport annuel (exercice clos le {d1.strftime("%d/%m/%Y")}, chiffre d’affaires {mn(tot)})'
                        + (f' : {det}' if det else '') + ('. Estimé : ' + ' ; '.join(est) if est else '') + '.'}


# ---------- vérification automatique ----------
ROUGE = r'\bfraud|indict|charged by (the )?sec|sec charges|accounting irregular|restat(e|ement)s? (its|financial)|bankrupt|chapter 11|ponzi|embezzl|going concern|delist|hindenburg|muddy waters|spruce point|wolfpack|grizzly research|short[- ]seller report'
ORANGE = r'\binvestigat|\bprobe\b|subpoena|lawsuit|\bsued\b|\bsues\b|class action|recall|antitrust|\bfined?\b|penalt|cuts? (its )?(guidance|outlook|forecast)|lowers? (guidance|outlook)|(ceo|chief executive|cfo).{0,30}(resign|steps? down|depart|ousted|fired)|data breach|cyberattack|warning letter|downgrade'


def verif(sym, prev, nom=''):
    s = yahoo.summary(sym, 'assetProfile,secFilings,netSharePurchaseActivity,calendarEvents') or {}
    try:
        n = yahoo.get('https://query1.finance.yahoo.com/v1/finance/search?q=' + urllib.parse.quote(sym) + '&quotesCount=0&newsCount=20') or {}
    except Exception:
        n = {}
    base = sym.split('.')[0].upper()
    STOP = {'the', 'inc', 'corp', 'corporation', 'company', 'co', 'group', 'holdings', 'ltd', 'plc', 'sa', 'se', 'ag', 'nv', 'class', 'and', 'de', 'la', 'le', 'international', 'american', 'national', 'first', 'global', 'energy', 'financial', 'systems', 'technologies'}
    w = [x for x in re.split(r'[^\w&-]+', (nom or '').split(' · ')[0]) if x and x.lower() not in STOP and len(x) > 2]
    mots = ([w[0]] if w else []) + [base]
    old = [f for f in (prev.get('alertes') or []) if f.get('d', '') >= (AUJ - dt.timedelta(days=365)).isoformat()]
    vus = {f['l'] for f in old}
    for it in n.get('news') or []:
        rel = [x.upper() for x in it.get('relatedTickers') or []]
        if sym.upper() not in rel and base not in rel: continue
        if len(rel) > 2: continue
        t = it.get('title') or ''; l = it.get('link') or ''
        if mots and not any(re.search(r'\b' + re.escape(m) + r'\b', t, re.I) for m in mots): continue  # le titre doit nommer la société
        if not l or l in vus: continue
        niv = 'rouge' if re.search(ROUGE, t, re.I) else 'orange' if re.search(ORANGE, t, re.I) else None
        if not niv: continue
        d = dt.datetime.fromtimestamp(it.get('providerPublishTime') or time.time(), dt.timezone.utc).date().isoformat()
        old.append({'d': d, 't': t[:200], 'l': l, 'n': niv, 'src': it.get('publisher')}); vus.add(l)
    old.sort(key=lambda f: f['d'], reverse=True); old = old[:12]
    ap = s.get('assetProfile') or {}
    gv = {k: ap.get(k) for k in ('overallRisk', 'auditRisk', 'boardRisk', 'compensationRisk', 'shareHolderRightsRisk') if ap.get(k) is not None}
    ns = s.get('netSharePurchaseActivity') or {}
    raw = lambda k: ((ns.get(k) or {}).get('raw'))
    ini = {'achats': raw('buyInfoCount'), 'ventes': raw('sellInfoCount'), 'net_pct': raw('netPercentInsiderShares')}
    ev = (s.get('calendarEvents') or {}).get('earnings') or {}
    pr = None
    if ev.get('earningsDate') and not ev.get('isEarningsDateEstimate'):
        try: pr = ev['earningsDate'][0]['fmt']
        except Exception: pr = None
    fil = (s.get('secFilings') or {}).get('filings') or []
    rouges = [f for f in old if f['n'] == 'rouge']; oranges = [f for f in old if f['n'] == 'orange']
    raisons = []
    if rouges or oranges: raisons.append(f'{len(rouges) + len(oranges)} titre(s) d’actualité à lire sur 12 mois (mots relevés : fraude, enquête, procès, faillite, rappel, prévisions baissées…) ; un relevé automatique peut se tromper, lis le titre avant de conclure')
    if gv.get('overallRisk', 0) >= 8: raisons.append(f'note de gouvernance ISS {gv["overallRisk"]}/10, fréquente quand un fondateur ou un actionnaire contrôle la société (information)')
    if not rouges and not oranges: raisons.insert(0, 'aucune alerte dans l’actualité récente (fraude, enquête, procès, faillite, rappel)')
    verdict = 'à surveiller' if (rouges or oranges) else 'propre'  # jamais de drapeau rouge automatique : il faut lire
    src = [f['l'] for f in old[:4]] + [x['edgarUrl'] for x in fil[:2] if x.get('edgarUrl')] + ['https://finance.yahoo.com/quote/' + sym + '/news/']
    return s, {'verdict': verdict, 'verifie': AUJ.strftime('%d/%m/%Y'), 'auto': True,
               'raison_verif': 'Vérification automatique : ' + ' ; '.join(raisons) + '.', 'alertes': old, 'gouvernance': gv, 'initiés': ini,
               'sources_verif': src, 'prochains_resultats': pr}, fil, ap


def rapport(fil):
    for f in fil:
        if f.get('type') in ('10-K', '20-F', '40-F'):
            for e in f.get('exhibits') or []:
                if e.get('type') == f['type'] and e.get('url'): return f, e['url']
    return None, None


def un(cle, sym, prev, nom=''):
    s, v, fil, ap = verif(sym, prev, nom)
    o = {'cle': cle, 'maj': AUJ.isoformat(), **v}
    f, url = rapport(fil)
    if url and prev.get('src_geo') == url and prev.get('geo'):
        for k in ('geo', 'note_geo', 'annee_geo', 'src_geo'): o[k] = prev[k]
    elif url:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            htm = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')
            g = geo_xbrl(htm)
            if g: o.update(g); o['src_geo'] = url
        except Exception as e:
            print(cle, 'rapport', e)
    if 'geo' not in o:
        P = {'United States': 'États-Unis', 'Canada': 'Canada'}
        c = ap.get('country') or ''
        if c:
            z = P.get(c) or ('Europe' if c in ('United Kingdom', 'Germany', 'France', 'Switzerland', 'Netherlands', 'Ireland', 'Italy', 'Spain', 'Sweden', 'Denmark', 'Norway', 'Finland', 'Belgium', 'Austria', 'Luxembourg', 'Portugal')
                              else 'Asie' if c in ('China', 'Japan', 'Taiwan', 'South Korea', 'India', 'Singapore', 'Hong Kong', 'Australia') else 'Autres')
            o['geo_siege'] = z
            o['note_geo'] = f'Pas de rapport annuel balisé disponible : seul le pays du siège est connu ({c}). Ventes par pays inconnues.'
    if fil: o['depots'] = [{'d': x.get('date'), 't': x.get('type'), 'l': x.get('edgarUrl')} for x in fil[:5]]
    return o


def main():
    mins = float(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 40
    only = [c.strip() for c in (sys.argv[2] if len(sys.argv) > 2 else '').split(',') if c.strip()]
    t_fin = time.time() + mins * 60
    L = json.load(open(D + 'tickers.json', encoding='utf-8'))
    rows = {nuit.cle_of(r[0], r[2]): r for r in L}
    prio = set()
    try: prio |= set(json.load(open(D + 'params.json', encoding='utf-8')).get('choix') or [])
    except Exception: pass
    try: prio |= {u['cle'] for u in json.load(open(D + 'univers.json', encoding='utf-8'))}
    except Exception: pass
    def age(c):
        try: return (AUJ - dt.date.fromisoformat(json.load(open(OUT + c.replace('/', '_') + '.json', encoding='utf-8'))['maj'])).days
        except Exception: return 9999
    todo = only or sorted((c for c in rows if age(c) >= int(os.environ.get('FICHES_JOURS', '3'))), key=lambda c: (c not in prio, -(rows[c][4] or 0)))
    import threading
    from concurrent.futures import ThreadPoolExecutor
    lock = threading.Lock(); cpt = [0]
    def run(c):
        if time.time() > t_fin: return
        r = rows.get(c)
        if not r: return
        f = OUT + c.replace('/', '_') + '.json'
        try: prev = json.load(open(f, encoding='utf-8'))
        except Exception: prev = {}
        try:
            o = un(c, nuit.ysym(r[0], r[2]), {k: v for k, v in prev.items() if k != 'alertes'} if os.environ.get('FICHES_RAZ') else prev, r[1])
            json.dump(o, open(f, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            with lock: cpt[0] += 1
        except Exception as e:
            print(c, e)
        time.sleep(0.2)
    with ThreadPoolExecutor(max_workers=int(os.environ.get('FICHES_FILS', '6'))) as ex:
        list(ex.map(run, todo))
    fait = cpt[0]
    print(fait, 'fiches faites,', max(0, len(todo) - fait), 'en attente')


if __name__ == '__main__':
    import urllib.parse
    main()
