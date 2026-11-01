# Portefeuille — web app

Application web installable (PWA) pour suivre le portefeuille : 10 actions + l'or, répartition, analyse, transactions, plan d'achat.

## Utiliser
- En ligne : activer **GitHub Pages** (Settings → Pages → *Deploy from a branch* → `main` / `(root)`), puis ouvrir l'adresse donnée.
- Sur téléphone : ouvrir l'adresse, puis « Ajouter à l'écran d'accueil ». L'app marche aussi hors ligne avec les derniers cours chargés.
- En local : `python3 -m http.server` dans ce dossier, puis http://localhost:8000.

## Données
- `data/*.json` : cours mensuels et hebdomadaires, fiches des sociétés, lignes, ventes par pays, taux de change, liste des tickers (États-Unis + Toronto).
- **Profils** : à la première visite, chacun choisit un pseudo. Chaque pseudo a son propre portefeuille, vide au départ (bouton « Partir du portefeuille conseillé » pour reprendre les 10 actions + l'or).
- Tout reste **sur le téléphone** (localStorage) : personne d'autre ne voit tes lignes ni tes transactions, rien n'est envoyé sur GitHub. Onglet Transactions → *Sauvegarde* pour exporter / importer un fichier.

## Cours en direct
- **Sans réglage** : GitHub Actions (`.github/workflows/cours.yml`) relève les cours toutes les 5 minutes pendant la séance (le plus fréquent permis par GitHub) américaine (`data/live.json`), et les clôtures chaque soir (`prix.json`, `hebdo.json`, `fx.json`). La page relit `live.json` chaque minute.
- **À la seconde** : entrer une clé gratuite [Finnhub](https://finnhub.io/register) dans l'onglet Transactions → *Cours en direct*. Les actions américaines, l'or (GLD) et les indices se mettent alors à jour à chaque transaction, via WebSocket. La clé reste dans le navigateur. Toronto (Loblaw, Dollarama) reste sur le relevé des 5 minutes : le plan gratuit de Finnhub ne couvre pas la bourse de Toronto.
- Les chiffres des sociétés (notes, croissance, marges…) sont vérifiés à la main sur 3 à 5 sources et mis à jour à chaque publication de résultats.

## Fichiers
- `index.html` : toute l'application (HTML, CSS, JS ; d3 7.9.0 depuis cdnjs).
- `manifest.webmanifest`, `sw.js`, `icons/` : installation et hors ligne.
- `tools/maj.py` : relevé des cours (Yahoo Finance, changes BCE).

Ce n'est pas un conseil financier.
