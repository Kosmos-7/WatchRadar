# Discipline de vente

La vente est statistiquement la décision où le retail détruit le plus de valeur. Cause #1 : le **disposition effect** (vendre les gagnants trop tôt, garder les perdants trop longtemps).

## Le test fondamental : "Would I buy at current price today?"

**La question seule qui compte**, posée systématiquement avant toute décision de garder/vendre une position :

> *"Si je n'avais pas cette position, achèterais-je cette action au prix actuel ?"*

- Si **oui** → garder, voire renforcer si la pondération le permet
- Si **non** → vendre

Cette question élimine l'anchoring sur le prix d'achat. Le marché ne sait pas et ne se soucie pas de ton prix d'entrée.

**Pourquoi c'est puissant** : sépare la décision d'investissement présente du regret/satisfaction passé. Force à raisonner forward-looking.

## Règles de vente à pré-définir AVANT l'achat

L'erreur classique : décider de vendre **après** que la position commence à bouger contre toi (loss aversion en plein action). La discipline : écrire les conditions de vente **avant** d'acheter.

**Template** :
```
Achat XYZ à 100€ — date YYYY-MM-DD
Thèse: [résumé en 2-3 phrases]
Vente déclenchée si:
  1. Stop-loss à -15% (technique)
  2. Catastrophe à -25% (sans condition de durée)
  3. Earnings miss avec révision baissière du consensus analystes
  4. Rupture de la thèse fondamentale (ex: perte du leader sectoriel)
  5. Score watchlist tombe sous 50/100 trois semaines consécutives
Horizon minimum de hold: 90 jours sauf événement fondamental majeur
```

Si la position bouge et que **aucune** des conditions de vente n'est déclenchée, **garder** — peu importe la douleur émotionnelle ou la tentation.

## Hiérarchie des stop-loss (inspiré Signal)

1. **R07 — Stop-loss standard** : -15% après 90 jours de détention. Rationalité : si après 3 mois la thèse n'a pas tenu et la perte est significative, accepter l'erreur.

2. **R08 — Stop-loss catastrophe** : -25% sans condition de durée. Rationalité : protège contre les effondrements rapides dans les 89 premiers jours (le "trou" entre R01 et R07).

Les deux sont **mécaniques** — pas de discussion possible. C'est précisément l'absence de jugement émotionnel qui les rend efficaces.

## Anti-disposition concrète

### Symptôme 1 : tentation de vendre un gagnant

**Question test** : *"Pourquoi exactement je veux vendre ?"*
- *"Pour sécuriser mes gains"* → loss aversion inversée. Le marché n'a pas vu ces gains, ils ne sont pas "tiens" tant que tu n'as pas une meilleure utilisation du capital.
- *"Parce que je pense que ça va baisser"* → tu as une **thèse de retournement** documentée ? Si oui, OK. Sinon c'est de l'intuition.
- *"Parce que c'est devenu trop gros dans mon portefeuille"* → légitime, mais c'est une question de **rebalancing**, pas de vente. Vendre une fraction (25-50%) suffit.

### Symptôme 2 : refus de vendre un perdant

**Question test** : *"Si la thèse d'achat était formulée aujourd'hui, l'achèterais-je ?"*
- *"Pas vraiment, mais je veux attendre que ça remonte"* → drapeau rouge. **Le marché ne te doit rien.** Vendre.
- *"Oui, la thèse tient encore"* → garder, et même éventuellement renforcer (si le scoring est meilleur maintenant qu'à l'achat). Mais pas par devoir d'averaging down.

### Symptôme 3 : sentiment d'urgence

Quand la pulsion de vendre vient d'une **émotion** (panique, regret, euphorie), **attendre 24-48h** avant d'agir. Si après ce délai tu peux articuler la décision en termes techniques (signal, fondamental, règle), elle est sans doute valide. Sinon, elle vient du système 1 (Kahneman).

## Disposition effect en chiffres

Odean (1998) — *Are Investors Reluctant to Realize Their Losses?*, Journal of Finance — étude sur 10 000 comptes brokerage :

> *"Investors demonstrated a strong preference for realizing winners rather than losers. The subsequent return of the prior winners they sold was, on average, higher than the subsequent return of the prior losers they held."*

Les gagnants vendus continuent de monter. Les perdants gardés continuent de baisser. Le pattern moyen est **statistiquement confirmé**.

Cela ne veut pas dire "ne jamais vendre les gagnants" ou "toujours vendre les perdants" — ce serait une caricature. Cela veut dire : **la pulsion par défaut** des retail va **dans la mauvaise direction**, donc il faut une discipline pour la contrer.

## Quand vendre légitimement

Liste des raisons valables, par ordre de robustesse :

1. **Stop-loss mécanique déclenché** (R07/R08) — pas de discussion
2. **Thèse fondamentale rompue** (changement de management, nouveau concurrent disruptif, scandale comptable) — vente totale rapide
3. **Allocation devenue déséquilibrée** (>20% du capital) — vente partielle pour rebalancer
4. **Meilleure opportunité identifiée** (score significativement supérieur ailleurs ET pas de cash dispo) — vente pour rotation
5. **Besoin de liquidité hors investissement** (achat immobilier, etc.) — vente programmée
6. **Tax-loss harvesting** (en fin d'année fiscale) — vente technique avec rachat compatible règles fiscales

**Ce qui n'est PAS une raison valable** :
- *"Le marché va baisser"* — timing de marché, statistiquement perdant
- *"J'ai assez gagné"* — anchoring sur P&L, pas sur valeur
- *"Je m'ennuie"* — action bias
- *"Mon ami a vendu"* — herding
- *"Death Cross frais"* si `signal_dynamics_warning` indique transition — attendre confirmation (golden cross qui se reforme OU cours qui repasse durablement sous MM200) avant de trancher

## Test du miroir

Pour chaque vente envisagée, écrire dans un journal :
- Date
- Ticker, prix de vente, prix d'achat, perf
- Raison (en 1 phrase précise)
- Catégorie : mécanique / thèse / rebalance / rotation / fiscal / **émotionnel**

Si la catégorie "émotionnel" représente >20% des ventes sur 12 mois, il y a un problème de discipline qu'il faut adresser structurellement (peut-être : ajouter des règles plus contraignantes ou réduire la fréquence de check du portefeuille).
