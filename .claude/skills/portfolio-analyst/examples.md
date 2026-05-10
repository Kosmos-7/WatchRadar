# Patterns Q/R archétypaux

Exemples pour calibrer le ton, la structure, et la profondeur d'analyse selon le type de question.

## Pattern 1 — "Dois-je acheter X ?"

**User** : *"Dois-je acheter NVDA ?"*

**Réponse type** :

```
Avant l'analyse : circle of competence ?
  → NVDA = US large cap tech, dans le IN. OK, on peut analyser.

Données techniques (yfinance ou via screener.score_ticker si dans Signal) :
  Prix : $212.40
  Cross : Golden 13j (frais)
  RSI : 64 (zone élargie, presque sortie)
  Volume : confirmé sur les 3 derniers jours (+2.5x moyenne)
  Z-score régression : +0.4σ (proche de la tendance, sain)
  
Fondamentaux :
  CA growth : +73%/an (extraordinaire)
  Net margin : 56% (exceptionnel)
  PEG : ~1.2 (raisonnable malgré valorisation)
  
Action récente : +33% en 4 jours sur catalyseur AI/datacenter

Verdict : ACHAT — conviction modérée
  - Setup technique propre (cross frais + volume)
  - Fondamentaux exceptionnels
  - MAIS : achat post-rally, RSI proche surachat, le mouvement récent est partiellement priced in
  
Sizing : 4-5% du capital max (modérée car rally récent)

Pre-mortem : 
  - Régulation IA brutale → multiple compresse fortement
  - Custom silicon hyperscalers réduit la dépendance NVDA
  - Earnings miss sur le datacenter → -20% rapide
  
Conditions de vente à pré-définir :
  - Stop-loss -15% (R07)
  - Catastrophe -25% (R08)
  - Earnings miss avec révision baissière
  - Cross descendant ou RSI <30 + perte de momentum
  
Alternative à considérer : attendre une consolidation/pullback 
(probable dans 4-8 semaines) pour entrer sur un setup plus propre.
```

**Pourquoi cette structure** :
- Catégorisation circle of competence en premier
- Données chiffrées avant verbal
- Verdict + conviction explicites
- Pre-mortem obligatoire pour position envisagée
- Conditions de sortie pré-définies (anti-disposition)
- Alternative honnête mentionnée

## Pattern 2 — "J'ai vendu trop tôt, je m'en veux"

**User** : *"J'ai vendu MSFT à 380, c'est à 420 maintenant. Je m'en veux."*

**Réponse type** :

```
Détection : disposition effect + resulting bias.

Analyse process vs outcome (Annie Duke):

Quel était ton process au moment de vendre ?
  - Stop-loss déclenché ? → décision mécanique correcte, peu importe le résultat ex post
  - Thèse fondamentale rompue ? → décision rationnelle correcte
  - Score watchlist tombé sous seuil ? → règle suivie, OK
  - Pulsion de "sécuriser le gain" ? → process émotionnel, leçon à tirer
  - Anchoring sur un prix cible mental ? → biais à corriger

Si ton process était mauvais (case 4 ou 5), la perte d'opportunité est 
une conséquence prévisible. La leçon n'est pas "j'aurais dû garder MSFT" 
mais "j'ai pris une décision pour la mauvaise raison".

Si ton process était bon (cases 1-3), tu n'as rien à te reprocher : 
+10% supplémentaire est de la malchance dans le bruit. Ne change pas 
ton process pour un seul outcome.

Reframe : la vraie question n'est pas "ai-je vendu trop tôt ?" mais 
"si MSFT était à 420 aujourd'hui sans que je l'aie en portefeuille, 
l'achèterais-je ?". Si oui → tu peux re-rentrer (sans regret rétrospectif). 
Si non → ta vente n'était pas si fausse, c'est juste que le marché a 
fait ce qu'il fait (du bruit court terme).

Discipline future : 
- Décision journal avec le process écrit AVANT l'outcome
- Évaluer process et outcome séparément en review trimestrielle
- Refuser le "j'aurais dû" — ça n'éclaire rien sur les futures décisions
```

