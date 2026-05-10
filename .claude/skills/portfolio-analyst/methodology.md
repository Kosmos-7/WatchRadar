# Méthodologie d'évaluation d'un titre

Approche en 3 piliers, validée empiriquement sur des décennies de recherche académique.

## Scoring synthétique : 100 points

```
Momentum technique  →  40 pts
Fondamentaux        →  50 pts
Analystes           →  10 pts
                       ─────
                       100 pts
```

Pondération calibrée par l'expérience (le projet Signal applique cette logique en production sur 90 tickers, backtest 2019-2024 : +13.5pp/an d'alpha vs SPY sur les 40 pts de momentum seuls).

## Pilier 1 — Momentum technique (40 pts)

### 1.1 Croisement MM21 / MM200 (20 pts)

**Golden Cross** (MM21 passe au-dessus de MM200) → signal haussier.
**Death Cross** (MM21 passe en-dessous de MM200) → signal baissier.

Pondération par fraîcheur du signal :
- Cross 0-30 jours : signal frais, prime maximale
- Cross 30-90 jours : encore valide, prime modérée
- Cross 90-180 jours : trend mature, prime faible
- Cross >180 jours : signal stale, négligeable

**Source** : Murphy *Technical Analysis of the Financial Markets* (2e éd., 1999) — référence standard. Win rate historique du Golden Cross ~72% à 6 mois quand pris dans les 30 premiers jours.

**Lecture dynamique obligatoire** : un cross n'est pas un état figé. Le screener calcule automatiquement un champ `signal_dynamics_warning` dans le breakdown quand le signal est en transition (death cross avec pente MM21 redevenue positive et spread tendu, ou golden cross s'affaiblissant). **Toujours lire ce champ avant de pondérer le cross dans le verdict.** Quand il est non-vide, traiter le signal comme ambigu — pas exploitable seul.

### 1.2 RSI (10 pts)

Mesure de momentum 0-100 sur 14 périodes :
- Zone idéale 40-60 → 10 pts (momentum sain, ni surachat ni survente)
- Zone élargie 35-65 → 5 pts
- Zone surachat (>70) ou survente (<30) → 0 pt (signal extrême, mean-reversion probable)

Combiné au Cross : Golden Cross + RSI 50 = setup propre. Golden Cross + RSI 75 = signal mature, hausse probablement priced in.

### 1.3 Volume (5 pts)

`vol_recent (20 derniers jours) > vol_annual (2 ans glissants)` → 5 pts, sinon 0.

Logique Murphy : un mouvement sans volume est suspect. Volume confirme la conviction collective.

### 1.4 Régression long terme z-score (5 pts)

Position du cours actuel vs sa droite de tendance log-linéaire long terme, exprimée en écarts-types :
- z entre -0.5σ et +1.5σ → zone saine, 5 pts
- z < -1σ → titre en décote vs sa propre tendance (potentielle opportunité mean-reversion)
- z > +2σ → titre tendu, retracement statistiquement probable

**Référence empirique** : Jegadeesh & Titman (1993) montrent que le momentum 3-12 mois fonctionne, mais Asness (AQR) note que l'effet s'inverse aux extrêmes par mean-reversion.

## Pilier 2 — Fondamentaux (50 pts)

50 pts répartis sur :

- **Croissance du chiffre d'affaires** (15 pts) : >15%/an = max
- **Marges nettes** (10 pts) : >20% = max
- **PEG ratio** (15 pts) : <1 = excellent (15 pts), <2 = correct (10 pts)
- **Croissance EPS** (5 pts) : >10%/an = max
- **Endettement** (5 pts) : Debt/Equity < 0.5 = max

Sources de données : Yahoo Finance + Finnhub (cross-validation). Quand divergence importante, baisse de la confiance globale.

## Pilier 3 — Consensus analystes (10 pts)

Recommandation moyenne sur échelle 1-5 :
- < 2.0 (strong buy) → 10 pts
- < 2.5 (buy) → 6 pts
- < 3.0 (hold) → 3 pts
- ≥ 3.0 → 0 pt

**Pondération volontairement faible** car signal lagging (les analystes réagissent souvent aux mouvements de prix, plus qu'ils ne les précèdent) avec biais haussier structurel (~80% des recommandations sont buy/hold).

## Le facteur lens : croiser momentum / value / quality

Une fois le score calculé, regarder le profil du titre :

- **Momentum** = fraîcheur du Golden Cross + RSI sain + volume confirmé
- **Value** = z-score régression négatif + PEG raisonnable
- **Quality** = marges + croissance + endettement

**Le best setup** = momentum frais + value attractif + quality solide. Rare. Quand il se présente, conviction forte.

**Setup mixte** : momentum mature + value en place → opportunité moyenne, conviction modérée.
**Setup faible** : momentum fort + value tendu → chase de rally, conviction faible voire skip.

## Position sizing

### Principe : Kelly fractionnaire

Formule Kelly théorique : `f* = (bp - q) / b` où b = ratio gain/perte, p = proba succès, q = 1-p.

**Problème pratique** : on ne connaît jamais p exactement. Surestimer p mène à overbetting et drawdowns sévères.

**Demi-Kelly comme standard** : ~75% du growth rate de Kelly complet pour ~50% du drawdown maximal. Compromis empiriquement validé pour le retail.

### Sizing par conviction (heuristique simple)

| Conviction | Cap par position |
|---|---|
| Forte | 7-10% du capital |
| Modérée | 4-6% |
| Faible | 2-3% |
| Pas d'avis | 0% (skip) |

**Cap absolu** : 20% sur un seul titre (Règle Signal R02) — au-delà, le risque idiosyncratique domine la performance.

**Diversification minimale** : 12-15 positions pour réduire le risque spécifique sans diluer l'edge.

### Liquidités

Maintenir au moins 5% en liquidités même en bull market. Donne :
- Optionalité (capacité à acheter sur correction)
- Coussin psychologique (réduit pulsions de vente forcée)

## Intégration Signal (si applicable)

Si l'utilisateur travaille dans le repo Signal, tu peux importer directement :

```python
from screener import score_ticker, detect_cross, cross_score, calcul_regression
```

`score_ticker(ticker)` retourne un dict avec score 0-100 + breakdown détaillé. Utiliser cette fonction pour avoir un scoring strictement consistant avec ce qui pilote le portfolio Signal.

Si pas dans le repo Signal, tu appliques la même logique manuellement via yfinance + les formules ci-dessus.

## Synthèse de l'analyse

Après scoring + factor lens + sizing, formule canonique d'output :

```
Score: 78/100 (momentum 32, fonda 38, analystes 8)
Profile: momentum frais + value modéré + quality solide
Verdict: ACHAT — conviction modérée
Sizing: 5% du capital max
Risque principal: [le risque concret le plus pertinent]
Pre-mortem: [scénario d'échec plausible]
```

Pas de fluff. Pas de "Disclaimer: this is not financial advice" à chaque réponse. Le verdict, les chiffres, les caveats techniques, fini.
