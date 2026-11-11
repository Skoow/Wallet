"""Mise à jour des cours pour la web app (lancé par GitHub Actions).

  python tools/maj.py boucle -> data/live.json chaque minute, de l'ouverture de Paris à la clôture américaine
  python tools/maj.py live   -> data/live.json : dernier cours des lignes, indices et changes (une fois)
  python tools/maj.py close  -> data/prix.json, data/hebdo.json, data/fx.json : clôture du jour (le soir)

Source : Yahoo Finance (graphique v8) ; changes BCE via frankfurter.app. En cas d'échec, l'ancienne valeur est gardée.
"""
import json, os, sys, time, subprocess, datetime as dt, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yahoo

D = 'data/'
UA = {'User-Agent': 'Mozilla/5.0 (portefeuille web app)'}
ETF = {'e/gld': 'GLD', 'e/slv': 'SLV', 'e/spy': 'SPY', 'e/qqq': 'QQQ', 'e/urth': 'URTH', 'e/ezu': 'EZU',
       'e/fxe': 'FXE', 'e/fxf': 'FXF', 'e/fxc': 'FXC', 'e/cac': '^FCHI',
       'e/agg': 'AGG', 'e/tlt': 'TLT', 'e/ief': 'IEF', 'e/shy': 'SHY', 'e/lqd': 'LQD', 'e/eunh': 'EUNH.DE', 'e/ieac': 'IEAC.L'}
EXCH = {'tsx': '.TO', 'epa': '.PA', 'swx': '.SW', 'xetra': '.DE', 'lse': '.L', 'ams': '.AS', 'mil': '.MI',
        'ebr': '.BR', 'elis': '.LS', 'bme': '.MC', 'sto': '.ST', 'osl': '.OL', 'hel': '.HE', 'cph': '.CO'}
# cryptos dont le symbole Yahoo n'est pas simplement XXX-USD
CSYM = {'ton': 'TON11419-USD', 'sui': 'SUI20947-USD', 'uni': 'UNI7083-USD', 'apt': 'APT21794-USD', 'arb': 'ARB11841-USD',
        'pepe': 'PEPE24478-USD', 'tao': 'TAO22974-USD', 'grt': 'GRT6719-USD', 'stx': 'STX4847-USD', 'mnt': 'MNT27075-USD',
        'pol': 'POL28321-USD', 'op': 'OP-USD', 'render': 'RENDER-USD', 'imx': 'IMX10603-USD', 'hype': 'HYPE32196-USD',
        'jup': 'JUP29210-USD', 'comp': 'COMP5692-USD', 'strk': 'STRK22691-USD', 'beam': 'BEAM28298-USD',
        'zk': 'ZK24091-USD', 'aero': 'AERO29270-USD', 'brett': 'BRETT29743-USD', 'popcat': 'POPCAT28782-USD', 'eigen': 'EIGEN-USD',
        'trump': 'TRUMP35336-USD', 's': 'S32684-USD', 'fartcoin': 'FARTCOIN-USD', 'virtual': 'VIRTUAL-USD', 'ena': 'ENA-USD'}


def sym(cle):
    if cle in ETF:
        return ETF[cle]
    k, rest = cle.split('/', 1)
    if k == 'c':  # cryptomonnaie, cotée en dollars
        return CSYM.get(rest, rest.upper() + '-USD')
    if k == 'm':  # matière première : contrat à terme le plus proche (ex. m/gc -> GC=F)
        return rest.upper() + '=F'
    if k == 'x':  # change (ex. x/gbpusd -> GBPUSD=X)
        return rest.upper() + '=X'
    if k == 's':
        return rest.upper().replace('.', '-')
    if k == 'a' and '-' in rest:
        ex, t = rest.split('-', 1)
        if ex in EXCH:
            return t.upper().replace('.', '-') + EXCH[ex]
    return None


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.load(r)
        except Exception as e:
            err = e
            time.sleep(1.5 * (i + 1))
    raise err


def quote(s):
    """(dernier cours, date de séance AAAA-MM-JJ, heure ISO) ou None."""
    r = yahoo.chart(s)
    if not r:
        return None
    m = r['meta']
    p, t = m.get('regularMarketPrice'), m.get('regularMarketTime')
    if not (p and t):
        return None
    tz = dt.timezone(dt.timedelta(seconds=m.get('gmtoffset', 0)))
    d = dt.datetime.fromtimestamp(t, tz)
    # clôture de la séance précédente, pour la variation du jour
    pc = None
    try:
        ts, cl = r.get('timestamp') or [], r['indicators']['quote'][0].get('close') or []
        for a, b in zip(ts, cl):
            if b and dt.datetime.fromtimestamp(a, tz).date() < d.date():
                pc = rp(b)
    except Exception:
        pc = None
    return rp(p), d.date().isoformat(), dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat(), pc


