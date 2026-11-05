"""Ajoute des actions aux séries de cours : python tools/ajout.py "s/pg,s/ko,a/tsx-wcn"
   -> data/prix.json (mensuel depuis 2006) et data/hebdo.json (mêmes semaines que les autres séries)."""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yahoo, maj


def _rp(v):
    """Arrondi qui garde les tout petits cours (6 chiffres significatifs sous 1)."""
    v = float(v)
    return float(f"{v:.6g}") if abs(v) < 1 else round(v, 4)


P, H = maj.load('prix.json'), maj.load('hebdo.json')
d0 = dt.date.fromisoformat(H[0]['debut']); n = len(H[0]['prix'])
weeks = [d0 + dt.timedelta(weeks=i) for i in range(n)]
LISTE = 'data/a_ajouter.txt'
arg = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else (open(LISTE).read() if os.path.exists(LISTE) else '')
if os.path.exists(LISTE):
    open(LISTE, 'w').write('')
arg = ','.join(l for l in arg.splitlines() if not l.strip().startswith('#'))
for cle in [c.strip() for c in arg.split(',') if '/' in c]:
    s = maj.sym(cle)
    m = yahoo.chart(s, 'depuis2006', '1mo'); w = yahoo.chart(s, '2y', '1wk')
    if not m or not m.get('timestamp'):
        print(cle, 'introuvable'); continue
    last = m['meta'].get('regularMarketPrice')
    mm = {}
    for ts, c in zip(m['timestamp'], m['indicators']['quote'][0]['close']):
        if c is None: continue
        d = dt.datetime.utcfromtimestamp(ts + 43200); mm[d.year * 12 + d.month - 1] = _rp(c)
    cm = dt.date.today().year * 12 + dt.date.today().month - 1
    if last: mm[cm] = _rp(last)
    k0 = min(mm); pr = []; prev = None
    for k in range(k0, cm + 1):
        prev = mm.get(k, prev); pr.append(prev)
    P = [r for r in P if r['cle'] != cle] + [{'cle': cle, 'debut': f'{k0 // 12}-{k0 % 12 + 1}', 'prix': pr}]
    wk = {}
    if w and w.get('timestamp'):
        for ts, c in zip(w['timestamp'], w['indicators']['quote'][0]['close']):
            if c is None: continue
            d = dt.datetime.utcfromtimestamp(ts + 43200).date(); wk[d - dt.timedelta(days=d.weekday())] = _rp(c)
    if last: wk[weeks[-1]] = _rp(last)
    hb = []; prev = None
    for d in weeks:
        prev = wk.get(d, prev); hb.append(prev)
    first = next((x for x in hb if x is not None), None); hb = [first if x is None else x for x in hb]
    H = [r for r in H if r['cle'] != cle] + [{'cle': cle, 'debut': H[0]['debut'], 'prix': hb}]
    print(cle, len(pr), 'mois', pr[-1], '| semaine', hb[-1])
maj.save('prix.json', P); maj.save('hebdo.json', H)
