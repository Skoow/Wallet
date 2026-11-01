"""Mise à jour des cours pour la web app (lancé par GitHub Actions).

  python tools/maj.py live   -> data/live.json : dernier cours des lignes, indices et changes (toutes les 15 min en séance)
  python tools/maj.py close  -> data/prix.json, data/hebdo.json, data/fx.json : clôture du jour (le soir)

Source : Yahoo Finance (graphique v8) ; changes BCE via frankfurter.app. En cas d'échec, l'ancienne valeur est gardée.
"""
import json, sys, time, datetime as dt, urllib.request, urllib.parse

D = 'data/'
UA = {'User-Agent': 'Mozilla/5.0 (portefeuille web app)'}
ETF = {'e/gld': 'GLD', 'e/slv': 'SLV', 'e/spy': 'SPY', 'e/qqq': 'QQQ', 'e/urth': 'URTH', 'e/ezu': 'EZU',
       'e/fxe': 'FXE', 'e/fxf': 'FXF', 'e/fxc': 'FXC', 'e/cac': '^FCHI'}
EXCH = {'tsx': '.TO', 'epa': '.PA', 'swx': '.SW', 'xetra': '.DE', 'lse': '.L', 'ams': '.AS', 'mil': '.MI'}


def sym(cle):
    if cle in ETF:
        return ETF[cle]
    k, rest = cle.split('/', 1)
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
    q = urllib.parse.quote(s)
    for host in ('query1', 'query2'):
        try:
            j = get(f'https://{host}.finance.yahoo.com/v8/finance/chart/{q}?range=5d&interval=1d')
            m = j['chart']['result'][0]['meta']
            p, t = m.get('regularMarketPrice'), m.get('regularMarketTime')
            if p and t:
                tz = dt.timezone(dt.timedelta(seconds=m.get('gmtoffset', 0)))
                d = dt.datetime.fromtimestamp(t, tz)
                return round(float(p), 4), d.date().isoformat(), dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat()
        except Exception:
            continue
    return None


def load(f):
    return json.load(open(D + f, encoding='utf-8'))


def save(f, o):
    json.dump(o, open(D + f, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))


def suivis():
    ch = load('params.json').get('choix', [])
    return list(dict.fromkeys(ch + ['e/gld', 'e/spy', 'e/urth', 'e/qqq', 'e/fxe', 'e/fxc', 'e/fxf']))


def live():
    P, H = load('prix.json'), load('hebdo.json')
    _, sh = roll(P, H, dt.date.today())
    ln = [len(r['prix']) for r in P]
    if sh or ln != [len(r['prix']) for r in load('prix.json')]:
        save('prix.json', P); save('hebdo.json', H); print('nouveau mois / nouvelle semaine')
    px, at = {}, {}
    for c in suivis():
        s = sym(c)
        r = quote(s) if s else None
        if r:
            px[c], at[c] = r[0], r[2]
    fx = {}
    for pair, s in (('EURUSD', 'EURUSD=X'), ('EURCAD', 'EURCAD=X')):
        r = quote(s)
        if r:
            fx[pair] = r[0]
    if not px:
        print('aucun cours reçu, live.json inchangé'); return False
    save('live.json', {'at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'px': px, 'heure': at, 'fx': fx})
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


if __name__ == '__main__':
    {'live': live, 'close': close}[sys.argv[1]]()
