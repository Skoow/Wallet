# Règles du projet

- Tout est en français, pour un usage personnel. Publier directement sur `main`.
- Avant chaque publication : `node tools/ci/test.js .` doit afficher « OK ». Ce test vérifie la page et aussi les données de chaque action du portefeuille conseillé.

## Ajouter ou remplacer une action : toujours tout récupérer, sans attendre qu'on le demande

Pour chaque action ajoutée à `data/params.json` (`choix`), faire dans le même changement :

1. **Cours** : `python3 tools/ajout.py "s/xxx"` si l'action n'est pas dans `data/prix.json` ni `data/h/`.
2. **Fiche et ratios** : si elle n'est pas dans `data/univers.json`, l'ajouter à `params.extra` (ticker, nom, pays, devise, secteur, métier) et vérifier que `data/p/<cle>.json` contient au moins 5 ratios (sinon lancer `python3 tools/nuit.py pro`, qui traite d'abord les actions sans fiche).
3. **Ventes par pays** : une entrée dans `data/expo.json` avec `geo` (5 zones qui font 100), `note_geo` qui dit ce qui est publié et ce qui est estimé, `clients`, `sources`, `themes`. Source : le dernier rapport annuel (10-K, 40-F, rapport de gestion), lu page par page.
4. **Vérification (3 sources)** : pour une action hors `univers.json`, ajouter `fiche` dans son entrée `data/expo.json` : `verdict` (propre / à surveiller / drapeau rouge), `verifie` (jj/mm/aaaa), `raison_verif`, `sources_verif`, `risque`, `strategie`, `prochains_resultats`.
5. **Achat conseillé** : régénérer `params.tx` (1 action par ligne au dernier cours) et augmenter `params.v`.

Les données de nuit (cours, ratios, dividendes) se mettent à jour seules. Les ventes par pays et la vérification ne peuvent pas être automatiques : la SEC exige un e-mail de contact et aucune clé n'est fournie. Elles se font donc à chaque ajout, et le test bloque la publication si elles manquent.

## Ne pas faire

- Pas de secret, pas de désactivation TLS, pas de contournement de blocage de site.
- Ne pas mettre l'e-mail de l'utilisateur dans une requête.
