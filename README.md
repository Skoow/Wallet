# Portefeuille — web app

Application web installable (PWA) pour suivre le portefeuille : 10 actions + l'or, répartition, analyse, transactions, plan d'achat.

## Utiliser
- En ligne : Settings → Pages → Source **GitHub Actions** ; le site se publie tout seul à chaque mise à jour.
- Sur téléphone : ouvrir l'adresse, puis « Ajouter à l'écran d'accueil ». L'app marche aussi hors ligne avec les derniers cours chargés.
- En local : `python3 -m http.server` dans ce dossier, puis http://localhost:8000.

## Données
- `data/*.json` : cours mensuels et hebdomadaires, fiches des sociétés, lignes, ventes par pays, taux de change, liste des tickers (États-Unis + Toronto).
- **Profils** : à la première visite, chacun choisit un pseudo. Chaque pseudo a son propre portefeuille, vide au départ (bouton « Partir du portefeuille conseillé » pour reprendre les 10 actions + l'or).
- Tout reste **sur le téléphone** (localStorage) : personne d'autre ne voit tes lignes ni tes transactions, rien n'est envoyé sur GitHub. Onglet Transactions → *Sauvegarde* pour exporter / importer un fichier.

## Mises à jour automatiques (sans clé)
| Quoi | Quand |
|---|---|
| Cours des lignes de base, de l'or, des indices (dont le CAC 40) et des changes | **chaque minute** du lundi au vendredi, de l'ouverture de Paris à la clôture américaine (`data/live.json`, lu directement par la page) |
| Cours de toutes les autres actions proposées | toutes les 5 minutes en séance |
| Gains et pertes, valeur du portefeuille, capitalisation, PER, rendement du cash | à chaque nouveau cours (calculés dans la page) |
| Clôtures, nouveau mois / nouvelle semaine, euro/dollar | chaque soir |
| Chiffres des sociétés (date des résultats, capitalisation, PER ; marges, ROE, cash, dette après chaque publication) | chaque nuit (Yahoo, marqués « auto ») |
| Dernier cours de toutes les actions ajoutées hors liste | chaque nuit |
| Liste de tous les tickers (USA + Toronto) et historiques de chaque action de plus de 2 Md$ | 1er dimanche du mois |

Un ticker ou un nom (« nvidia », « ecolab », « L.TO ») suffit : l'action est reconnue et son historique se charge aussitôt.
Avec une clé Finnhub gratuite (facultative, écran d'arrivée), les actions américaines passent **à la seconde**.

**Réglage unique** : Settings → Pages → Source : **GitHub Actions**. Le dépôt doit être public (minutes d'Actions illimitées).

## Fichiers
- `index.html` : toute l'application (HTML, CSS, JS ; d3 7.9.0 depuis cdnjs).
- `manifest.webmanifest`, `sw.js`, `icons/` : installation et hors ligne.
- `tools/maj.py` : relevé des cours (Yahoo Finance, changes BCE) ; `tools/nuit.py` : tickers, historiques, chiffres des sociétés ; `tools/yahoo.py` : accès Yahoo.

Ce n'est pas un conseil financier.