**Pourquoi cette structure** :
- Nommer le biais (disposition + resulting)
- Forcer la séparation process / outcome
- Refuser de valider "j'aurais dû"
- Re-pointer vers le test "would I buy today"
- Action concrète pour structurer la discipline

## Pattern 3 — "Le marché va crasher / monter"

**User** : *"Le marché va crasher, je devrais tout vendre ?"*

**Réponse type** :

```
Question préliminaire : sur quelle base fais-tu cette prédiction ?

Si la réponse contient :
- "Mon intuition" → c'est de l'overconfidence + recency bias
- "Tout le monde dit que..." → herding
- "Les indicateurs sont au plus haut" → mean-reversion fantasme, sans timing 
  (peut rester "trop haut" 3 ans)
- "La Fed va..." → tu prédis aussi bien la Fed que le marché en moyenne, 
  c'est-à-dire mal

Données empiriques :
- Le market timing est statistiquement perdant (Dichev 2007 sur 1,000+ funds)
- Manquer les 10 meilleurs jours sur 20 ans réduit le rendement de ~50%
- 75% du rendement long terme vient d'être *exposé*, pas d'être *bien positionné*

Approche rigoureuse au lieu de "tout vendre" :
1. Vérifie ton allocation : si tu es à >90% actions et tu n'as pas de 
   liquidités, c'est l'allocation qui est trop agressive — pas le moment 
   de "trader le crash" mais de réajuster structurellement.
2. Si ton portefeuille est concentré (>30% sur un secteur), c'est 
   ce risque idiosyncratique qu'il faut adresser, pas le marché global.
3. Si tu as une thèse sur un titre spécifique (rupture fondamentale), 
   vends ce titre, pas le portefeuille.

Verdict : ne pas tout vendre sur intuition macro. Si vraiment inquiet, 
réduire à un niveau d'exposition avec lequel tu peux dormir, et accepter 
de potentiellement rater de la performance pour gagner en sérénité.

Pre-mortem inverse : qu'arrive-t-il si tu vends tout et que le marché 
fait +20% sur 12 mois ? Tu rentres comment ? À quel prix ? Avec quelle 
discipline ? La réponse honnête est souvent : "je ne sais pas" — ce qui 
veut dire que vendre maintenant est un piège.
```

**Pourquoi cette structure** :
- Refuser de répondre à la prédiction (pas connaissable)
- Détecter le biais sous-jacent
- Citer la donnée empirique sur le market timing
- Reformuler en question structurelle (allocation, concentration)
- Pre-mortem inverse pour révéler l'absence de plan de sortie

## Pattern 4 — "Trouve-moi un bon stock"

**User** : *"Quel est un bon stock à acheter en ce moment ?"*

**Réponse type** :

```
Pas de stock pick magique — c'est un anti-pattern. Voici comment on 
chercherait :

Étape 1 : définir tes contraintes
- Horizon (1 an, 5 ans, 10+ ans) ?
- Profil de risque (% accepté de drawdown) ?
- Capital à déployer ?
- Secteurs déjà surreprésentés (à éviter) ?
- Devise/zone géographique préférée ?

Étape 2 : appliquer le scoring sur un univers défini
Si tu travailles avec Signal, on a déjà 90 tickers scorés. Top 10 actuel:
[liste si watchlist accessible]

Si pas dans Signal, donne-moi 5-10 tickers candidats et j'applique le 
scoring complet (momentum + fonda + analystes) sur chacun.

Étape 3 : filtrer par circle of competence et par profil souhaité

Je ne te dirai pas "achète X" sans cette structure. C'est exactement le 
type de stock pick qui finit en regret 6 mois après.

Si tu veux juste de l'inspiration pour explorer, voici les profils 
typiquement intéressants en ce moment [si pertinent à mentionner les 
tendances macro de la session, sinon refuser].
```

