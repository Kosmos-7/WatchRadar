# A/D Line — évaluation et décision de ne pas intégrer

**Date** : 7 mai 2026
**Décision** : ne pas intégrer dans le scoring de prod
**Statut** : archivé pour réévaluation future si évidence empirique le justifie

---

## Contexte

L'A/D Line (Accumulation/Distribution Line de Williams) mesure le volume pondéré
par la position de la clôture dans la fourchette du jour :

```
CLV = ((Close - Low) - (High - Close)) / (High - Low)   ∈ [-1, +1]
A/D du jour = CLV × Volume
A/D Line    = somme cumulée
```

Différent du `vol_pts` actuel de Signal qui ne regarde que le volume brut sans
pondération directionnelle. Pourrait théoriquement détecter des divergences
prix/flux (accumulation pendant baisse, distribution pendant hausse).

## Tests effectués

### Test 1 — Cas concrets sur watchlist actuelle

Sur 6 mois pour 4 tickers de la watchlist Signal actuelle :

| Ticker | Prix 6m | A/D 6m | Lecture |
|---|---|---|---|
| NVDA | +12.8% | ~0 (plat) | Hausse sans accumulation soutenue |
| LSEG.L | -0.9% | A/D 3m positif | Accumulation discrète préparatoire |
| CRM | -22.2% | A/D 6m positif | Divergence haussière classique |
| ASML.AS | +49.8% | +7.9M (modéré) | Hausse explosive entrecoupée |

**Lecture qualitative** : l'A/D apporte une dimension réelle non capturée par
les autres métriques (notamment CRM et NVDA où le scoring actuel et l'A/D
divergent significativement).

### Test 2 — Backtest 2019-2024 (53 tickers US)

Configuration testée :
- Fenêtre A/D = 20 jours
- Seuils gradués : 0/2/5 selon ratio CLV pondéré (>0.10 → 2, >0.30 → 5)
- Intégration : composante momentum supplémentaire (40 → 45 pts)
- Univers : 53 tickers US, 312 semaines

| Métrique | Baseline | + A/D | Δ |
|---|---|---|---|
| Portfolio CAGR | +32.35% | +33.49% | +1.14pp |
| ALPHA CAGR/an | +13.51pp | +14.66pp | **+1.15pp** |
| Sharpe Ratio | 1.68 | 1.76 | +0.08 |
| Volatilité | 19.29% | 19.05% | -0.24pp |
| Max Drawdown | -22.70% | -23.72% | -1.02pp |
| Win rate | 65.2% | 64.4% | -0.8pp |
| Avg winner | +18.5% | +19.1% | +0.6pp |
| Avg loser | -10.1% | -9.8% | +0.4pp |

## Pourquoi on n'intègre pas

### 1. Gain marginal et probablement instable
+1.15pp/an se situe à 0.15pp du seuil de matérialité préfixé (>+1pp). Un seul
test, une seule période, une seule configuration. Bootstrap non fait mais
l'incertitude statistique est probablement supérieure à 0.5pp.

### 2. Risque de p-hacking implicite
Les paramètres testés (fenêtre 20j, seuils 0.10/0.30, pondération 5pts) sont
ma première intuition. Pas de test de sensibilité multi-configs ni de
sous-périodes. L'effet de `+1.15pp` pourrait s'effondrer sur une autre
configuration, ce qui révélerait un fitting plutôt qu'un signal réel.

### 3. Biais structurels non corrigeables
- **Survivorship bias** : test sur les 53 tickers actuels Signal (curatés en 2026)
- **Curator bias** : sélection manuelle "compatible momentum" — biais d'avoir
  exclu inconsciemment les actions où la stratégie performe mal
- **Univers partiel** : 53/90 tickers Signal (US uniquement, pas EU/UK)
- **Période unique** : 2019-2024 inclut COVID et boom IA, régimes spécifiques

Ces biais sont structurels — étendre l'univers ne les corrige pas, ça les amplifie.

### 4. Coût de complexité disproportionné
Intégrer demande :
- Documenter le concept dans `apprendre.html` (nouveau lexique)
- Ajouter au breakdown dans la fiche action
- Créer un learning v2.0
- Maintenir 2 paramètres supplémentaires (fenêtre, seuils)
- Risque de bugs dans la transition

Pour un gain incertain de 1pp/an sur un alpha déjà à +13.5pp.

### 5. Discipline anti-overengineering
Le projet a explicitement adopté une posture anti-surengineering — discussions
précédentes sur Weinstein RS et Murphy volume gradué ont conclu "ne pas
ajouter sans évidence empirique forte". L'A/D Line tomberait dans la même
classe : intéressant en théorie, marginal en pratique.

## Conditions pour réévaluer

Réintroduire l'A/D Line **uniquement si** une de ces conditions est observée
en conditions réelles de production :

1. Plusieurs cas concrets où Signal a clairement raté un retournement (achat
   trop tardif sur titre en accumulation discrète, ou vente trop précoce sur
   titre en distribution silencieuse) — au moins 3-5 cas documentés
2. Underperformance prolongée vs MSCI World (alpha < +5pp/an sur 6 mois)
   suggérant que la méthodologie actuelle a perdu son edge
3. Ajout d'une source de données qui permettrait de corriger les biais du
   backtest (composition historique du S&P, données delisted)

## Code archivé

L'implémentation `score_ad()` testée :

```python
def score_ad(hist, window=20):
    """Score A/D Line sur une fenêtre récente, gradué 0/2/5."""
    if len(hist) < window:
        return 0
    recent = hist.tail(window)
    h, l, c, v = recent["High"], recent["Low"], recent["Close"], recent["Volume"]
    rng = (h - l).replace(0, 1)
    clv = ((c - l) - (h - c)) / rng
    ad_sum = float((clv * v).sum())
    vol_mean = float(v.mean())
    if vol_mean <= 0:
        return 0
    ratio = ad_sum / (vol_mean * window)
    if ratio > 0.30: return 5
    if ratio > 0.10: return 2
    return 0
```

Intégration prévue (non appliquée) : ajout dans `score_momentum_at()` et
`score_ticker()`, avec réduction `analystes` 10→5 pts pour conserver total à 100.
