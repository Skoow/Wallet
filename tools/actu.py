"""Actualité importante (positive ou négative) des actions suivies en priorité, rafraîchie chaque soir.

    python tools/actu.py [cle1,cle2,...]

Met à jour seulement le champ « actu » de data/f/<cle>.json : [{d, r (résumé en français), n (vert / orange / rouge), t (titre), l (lien), src}].
Sans argument : actions du portefeuille conseillé, de la liste de base et des lignes ajoutées (params.extra).
Les autres actions ont leur actualité refaite avec leur fiche, tous les 3 jours (tools/fiches.py)."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fiches, nuit

D = 'data/'


def main():
    only = [c.strip() for c in (sys.argv[1] if len(sys.argv) > 1 else '').split(',') if c.strip()]
    L = json.load(open(D + 'tickers.json', encoding='utf-8'))
    rows = {nuit.cle_of(r[0], r[2]): r for r in L}
    todo = set(only)
    if not only:
        try:
            p = json.load(open(D + 'params.json', encoding='utf-8'))
            todo |= set(p.get('choix') or []) | set((p.get('extra') or {}).keys())
        except Exception:
            pass
        try:
            todo |= {u['cle'] for u in json.load(open(D + 'univers.json', encoding='utf-8'))}
        except Exception:
            pass
    n = 0
    for c in sorted(todo):
        r = rows.get(c)
        if not r:
            continue
        f = fiches.OUT + c.replace('/', '_') + '.json'
        try:
            prev = json.load(open(f, encoding='utf-8'))
        except Exception:
            prev = {'cle': c}
        sym = nuit.ysym(r[0], r[2])
        a = fiches.actu_de(sym, r[1], fiches.nouvelles(sym), prev)
        if a != prev.get('actu'):
            prev['actu'] = a
            json.dump(prev, open(f, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            n += 1
        time.sleep(0.25)
    print(len(todo), 'actions regardées,', n, 'fiches avec une actualité nouvelle')


if __name__ == '__main__':
    import urllib.parse  # noqa: F401
    main()