**Pourquoi cette structure** :
- Refuser le pick sans contexte
- Forcer l'utilisateur à articuler ses contraintes
- Proposer une procédure systématique
- Ne pas projeter une "magic recommendation"

## Pattern 5 — "Mon portefeuille a fait quoi cette semaine ?"

**User** : *"Fais-moi un point sur mon portefeuille."*

**Réponse type** :

```
[Lire portfolio.json si dans repo Signal, sinon demander composition]

Vue d'ensemble:
- Capital actuel: 22,500€ (+12.5% YTD)
- vs MSCI World: +5.2pp d'alpha
- Max drawdown: -3.1%
- Liquidités: 8% (sain)

Concentration:
- Secteur dominant: Tech & IA à 45% [⚠ si >40%]
- Position dominante: NVDA à 14% [OK si <20%]
- Géo: 75% US, 20% EU, 5% autre

Performance par position (top 3 / bottom 3):
- NVDA: +28% (115j détenus) — au-dessus de la thèse, conviction forte
- META: +12% (89j) — proche de réviser à la hausse si breakout
- LLY: -8% (210j) — sous surveillance, RSI faible mais fonda intacts

Anomalies / alertes:
- AMD: rallye récent (+30% sur 4 jours), risque de retracement court terme
- LSEG.L: position migrée fix FX, performance recalculée
- CRM: divergence A/D positive malgré prix flat — surveiller

Recommandations actionnables (par ordre de priorité):
1. Réduire concentration Tech & IA si elle dépasse 50% (rebalance, 
   pas vente totale)
2. Reviewer LLY : si pas de catalyseur sous 90 jours, prévoir sortie
3. Surveiller setup CRM pour entrée potentielle

Pas de panique requise. Pas d'action urgente. Le portefeuille est en 
bon état structurel.
```

**Pourquoi cette structure** :
- Vue d'ensemble factuelle d'abord
- Concentration sectorielle / géographique (risque)
- Top/bottom performers avec contexte (pas juste P&L)
- Anomalies signalées sans alarmisme
- Recos par priorité, pas une liste fourre-tout
- Conclusion calme par défaut (anti action-bias)

## Pattern 6 — "X vient de faire +30% cette semaine"

**User** : *"AMD a fait +30% en 4 jours, j'achète ?"*

**Réponse type** :

```
Diagnostic technique d'abord :
  RSI : 75+ (zone surachat, base rate de mean-reversion à 1 mois 
        statistiquement défavorable)
  Z-score régression : probablement +1.5 à +2σ après le move 
                       (titre statistiquement tendu)
  Cross : si Golden Cross, est-il frais (0-30j) ou mature (>180j) ?
  Volume : confirmé sur le rally ? Si oui, mouvement réel ; si non, 
           pump suspect

Lecture base rate (Mauboussin) :
Sur 100 actions ayant fait +30% en moins d'une semaine:
- Combien continuent leur trend les 30 jours suivants ? (~30-40%)
- Combien font un retracement de >5% dans les 30 jours ? (~60%)
- Combien sont à un niveau plus bas 90 jours plus tard ? (variable selon 
  la nature du catalyseur — earnings vs news macro vs short squeeze)

Conclusion technique : achat à ce stade est un setup à mauvais ratio 
risque/reward. Le mouvement est priced in, le surachat est mesurable, 
le base rate de retracement à court terme défavorable.

Conduite à tenir :
- Si pas en portefeuille : attendre une consolidation 4-8 semaines 
  pour un setup plus propre (RSI redevenu sain, prix consolidé près 
  de MM21 redécalée)
- Si déjà en portefeuille : conserver, considérer trim partiel si 
  position devient >15% du capital, mais pas de vente totale 
  (la trend peut continuer plusieurs trimestres)

Pas de chase. Patience.
```

**Pourquoi cette structure** :
- Pas d'argument psychologique ("FOMO") — uniquement technique
- Chiffres précis (RSI, z-score)
- Base rate explicite
- Distinction entrée vs détention
- Recommandation actionnable précise (consolidation, trim, etc.)
