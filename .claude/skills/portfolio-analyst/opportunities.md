# Reconnaître les opportunités

L'inverse du rôle "détecter les pièges" — savoir identifier un setup qui mérite une position. Le skill ne doit pas seulement freiner ; il doit aussi affirmer quand c'est le moment d'engager.

## Circle of competence (Buffett-Munger)

Trois cases avant toute évaluation profonde :

```
┌─────────────┬─────────────┬──────────────┐
│     IN      │    OUT      │   TOO HARD   │
└─────────────┴─────────────┴──────────────┘
```

**IN** : domaines où l'utilisateur (ou le skill via ses données) peut former un avis fondé.
- Big tech US, semiconducteurs, software : OK (data abondante, cas d'usage clair)
- Pharma large cap (Lilly, Novo) : OK avec caveat sur pipelines
- Banques EU/US large cap : OK
- Industrie classique (Schneider, Siemens) : OK

**OUT** : domaines où on n'a pas l'expertise pour distinguer le bon du mauvais.
- Biotech early-stage : trop binaire, expertise scientifique requise
- Petites-mid caps techno chinoises : risque réglementaire imprévisible
- Crypto : pas de fondamentaux comparables, microstructure différente
- SPACs / startups récemment cotées : track record insuffisant

**TOO HARD** : intéressant en théorie mais l'effort pour décider correctement excède l'edge potentiel.
- Distressed debt, restructurations
- Marchés frontières
- Produits dérivés complexes

**Règle** : si la question porte sur du OUT ou du TOO HARD, **dire que c'est en dehors de la zone de compétence**. Ne pas pretendre une analyse qu'on ne peut pas livrer. Munger : *"It is remarkable how much long-term advantage we have gotten by trying to be consistently not stupid, instead of trying to be very intelligent."*

## Critères d'une bonne thèse d'achat

Une thèse est solide si elle réunit **au moins 3 sur 5** :

### 1. Asymétrie risk/reward favorable

Upside potentiel >> downside probable, en absolu.
- Bon : "+30% à 12 mois si la thèse joue, -10% maximum si elle rate" (3:1)
- Mauvais : "+15% si tout va bien, -20% si raté" (asymétrie inverse)

Inspirée de Taleb (*Antifragile*) : ne chercher que des paris où l'upside est non borné et le downside est limité.

### 2. Setup technique propre

- Cross frais (Golden Cross 0-30 jours) ou consolidation post-cross
- RSI dans la zone 40-65 (ni surachat ni survente)
- Volume confirmé sur le breakout
- Z-score régression entre -1 et +1

### 3. Fondamentaux solides

- Croissance CA >10%/an récurrente (pas un one-off)
- Marges nettes en expansion ou stables à haut niveau
- Debt/Equity raisonnable (<1)
- ROE >15% si hors finance / >10% si finance

### 4. Catalyseur identifiable à court-moyen terme

Pas de "bon prix au cas où" — il faut quelque chose qui doit se passer pour réaliser la thèse :
- Earnings prochains avec guidance révisable
- Nouveau produit / ramp commercial
- Décision réglementaire attendue
- Cycle sectoriel favorable

Sans catalyseur, le pari est de la "value" pure — peut prendre des années à se matérialiser.

### 5. Désaccord avec le consensus

Howard Marks (*I Beg to Differ*) : pour un alpha positif, il faut être en désaccord avec le consensus **et avoir raison**.

- Si tu es d'accord avec tout le monde, tu paies le prix du consensus → rendement = beta du marché
- Si tu es en désaccord et tu te trompes → tu perds
- Si tu es en désaccord et tu as raison → alpha

**Question explicite** : qu'est-ce que je vois que le consensus ne voit pas (ou refuse de voir) ?

## Les setups qui marchent statistiquement

### A. Momentum frais sur titres de qualité (Jegadeesh-Titman)

Profil :
- Golden Cross 0-30 jours
- RSI 50-65
- Volume confirmé
- Fondamentaux solides
- Z-score 0 à +1

C'est la sweet spot. Probabilité historique de +X% à 6-12 mois nettement positive (Jegadeesh-Titman 1993 sur 30+ ans de data).

**Source** : Jegadeesh & Titman (1993) *Returns to Buying Winners and Selling Losers*, Journal of Finance — momentum 3-12 mois génère ~1%/mois excess return en US, validé sur 46 pays / 150 ans (AQR).

### B. Mean-reversion sur titres tendus (extreme z-score)

Profil :
- Death Cross >60 jours OU consolidation longue
- RSI <30 (survente extrême)
- Z-score régression < -2σ (titre largement décroché de sa tendance long terme)
- Fondamentaux intacts (pas de rupture business)

Il faut un **catalyseur visible** pour le retournement. Sinon c'est juste un titre qui peut continuer à baisser.

### C. Dual momentum (Antonacci)

Combiner :
- **Momentum absolu** : le titre a-t-il fait mieux que le cash sur 12 mois ? Si non, skip (régime baissier)
- **Momentum relatif** : le titre est-il dans le top quintile de son univers sur 12 mois ?

Antonacci (*Dual Momentum*, 2014) backtest 39 ans : 17.4% CAGR vs 8.85% pour ACWI, max drawdown 22.7% vs 60.21% — performance améliorée surtout par évitement des bear markets via le filtre absolu.

**Caveat** : un seul backtest, configuration spécifique. À considérer comme heuristique, pas comme dogme.

## Anti-pattern : chase de rally

Le faux setup qui ressemble à une opportunité :
- Action qui vient de faire +20-30% en quelques jours
- News positive (earnings beat, partnership, etc.)
- Tout le monde en parle
- Volume explosif

**Probabilité de poursuite** : moins favorable qu'on ne pense.
- L'info est déjà priced in
- Les momentum traders entrent et sortent rapidement
- Mean-reversion à court terme statistiquement significative

**Reframe** : *"Ce n'est pas le bon moment pour cette action. Si c'est vraiment une trend, elle va consolider et offrir un setup plus propre dans 4-8 semaines (RSI redevenu sain, prix proche du nouveau régime de MM21)."* Patience.

## Anti-pattern : value trap

Le faux setup côté value :
- Titre en chute libre
- PER bas, dividend yield élevé
- "Pas cher" au regard des fondamentaux passés
- "Ça va bien remonter"

Risque : **value trap** — le titre est bas pour une bonne raison (déclin structurel) qui n'est pas encore pleinement reflétée dans les fondamentaux récents. Examples historiques : Kodak avant le digital, presse écrite, banques EU post-2010.

**Distinguer value vs value trap** :
- Vraie value = titre temporairement décoté pour raison cyclique ou sentiment, fondamentaux intacts
- Value trap = titre permanenent décoté pour raison structurelle, fondamentaux en érosion

Test : croissance CA des 5 derniers exercices. Si >0% en moyenne, possible value. Si <0%, drapeau rouge value trap.

## Range d'entrée et stratégies de positionnement

Une thèse valide ne dit pas comment entrer. **"Bon prix" est une fausse question** : il n'existe pas de prix optimal connaissable ex ante. La discipline est de positionner l'entrée dans un **range** structurellement cohérent, pas sur un point précis.

### Identifier le range d'entrée

À partir des indicateurs techniques (extraits via yfinance ou breakdown screener), classer les niveaux par profondeur depuis le cours actuel :

| Niveau | Repère technique | Lecture |
|---|---|---|
| Plafond | 52w high | Zone tardive, momentum maximal |
| 0% | Cours actuel | Point de référence |
| -1 à -2% | MM21 | Premier support, accessible quotidiennement |
| -3 à -5% | Fibo 23.6% du dernier cycle | Pullback léger sur trend saine |
| -4 à -7% | MM50 | Support technique classique |
| -6 à -9% | **Fibo 38.2%** | **Retracement standard d'une trend établie** |
| -9 à -12% | Fibo 50% | Retracement profond, achat agressif |
| -12 à -15% | Fibo 61.8% / MM200 | Retracement majeur, momentum techniquement remis en cause |
| Niveau de breakout / golden cross | — | Si touché, le rally entier est annulé |

**Le range d'entrée structurellement intéressant** sur trend établie : entre **MM21 et Fibo 38.2%** (haut = entrée tardive, bas = entrée optimale).
- Au-dessus de MM21 → tu chasses le rally
- En dessous de Fibo 38.2% → il faut un changement de régime pour justifier l'achat (réévaluer la thèse fonda)

### Variante : range d'entrée pour setup mean-reversion (catégorie B)

Quand la thèse est mean-reversion (titre largement décoté de sa trend long terme, z-score < -1.5σ, fondamentaux intacts), les niveaux se lisent **comme cibles haussières depuis le plus bas récent**, pas comme retracements depuis le plus haut :

| Niveau | Lecture |
|---|---|
| Plus bas 1y | Si rechute → setup invalidé |
| MM50 | Support du rebond — entrée idéale sur pullback |
| MM21 | Support immédiat |
| Cours actuel | Point de référence |
| **MM200** | **Niveau pivot — si cassé à la hausse, trend long terme reconfirme** |
| Fibo 38.2% du range 3y (low→high) | Première cible (~+15-20%) |
| Fibo 50% | Cible moyenne (~+25-30%) |
| Fibo 61.8% | Cible ambitieuse (~+35-50%) |
| 52w high | Retour complet |

**Différence avec setup A (bull-cycle)** : on cherche un point d'entrée *avant* la reprise complète mais *après* la confirmation du rebond technique (RSI sorti de la zone de survente, pente MM21 redevenue positive — le screener génère alors un `signal_dynamics_warning` "Rebond mean-reversion en cours"). La 1ère tranche peut être engagée même si le cours est encore sous MM200, à condition que les autres signaux concordent.

**Scale-in mean-reversion recommandé** :
- 1/3 maintenant si rebond confirmé + catalyseur identifié (earnings imminent, etc.)
- 1/3 sur cassure haussière de MM200 (confirmation structurelle)
- 1/3 sur consolidation post-MM200 ou retour à Fibo 38.2%

### 3 stratégies pour opérer dans le range

**A. Limit conservateur** : ordre limit à MM50 ou Fibo 38.2%. Entrée confortable mais **probabilité ~40-50% d'être touché dans 30j** si la trend continue. À favoriser si tu acceptes de rater plutôt que de payer cher.

**B. Scale-in 3 tranches (défaut recommandé)** : 1/3 maintenant, 1/3 sur retour MM21, 1/3 sur retour MM50 ou Fibo 38.2%. Mécanique, pas de regret, capture moyenne intéressante. À privilégier quand le setup est solide mais l'entrée est tardive (proche 52w high).

**C. All-in agressif** : position complète immédiate. À réserver aux catalyseurs imminents + forte conviction. Probabilité de retracement court terme 5-10% élevée si proche 52w high.

### Sizing des tranches

Règle pratique : **ne jamais engager >50% de la cible totale sur la première tranche**. Garder 50% de munition pour le pullback. Cap total selon conviction (cf `methodology.md` : 4-6% modérée, 7-10% forte).

### Invalidations à surveiller pendant le scale-in

- Cassure MM50 avec volume confirmé → suspendre les tranches restantes
- RSI <30 sans rebond rapide → momentum cassé, attendre
- `signal_dynamics_warning` qui apparaît → stop scale-in immédiat
- Earnings miss / guidance révisée à la baisse → ré-évaluer thèse, possible bascule en vente

### Anti-patterns d'entrée

- **Chercher LE bon prix** au lieu d'un range : impossible ex ante, paralysant
- **Tout entrer maintenant par peur de rater** : action bias + FOMO déguisé
- **Attendre indéfiniment un retracement profond** sur trend saine : coût d'opportunité élevé, le titre peut continuer 6 mois sans pullback significatif
- **Renforcer en bas (averaging down)** sur titre dont la thèse fonda s'est dégradée : disposition effect classique, scale-in =/= averaging down
