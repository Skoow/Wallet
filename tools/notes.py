"""Note /100 de toutes les actions de la recherche -> data/notes.json (même barème que la page).
   Entrées : data/p/<clé>.json (chiffres), data/h/<clé>.json (cours pour la régularité), data/univers.json."""
import json, os, glob, datetime as dt

D = 'data/'
NMAP = [0, 2, 2, 2, 2, 2, 5, 5, 6, 9, 9, 10, 11, 13, 16, 17, 19, 20, 21, 21, 21, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 35, 36, 38, 39, 40, 42, 43, 44, 44, 46, 47, 48, 50, 51, 53, 54, 55, 56, 58, 59, 61, 62, 63, 64, 65, 66, 68, 69, 70, 72, 73, 74, 75, 76, 77, 78, 79, 80, 82, 83, 84, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 98, 99, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
NC = {
    'pm': ('marge_nette', 1, [[-10, 0], [0, .25], [5, .55], [10, .75], [20, 1]], [-60, 60]),
    'gm': ('marge_brute', 1, [[0, 0], [20, .3], [40, .6], [60, .85], [75, 1]], [-50, 100]),
    'roic': ('roic', 1, [[-10, 0], [0, .2], [8, .5], [15, .8], [25, 1]], [-60, 80]),
    'roe': ('roe', 1, [[0, 0], [8, .4], [12, .65], [18, .9], [25, 1]], [-60, 80]),
    'fcf': ('cash_libre', 1, [[-10, 0], [0, .3], [5, .6], [15, .9], [25, 1]], [-60, 60]),
    'g5': ('croissance_ca_5a', 1, [[-5, 0], [0, .3], [5, .55], [10, .75], [20, 1]], [-30, 60]),
    'g1': ('croissance_ca_1a', 1, [[-15, 0], [0, .35], [5, .55], [10, .7], [25, 1]], [-50, 100]),
    'e5': ('croissance_bpa_5a', 1, [[-10, 0], [0, .3], [10, .7], [20, 1]], [-50, 80]),
    'de': ('dette_ebitda', -1, [[0, 1], [1, .95], [2, .8], [3, .6], [4, .35], [6, .1], [8, 0]], [-1, 20]),
    'sh': ('actions_an', -1, [[-3, 1], [0, .8], [2, .5], [5, .1], [8, 0]], [-20, 30]),
    'fy': ('rendement_cash', 1, [[-5, 0], [0, .2], [2, .45], [4, .7], [7, .9], [10, 1]], [-20, 20]),
    'pe': ('per_prevu', -1, [[8, 1], [15, .85], [25, .6], [35, .4], [50, .15], [80, 0]], [0, 150])}
CRIT = {'rent': 15, 'eff': 15, 'cash': 10, 'croi': 15, 'sol': 10, 'prix': 10}


def lin(pts, v):
    if v <= pts[0][0]: return pts[0][1]
    for i in range(1, len(pts)):
        if v <= pts[i][0]:
            a, b = pts[i - 1]; c, d = pts[i]
            return b + (d - b) * (v - a) / (c - a)
    return pts[-1][1]


def num(x):
    try:
        return None if x is None or x == '' else float(x)
    except Exception:
        return None


def nraw(u, c):
    f, d, a, cap = NC[c]; v = num(u.get(f))
    if v is None: return None
    if c in ('fcf', 'pm') and v > 100: return None
    if c == 'fy' and abs(v) > 40: return None
    if c == 'g1' and v > 300: return None
    v = max(cap[0], min(cap[1], v))
    if c == 'de' and v < 0: return 20
    return v


def depuis_pro(o):
    """Champs de la note à partir d'un fichier data/p."""
    u = dict(o.get('ratios') or {})
    C = [c for c in o.get('comptes') or [] if c.get('ca_mds')]
    if len(C) >= 2 and C[0]['ca_mds'] > 0 and C[-1]['ca_mds'] > 0:
        u['croissance_ca_5a'] = round(((C[-1]['ca_mds'] / C[0]['ca_mds']) ** (1 / (len(C) - 1)) - 1) * 100, 1)
    B = [c for c in C if (c.get('bpa') or 0) > 0]
    if len(B) >= 2:
        u['croissance_bpa_5a'] = round(((B[-1]['bpa'] / B[0]['bpa']) ** (1 / (len(B) - 1)) - 1) * 100, 1)
    S = [c for c in C if (c.get('actions_m') or 0) > 0]
    if len(S) >= 2:
        u['actions_an'] = round(((S[-1]['actions_m'] / S[0]['actions_m']) ** (1 / (len(S) - 1)) - 1) * 100, 1)
    if C:
        if u.get('marge_nette') is None and C[-1].get('marge_nette') is not None: u['marge_nette'] = C[-1]['marge_nette']
        if u.get('cash_libre') is None and C[-1].get('cash_libre') is not None: u['cash_libre'] = C[-1]['cash_libre']
    u['fin'] = (o.get('profil') or {}).get('secteur') == 'Financial Services'
    return u


def regularite(cle):
    try:
        h = json.load(open(D + 'h/' + cle.replace('/', '_') + '.json', encoding='utf-8'))
    except Exception:
        return None
    p = [x for x in h.get('prix') or []]
    n = up = 0
    for m in range(max(0, len(p) - 120), len(p)):
        x = p[m]
        if x is None: continue
        w = [y for y in p[max(0, m - 49):m + 1] if y is not None]
        if len(w) < 40: continue
        n += 1; up += x > sum(w) / len(w)
    return up / n * 100 if n >= 24 else None


def main():
    S = {}
    for f in glob.glob(D + 'p/*.json'):
        try:
            o = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if o.get('vide'): continue
        S[os.path.basename(f)[:-5].replace('_', '/', 1)] = depuis_pro(o)
    # percentiles sur l'ensemble
    ALL = {c: sorted(v for v in (nraw(u, c) for u in S.values()) if v is not None) for c in NC}
    import bisect
    def pct(c, v):
        a = ALL[c]
        if len(a) < 3: return None
        lo = bisect.bisect_left(a, v); hi = bisect.bisect_right(a, v)
        p = (lo + hi) / 2 / len(a)
        return p if NC[c][1] > 0 else 1 - p
    out = {}
    for cle, u in S.items():
        fin = u.get('fin')
        def crit(c):
            v = nraw(u, c)
            if v is None: return None
            a = lin(NC[c][2], v); p = pct(c, v)
            return .8 * (a if p is None else p) + .2 * a
        def block(it):
            w = s = 0
            for c, wt in it:
                r = crit(c)
                if r is not None: w += wt; s += wt * r
            return s / w if w else None
        B = {'rent': block([('pm', 1)] if fin else [('pm', 8), ('gm', 7)]), 'eff': block([('roe', 1)] if fin else [('roic', 1), ('roe', 1)]),
             'cash': None if fin else block([('fcf', 1)]), 'croi': block([('g5', 8), ('g1', 4), ('e5', 3)]),
             'sol': block([('sh', 1)] if fin else [('de', 6), ('sh', 4)]), 'prix': block([('pe', 1)] if fin else [('fy', 6), ('pe', 4)])}
        pm, fcf, sh, de = num(u.get('marge_nette')), num(u.get('cash_libre')), num(u.get('actions_an')), num(u.get('dette_ebitda'))
        if pm is not None and pm < 0 and B['rent'] is not None: B['rent'] = min(B['rent'], .3)
        if not fin and fcf is not None and fcf < 0 and B['cash'] is not None: B['cash'] = min(B['cash'], .25)
        if not fin and de is not None and (de > 4 or de < 0) and B['sol'] is not None: B['sol'] = min(B['sol'], .4)
        if sh is not None and sh > 5 and B['sol'] is not None: B['sol'] = min(B['sol'], .2)
        connus = sum(1 for k, v in B.items() if v is not None)
        if connus < 4: continue
        pts = sum((.4 if B[k] is None else B[k]) * m for k, m in CRIT.items())
        pa = regularite(cle); pts += pa / 100 * 15 if pa is not None else 7.5
        pts += 5  # fiabilité : pas de vérification à la main
        out[cle] = NMAP[max(0, min(100, round(pts)))]
    json.dump({'maj': dt.date.today().isoformat(), 'n': out}, open(D + 'notes.json', 'w', encoding='utf-8'), separators=(',', ':'))
    print(len(out), 'notes')


if __name__ == '__main__':
    main()
