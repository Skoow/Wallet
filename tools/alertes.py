"""Alertes des lignes du portefeuille conseillé (data/params.json -> choix) -> data/alertes.json.
   Résultats dans 2 jours, passage au « bon moment » (valorisation), note qui baisse, drapeau rouge / à surveiller.
   La tâche du matin lit ce fichier et envoie le résumé en notification."""
import json, datetime as dt

D = 'data/'


def load(f, d=None):
    try: return json.load(open(D + f, encoding='utf-8'))
    except Exception: return d


def entree(cle, u, o, prix):
    """Même calcul que la page : PER du jour contre sa médiane 5 ans (cours mensuel / BPA de l'exercice précédent), cash libre, révisions."""
    B = {int(c['annee']): c['bpa'] for c in (o or {}).get('comptes') or [] if (c.get('bpa') or 0) > 0}
    r = next((x for x in prix if x['cle'] == cle), None)
    if not r or len(B) < 2 or not (o or {}).get('bpa_12m'): return None
    y0, m0 = map(int, r['debut'].split('-')); P = r['prix']; s0 = y0 * 12 + m0 - 1
    def eps(y):
        b = None
        for k in sorted(B):
            if k <= y: b = B[k]
        return b
    pe = []
    for i in range(max(0, len(P) - 60), len(P)):
        e = eps((s0 + i) // 12 - 1)
        if P[i] and e and 0 < P[i] / e < 250: pe.append(P[i] / e)
    if len(pe) < 24: return None
    pe.sort(); md = pe[len(pe) // 2]; cur = P[-1] / o['bpa_12m']
    ch = md / cur - 1; pts = 2 if ch >= .1 else 1 if ch >= 0 else -2 if ch <= -.2 else -1 if ch <= -.1 else 0
    fcf = u.get('rendement_cash')
    if fcf is not None: pts += 1 if fcf >= 4 else -1 if fcf < 1.5 else 0
    rv = ((o.get('revisions') or {}).get('an') or {}).get('revision_90j_pct')
    if rv is not None: pts += 1 if rv >= 3 else -1 if rv <= -3 else 0
    return 'Bon moment' if pts >= 2 else 'Attendre un repli' if pts <= -2 else 'En 2–3 fois'


def main():
    U = {u['cle']: u for u in load('univers.json', [])}
    PRO = load('pro.json', {}); PRIX = load('prix.json', [])
    choix = [c for c in (load('params.json', {}) or {}).get('choix', []) if c and not c.startswith('e/')]
    old = load('alertes.json', {}) or {}
    etat_old = old.get('etat', {})
    today = dt.date.today(); out = []; etat = {}
    for c in choix:
        u = U.get(c) or {}; nom = u.get('nom', c)
        e = entree(c, u, PRO.get(c), PRIX)
        n = u.get('note'); v = u.get('verdict')
        etat[c] = {'entree': e, 'note': n, 'verdict': v}
        was = etat_old.get(c, {})
        pr = u.get('prochains_resultats')
        try:
            dj = (dt.date.fromisoformat(str(pr)[:10]) - today).days
            if 0 <= dj <= 2: out.append(['resultats', nom, 'résultats ' + ('aujourd’hui' if dj == 0 else 'demain' if dj == 1 else 'dans 2 jours') + ' : attendre le lendemain pour acheter'])
        except Exception: pass
        if e == 'Bon moment' and was.get('entree') not in (None, 'Bon moment'): out.append(['achat', nom, 'passe au bon moment (moins chère que d’habitude)'])
        if e == 'Attendre un repli' and was.get('entree') == 'Bon moment': out.append(['cher', nom, 'n’est plus au bon prix'])
        if n is not None and was.get('note') is not None and n <= was['note'] - 8: out.append(['note', nom, 'note en baisse : %s → %s' % (was['note'], n)])
        if v == 'drapeau rouge' and was.get('verdict') != 'drapeau rouge': out.append(['rouge', nom, 'drapeau rouge : ' + (u.get('raison_verif') or 'voir la fiche')])
        elif v == 'à surveiller' and was.get('verdict') not in (None, 'à surveiller', 'drapeau rouge'): out.append(['surveiller', nom, 'à surveiller : ' + (u.get('raison_verif') or 'voir la fiche')])
    bon = [U.get(c, {}).get('nom', c) for c, x in etat.items() if x['entree'] == 'Bon moment']
    json.dump({'maj': today.isoformat(), 'alertes': out, 'bon_moment': bon, 'etat': etat},
              open(D + 'alertes.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(len(out), 'alertes ;', len(bon), 'au bon moment')


if __name__ == '__main__':
    main()