def rp(v):
    """Arrondi qui garde les tout petits cours (SHIB, PEPE…) : 6 chiffres significatifs sous 1."""
    v = float(v)
    return float(f'{v:.6g}') if abs(v) < 1 else round(v, 4)


def load(f):
    return json.load(open(D + f, encoding='utf-8'))


def save(f, o):
    json.dump(o, open(D + f, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))


def suivis():
    # toutes les actions proposées dans l'appli (chaque profil choisit les siennes), indices et changes
    ch = load('params.json').get('choix', [])
    tout = [r['cle'] for r in load('prix.json')]
    return list(dict.fromkeys(ch + ['e/gld', 'e/spy', 'e/urth', 'e/qqq', 'e/cac', 'e/fxe', 'e/fxc', 'e/fxf'] + tout))


def live(cles=None):
    P, H = load('prix.json'), load('hebdo.json')
    _, sh = roll(P, H, dt.date.today())
    ln = [len(r['prix']) for r in P]
    if sh or ln != [len(r['prix']) for r in load('prix.json')]:
        save('prix.json', P); save('hebdo.json', H); print('nouveau mois / nouvelle semaine')
    try:
        old = load('live.json')
    except Exception:
        old = {}
    px, at, vl = dict(old.get('px', {})), dict(old.get('heure', {})), dict(old.get('veille', {}))
    cl = list(cles or suivis())
    sy = {}
    for c in cl:
        s = sym(c)
        if s: sy[s] = c
    got = set()
    try:  # relevé groupé : 50 titres par appel (bien plus rapide qu'un par un)
        import yahoo
        for s_, (p, t, pc, er) in yahoo.quotes(list(sy)).items():
            c = sy.get(s_)
            if not c: continue
            px[c], at[c] = rp(p), dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat(timespec='seconds')
            if pc: vl[c] = rp(pc)
            got.add(c)
    except Exception as e:
        print('relevé groupé :', e)
    manq = [s_ for s_, c in sy.items() if c not in got]
    for s_ in manq[:80]:  # repli un par un, borné pour tenir la minute
        r = quote(s_)
        if r:
            c = sy[s_]
            px[c], at[c] = r[0], r[2]
            if r[3]:
                vl[c] = r[3]
    fx = dict(old.get('fx', {}))
    for pair, s in (('EURUSD', 'EURUSD=X'), ('EURCAD', 'EURCAD=X')):
        r = quote(s)
        if r:
            fx[pair] = r[0]
    if not px:
        print('aucun cours reçu, live.json inchangé'); return False
    out = {'at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'px': px, 'heure': at, 'veille': vl, 'fx': fx}
    if old.get('hs'):
        out['hs'] = old['hs']  # cours hors séance gardés entre deux relevés
    save('live.json', out)
    print(len(px), 'cours')
    return True


def mi(debut):
    y, m = map(int, debut.split('-')[:2]); return y * 12 + m - 1


def roll(P, H, today):
    """Ajoute le mois / la semaine qui commence (valeur = dernier cours connu). Renvoie le décalage en semaines."""
    cm = today.year * 12 + today.month - 1
    for r in P:
        last_m = mi(r['debut']) + len(r['prix']) - 1
        while last_m < cm:
            r['prix'].append(r['prix'][-1]); last_m += 1
    d0 = dt.date.fromisoformat(H[0]['debut']); n = len(H[0]['prix'])
    last_w = d0 + dt.timedelta(weeks=n - 1)
    cur_w = today - dt.timedelta(days=today.weekday())
    shift = max(0, (cur_w - last_w).days // 7)
    for h in H:
        for _ in range(shift):
            h['prix'].append(h['prix'][-1]); h['prix'].pop(0)
        if shift:
            h['debut'] = (dt.date.fromisoformat(h['debut']) + dt.timedelta(weeks=shift)).isoformat()
    return cur_w, shift


def close():
    P, H = load('prix.json'), load('hebdo.json')
    today = dt.date.today()
    cur_w, _ = roll(P, H, today)
    got, miss, Q = 0, [], {}
    for r in P:
        s = sym(r['cle'])
        q = quote(s) if s else None
        if q:
            Q[r['cle']] = q
        else:
            miss.append(r['cle'])
    for r in P:
        q = Q.get(r['cle'])
        if not q:
            continue
        d = dt.date.fromisoformat(q[1])
        ix = d.year * 12 + d.month - 1 - mi(r['debut'])
        if ix < 0 or ix >= len(r['prix']):
            continue
        ref = r['prix'][ix - 1] if ix > 0 else r['prix'][ix]
        if ref and abs(q[0] / ref - 1) > 0.25:
            miss.append(r['cle'] + ' (saut > 25 %)'); continue
        r['prix'][ix] = q[0]
        for j in range(ix + 1, len(r['prix'])):  # mois déjà ouverts depuis : partent de cette clôture
            r['prix'][j] = q[0]
        got += 1
    for h in H:
        q = Q.get(h['cle'])
        if q and dt.date.fromisoformat(q[1]) >= cur_w:
            h['prix'][-1] = q[0]
    save('prix.json', P); save('hebdo.json', H)
    try:
        j = get('https://api.frankfurter.app/latest?from=EUR&to=USD,CAD')
        save('fx.json', [{'paire': 'EURUSD', 'taux': j['rates']['USD'], 'date': j['date']},
                         {'paire': 'EURCAD', 'taux': j['rates']['CAD'], 'date': j['date']}])
    except Exception as e:
        print('changes non mis à jour :', e)
    print(got, 'séries mises à jour ; manquantes :', ', '.join(miss) or 'aucune')
    live()


def git_push(msg, paths):
    subprocess.run(['git', 'add'] + paths, check=False)
    if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode == 0:
        return
    subprocess.run(['git', 'commit', '-q', '-m', msg], check=False)
    for _ in range(4):
        r = subprocess.run(['git', 'pull', '-q', '--rebase', 'origin', 'main'], check=False)
        if r.returncode != 0:
            # conflit : on annule le rebase, on repart du serveur et on réécrit nos fichiers
            subprocess.run(['git', 'rebase', '--abort'], check=False)
            keep = {p: open(p, 'rb').read() for p in paths if os.path.exists(p)}
            subprocess.run(['git', 'fetch', '-q', 'origin', 'main'], check=False)
            subprocess.run(['git', 'reset', '-q', '--hard', 'origin/main'], check=False)
            for p, b in keep.items():
                open(p, 'wb').write(b)
            subprocess.run(['git', 'add'] + paths, check=False)
            if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode == 0:
                return
            subprocess.run(['git', 'commit', '-q', '-m', msg], check=False)
        if subprocess.run(['git', 'push', '-q', 'origin', 'main']).returncode == 0:
            return
        time.sleep(3)


def hors(cles=None):
    """Cours hors séance (avant l'ouverture / après la clôture américaine) -> live.json « hs » : {clé: [cours, variation %, 'pre'|'post', heure ISO]}."""
    cl = [c for c in (cles or suivis()) if c.startswith('s/') or c.startswith('e/')]
    sy = {}
    for c in cl:
        s_ = sym(c)
        if s_ and '.' not in s_ and '=' not in s_:
            sy[s_] = c
    try:
        old = load('live.json')
    except Exception:
        return False
    hs = {}
    c_ = yahoo.crumb()
    keys = list(sy)
    for i in range(0, len(keys), 50):
        part = keys[i:i + 50]
        q = urllib.parse.quote(','.join(part))
        j = None
        for host in ('query1', 'query2'):
            try:
                j = yahoo.get(f'https://{host}.finance.yahoo.com/v7/finance/quote?symbols={q}&fields=marketState,regularMarketTime,preMarketPrice,preMarketChangePercent,preMarketTime,postMarketPrice,postMarketChangePercent,postMarketTime' + (f'&crumb={urllib.parse.quote(c_)}' if c_ else ''))
                break
            except Exception:
                continue
        for r in ((j or {}).get('quoteResponse') or {}).get('result') or []:
            c = sy.get(r.get('symbol'))
            if not c:
                continue
            st = str(r.get('marketState') or '')
            if st == 'REGULAR':
                continue  # séance en cours : pas de cours hors séance à afficher
            rt = int(r.get('regularMarketTime') or 0)
            for k, lab in (('postMarket', 'post'), ('preMarket', 'pre')):
                p, pc, t = r.get(k + 'Price'), r.get(k + 'ChangePercent'), r.get(k + 'Time')
                if lab == 'pre' and st != 'PRE':
                    continue
                if lab == 'post' and (st == 'PRE' or not t or int(t) <= rt):
                    continue
                if p and pc is not None and t:
                    hs[c] = [rp(p), round(float(pc), 2), lab, dt.datetime.fromtimestamp(int(t), dt.timezone.utc).isoformat()]
                    break
        time.sleep(0.3)
    old['hs'] = hs
    save('live.json', old)
    print(len(hs), 'cours hors séance')
    return True


def grandes(cap=20):
    """Sociétés de plus de `cap` Md$ (suivies dans data/h) : leurs cours en séance couvrent les lignes ajoutées par l'utilisateur."""
    try:
        import nuit
        T = load('tickers.json')
        out = []
        for r in T:
            if (r[4] or 0) >= cap:
                c = nuit.cle_of(r[0], r[2])
                if os.path.exists('data/h/' + c.replace('/', '_') + '.json'):
                    out.append(c)
        return out
    except Exception as e:
        print('grandes sociétés :', e)
        return []


def petites(cap=0.3):
    """Toutes les sociétés de plus de `cap` Md$ (États-Unis, Toronto) avec un historique : couvrent les lignes ajoutées par chacun."""
    try:
        import nuit
        out = []
        for r in load('tickers.json'):
            if r[2] in ('US', 'TSX') and (r[4] or 0) >= cap:
                c = nuit.cle_of(r[0], r[2])
                if os.path.exists('data/h/' + c.replace('/', '_') + '.json'):
                    out.append(c)
        return out
    except Exception as e:
        print('petites sociétés :', e)
        return []


def live2(cles, deja=()):
    """data/live2.json : {cle: [cours, clôture de la veille, horodatage (s)]} pour les sociétés hors relevé minute. Écriture atomique."""
    dj = set(deja)
    sy = {}
    for c in cles:
        if c in dj:
            continue
        s_ = sym(c)
        if s_:
            sy[s_] = c
    try:
        old = load('live2.json').get('q', {})
    except Exception:
        old = {}
    q = dict(old)
    try:
        for s_, (p, t, pc, er) in yahoo.quotes(list(sy)).items():
            c = sy.get(s_)
            if c:
                q[c] = [rp(p), rp(pc) if pc else None, int(t)]
    except Exception as e:
        print('live2 :', e)
        return False
    tmp = D + 'live2.json.tmp'
    json.dump({'at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'q': q}, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, D + 'live2.json')
    print(len(q), 'cours (live2)')
    return True


def boucle(minutes=350, pas=60):
    """En séance : cours des lignes de base, indices et changes chaque minute ; toutes les actions toutes les 5 min."""
    fin = time.time() + minutes * 60
    base = list(dict.fromkeys(load('params.json').get('choix', []) + ['e/gld', 'e/spy', 'e/urth', 'e/qqq', 'e/cac', 'e/fxe', 'e/fxc', 'e/fxf']))
    GR = grandes()
    print(len(GR), 'grandes sociétés suivies en séance')
    PE = petites()
    print(len(PE), 'autres sociétés suivies toutes les 5 min (live2)')
    import threading
    th = None
    i = 0
    while time.time() < fin:
        t0 = time.time()
        h = dt.datetime.now(dt.timezone.utc)
        m = h.hour * 60 + h.minute
        if m > 21 * 60 + 20 or m < 6 * 60 + 45 or h.weekday() >= 5:
            break
        live(list(dict.fromkeys(suivis() + GR)) if i % 2 == 0 else base)
        if i % 5 == 0 and PE and (th is None or not th.is_alive()):
            th = threading.Thread(target=live2, args=(PE, set(suivis()) | set(GR)), daemon=True)
            th.start()
        if i % 5 == 0 and (m < 14 * 60 + 30 or m >= 20 * 60):
            try:
                hors()
            except Exception as e:
                print('hors séance :', e)
        git_push('Cours ' + h.strftime('%H:%M'), ['data/live.json', 'data/prix.json', 'data/hebdo.json'] + (['data/live2.json'] if os.path.exists(D + 'live2.json') else []))
        i += 1
        time.sleep(max(5, pas - (time.time() - t0)))


def relais(minutes=345):
    """Tâche relais (~6 h), relancée par le workflow à sa fin : ne dépend plus des déclenchements planifiés de GitHub,
    qui arrivent avec des heures de retard. En semaine 06:45-21:20 UTC : cours chaque minute ; 21:25 : clôtures ;
    jusqu'à 01:00 UTC : cours après séance toutes les 15 min. Le reste du temps : attente."""
    fin = time.time() + minutes * 60
    fait = None
    while time.time() < fin - 120:
        h = dt.datetime.now(dt.timezone.utc)
        m, wd = h.hour * 60 + h.minute, h.weekday()
        if wd < 5 and 6 * 60 + 45 <= m <= 21 * 60 + 20:
            boucle(max(1, int((fin - time.time()) / 60) - 2))
            continue
        if wd < 5 and m > 21 * 60 + 20 and fait != h.date():
            try:
                close(); hors()
            except Exception as e:
                print('clôture :', e)
            git_push('Clôture ' + h.strftime('%Y-%m-%d'), ['data/live.json', 'data/prix.json', 'data/hebdo.json', 'data/fx.json'])
            fait = h.date()
            continue
        apres = (wd < 5 and m > 21 * 60 + 20) or (m < 60 and (wd - 1) % 7 < 5)
        if apres and m % 15 == 0:
            try:
                hors(); git_push('Après séance ' + h.strftime('%H:%M'), ['data/live.json'])
            except Exception as e:
                print('après séance :', e)
        time.sleep(60)


if __name__ == '__main__':
    {'live': live, 'close': close, 'boucle': boucle, 'hors': hors, 'relais': relais}[sys.argv[1]]()
