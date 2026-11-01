# Portefeuille — web app

Application web installable (PWA) pour suivre le portefeuille : 10 actions + l'or, répartition, analyse, transactions, plan d'achat.

## Utiliser
- En ligne : activer **GitHub Pages** (Settings → Pages → *Deploy from a branch* → `main` / `(root)`), puis ouvrir l'adresse donnée.
- Sur téléphone : ouvrir l'adresse, puis « Ajouter à l'écran d'accueil ». L'app marche aussi hors ligne avec les derniers cours chargés.
- En local : `python3 -m http.server` dans ce dossier, puis http://localhost:8000.

## Données
- `data/*.json` : cours mensuels et hebdomadaires, fiches des sociétés, lignes, ventes par pays, taux de change, liste des tickers (États-Unis + Toronto).
- Tes choix de lignes et tes transactions restent **dans ton navigateur** (localStorage). Onglet Transactions → *Sauvegarde* pour exporter / importer un fichier.

## Fichiers
- `index.html` : toute l'application (HTML, CSS, JS ; d3 7.9.0 depuis cdnjs).
- `manifest.webmanifest`, `sw.js`, `icons/` : installation et hors ligne.

Ce n'est pas un conseil financier.
