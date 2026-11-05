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
    for c in (cles or suivis()):
        s = sym(c)
        r = quote(s) if s else None
        if r:
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
        if d.year * 12 + d.month - 1 != mi(r['debut']) + len(r['prix']) - 1:
            continue
        ref = r['prix'][-2] if len(r['prix']) > 1 else r['prix'][-1]
        if ref and abs(q[0] / ref - 1) > 0.25:
            miss.append(r['cle'] + ' (saut > 25 %)'); continue
        r['prix'][-1] = q[0]; got += 1
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
                j = yahoo.get(f'https://{host}.finance.yahoo.com/v7/finance/quote?symbols={q}&fields=marketState,preMarketPrice,preMarketChangePercent,preMarketTime,postMarketPrice,postMarketChangePercent,postMarketTime' + (f'&crumb={urllib.parse.quote(c_)}' if c_ else ''))
                break
            except Exception:
                continue
        for r in ((j or {}).get('quoteResponse') or {}).get('result') or []:
            c = sy.get(r.get('symbol'))
            if not c:
                continue
            st = str(r.get('marketState') or '')
            for k, lab in (('postMarket', 'post'), ('preMarket', 'pre')):
                p, pc, t = r.get(k + 'Price'), r.get(k + 'ChangePercent'), r.get(k + 'Time')
                if p and pc is not None and t and (lab == 'pre' or st != 'PRE'):
                    hs[c] = [rp(p), round(float(pc), 2), lab, dt.datetime.fromtimestamp(int(t), dt.timezone.utc).isoformat()]
                    break
        time.sleep(0.3)
    old['hs'] = hs
    save('live.json', old)
    print(len(hs), 'cours hors séance')
    return True


def boucle(minutes=350, pas=60):
    """En séance : cours des lignes de base, indices et changes chaque minute ; toutes les actions toutes les 5 min."""
    fin = time.time() + minutes * 60
    base = list(dict.fromkeys(load('params.json').get('choix', []) + ['e/gld', 'e/spy', 'e/urth', 'e/qqq', 'e/cac', 'e/fxe', 'e/fxc', 'e/fxf']))
    i = 0
    while time.time() < fin:
        t0 = time.time()
        h = dt.datetime.now(dt.timezone.utc)
        if h.hour * 60 + h.minute > 21 * 60 + 20:
            break
        live(None if i % 5 == 0 else base)
        if i % 5 == 0 and (h.hour < 14 or (h.hour == 14 and h.minute < 30)):
            try:
                hors()
            except Exception as e:
                print('hors séance :', e)
        git_push('Cours ' + h.strftime('%H:%M'), ['data/live.json', 'data/prix.json', 'data/hebdo.json'])
        i += 1
        time.sleep(max(5, pas - (time.time() - t0)))


if __name__ == '__main__':
    {'live': live, 'close': close, 'boucle': boucle, 'hors': hors}[sys.argv[1]]()
