# Changelog — Signal

Toutes les évolutions notables du projet sont documentées ici.
Format inspiré de [keepachangelog.com](https://keepachangelog.com/fr/).

---

## [1.6.0] — 2026-05-10

### Architecture (portfolio_agent.py + sync_skill.py) — alignement skill ↔ prod

**Le skill `portfolio-analyst` existe désormais à 2 niveaux** :
- **User-level** : `~/.claude/skills/portfolio-analyst/` — master éditable. Claude Code en local le charge en priorité (hiérarchie personal > project) pour toutes les questions portfolio, dans ou hors repo Signal.
- **Project-level** : `<repo>/.claude/skills/portfolio-analyst/` — copie synchronisée, committée dans Git, déployée avec le code. Lue par `portfolio_agent.py` sur le runner GitHub Actions où le user-level n'existe pas.

**Synchronisation user-level → project-level via `sync_skill.py`** :
- Direction : user-level (master éditable) → project-level (copie déployable)
- Usage : `python sync_skill.py` avant chaque commit qui touche le skill
- Mode `--check` pour CI / pre-commit hook (échoue si désynchronisé)
- Pourquoi cette direction : tu édites naturellement le user-level via Claude Code, et Claude Code en local prime sur project-level de toute façon (hiérarchie)

**`load_skill_discipline()` (portfolio_agent.py)** :
- Lit désormais le project-level via chemin **relatif** : `Path(__file__).parent / ".claude" / "skills" / "portfolio-analyst" / "SKILL.md"`
- Marche partout où le repo est cloné (runner GitHub Actions inclus)
- Bug d'architecture v1.6.0-rc1 corrigé : la version initiale lisait `Path.home()` qui n'existe pas sur le runner

### Prompt agent (portfolio_agent.py)
- **Injection skill au début du prompt passe 2** via `load_skill_discipline()` — single source of truth
- **Watchlist top 10 enrichie** (passes 1 et 2) : ajout de `cross_slope_mm21_pct`, `cross_spread_pct` et **`signal_dynamics_warning`** (death cross qui se résorbe, golden qui s'affaiblit, rebond mean-reversion sur cross stale, affaiblissement post-rally). L'agent peut désormais lire le signal **en mouvement**, plus statiquement.
- **Règles non négociables 7 et 8** ajoutées :
  - R7 — Signal en transition : si `signal_dynamics_warning` non-vide, traiter le cross technique comme ambigu, ne pas vendre/acheter sur ce signal seul
  - R8 — Cross-validation analystes/cours : pour titres en zone d'incertitude (score 30-65), si consensus très favorable mais cours en dégradation 6-12m, suspecter une dégradation des données screener (effet change, périmètre M&A, désync data)
- **Watchlist top 10 enrichie** (passes 1 et 2) : ajout de `cross_slope_mm21_pct`, `cross_spread_pct` et **`signal_dynamics_warning`** (death cross qui se résorbe, golden qui s'affaiblit, rebond mean-reversion sur cross stale, affaiblissement post-rally). L'agent peut désormais lire le signal **en mouvement**, plus statiquement.
- **Règles non négociables 7 et 8** ajoutées :
  - R7 — Signal en transition : si `signal_dynamics_warning` non-vide, traiter le cross technique comme ambigu, ne pas vendre/acheter sur ce signal seul
  - R8 — Cross-validation analystes/cours : pour titres en zone d'incertitude (score 30-65), si consensus très favorable mais cours en dégradation 6-12m, suspecter une dégradation des données screener (effet change, périmètre M&A, désync data)

### Scoring (screener.py)
- **`signal_dynamics_warning`** étendu : 4 conditions désormais détectées
  - Death Cross en cours de résorption (récent + pente MM21 positive + spread tendu)
  - Golden Cross en cours d'affaiblissement (récent + pente MM21 négative + spread tendu)
  - **Rebond mean-reversion sur cross stale** (death stale + pente MM21 forte + cours largement sous MM200) — setup B opportunities.md
  - **Affaiblissement post-rally sur cross stale** (golden stale + pente MM21 négative + cours largement au-dessus MM200)
- **Archive snapshot hebdo** : `notes/watchlist_archive/YYYY-MM-DD.json` créé à chaque run du screener. Permet dans 6+ mois de reconstituer un historique fonda point-in-time pour backtester les 60% du score (Fondamentaux + Analystes) actuellement non testés (limitation reconnue ligne 12-14 de backtest.py).

### Validation
- Backtest baseline 2026-05-10 : Alpha CAGR **+13.68pp/an**, Sharpe **1.68 vs 0.95 SPY**, Max DD **-22.70%**, Win rate **65.2%** sur 281 semaines (2019-2024). Cohérent avec methodology.md (+13.5pp).
- Note honnête : `backtest.py` simule la stratégie momentum-only (top N → achat mécanique). **Il ne simule pas Claude.** Les modifs prompt agent n'apparaîtront pas dans ce backtest. Validation des règles 7/8 nécessite observation live sur 4-8 semaines.

---

## [1.5.0] — 2026-05-06

### Architecture (portfolio_agent.py)
- **Deux passes Claude** : séparation analyste / décideur pour éviter la rationalisation LLM
  - Passe 1 (Claude Haiku) : analyse neutre de chaque position et opportunité — sans décision
  - Passe 2 (Claude Sonnet) : décisions basées sur l'analyse + thèses d'achat originales
- **Mémoire de la thèse d'achat** : `raison_achat` stockée dans chaque position au moment de l'achat
- **Obligation de delta documenté** : pour toute vente < 90j, le modèle doit citer la thèse d'achat originale et expliquer ce qui a concrètement changé — même signal relu différemment = vente refusée
- Analyse passe 1 injectée dans le prompt passe 2 (delta_these, état, qualité signal watchlist)

---

## [1.4.0] — 2026-05-06

### Scoring (screener.py)
- **Free Cash Flow margin** ajouté aux fondamentaux : +5 pts si FCF/CA > 15 %, +3 pts si > 5 %
  - Complémentaire à la marge nette — cap fondamentaux maintenu à 50 pts
- **Pénalité Death Cross** : −5 pts si Death Cross ≤ 30j, −3 pts si ≤ 60j (appliqué post-confiance, non compensable)
- **Changelog enrichi** : raisons de sortie spécifiques (Death Cross, momentum faible, fondamentaux insuffisants, surachat régression) au lieu du message générique
- `fcf_margin_pct` et `death_pen` ajoutés au breakdown JSON

### UX (index.html)
- **Tri alternatif** : boutons Score global / Fondamentaux / Momentum, actifs en temps réel et compatibles avec les filtres existants

### UX (portfolio.html)
- **Journal enrichi** : badge P&L réalisé + jours détenus sur les VENTE, badge score d'entrée sur les ACHAT
- **Stats P&L réalisé** : bloc résumé (trades clôturés, win rate, performance moyenne, P&L € cumulé)
- 20 ordres affichés par défaut avec bouton "voir les suivants"

---

## [1.3.0] — 2026-05-05

### Scoring (screener.py)
- **RSI gradué** : 10 pts en zone 40–60, 5 pts en 35–65, 0 sinon (remplace le binaire 10/0)
- **Fondamentaux 50 pts** (était 40) : redistribution depuis les analystes
  - PEG ratio : nouveau palier PEG < 1 → 15 pts (était 10 max)
  - EPS growth (`earningsGrowth` Yahoo Finance) ajouté : +5 pts si > 15 %, +2 pts si > 5 %
- **Analystes 10 pts** (était 20) : biais haussier structurel sell-side documenté (Barber 2001, Jegadeesh 2004)
- `min(50, fund_pts)` et `min(10, ana_pts)` dans le breakdown

### Contenu (index.html)
- Section "Comment fonctionne le scoring" mise à jour : RSI gradué, Analystes 10 pts, détail PEG
- **Section Lexique** ajoutée : 17 définitions en 4 catégories (Signaux techniques, Régression, Fondamentaux, Score & Consensus)

---

## [1.2.0] — 2026-05-05

### Refonte visuelle (portfolio.html)
- Thème dark complet aligné sur index.html (palette `#08080d` / `#0f0f16` / or `#e8a820`)
- Header frosted glass, card glow au survol
- SVG graphique de performance : gold `#e8a820`, grid `#2a2a38`, MSCI `#44445a`
- Correction couleurs SVG hardcodées (étaient `#d97706`)

---

## [1.1.0] — 2026-05-04

### Renommage WatchRadar → Signal
- Nom du projet, titres de pages, brand header, prompts Claude
- Email fictif `contact@watchradar.fr` supprimé (HTML statique + JS)
- Git bot identity : `bot@signal.fr` / `Signal Bot`
- Repo GitHub renommé `Kosmos-7/Signal`

### Refonte visuelle (index.html)
- Palette dark modernisée : `--bg: #08080d`, `--surface: #0f0f16`, or `#e8a820`
- Header sticky frosted glass (`rgba(8,8,13,0.88)` + `backdrop-filter: blur(20px)`)
- Hover cards : inset glow + `box-shadow` extérieur
- Score bars fondamentaux et analystes corrigés (`/50` et `/10`)

---

## [1.0.0] — Lancement initial

### Screener (screener.py)
- Univers de 90 valeurs (CAC40, DAX, AEX, OMX, LSE, S&P100, APAC)
- Scoring : Momentum (Golden/Death Cross MM21/MM200, RSI, volume, régression) + Fondamentaux + Analystes
- Régression log-linéaire avec z-score et fenêtres adaptées (10 ans tech, 20 ans autres)
- Validation croisée Finnhub + alertes news (guidance, M&A, réglementaire)
- Bonus sectoriel +3 pts (Technologie, Santé, Industrie, Finance)
- Concentration sectorielle alertée si > 5 titres dans un même secteur
- Export `watchlist.json` avec breakdown complet, changelog, distribution sectorielle

### Portfolio agent (portfolio_agent.py)
- Agent piloté par Claude Sonnet via Anthropic API
- Capital fictif 20 000 €, règles de survie (patience 90j, taille max 30 %, mode panique, stop-loss −15 %)
- Conversion multi-devises EUR/USD/GBP temps réel
- Historique de performance (52 semaines), max drawdown, trimestres négatifs
- Macro news via Finnhub, contexte CAC40 + MSCI World
- Export `portfolio.json`

### Interface (index.html + portfolio.html)
- Watchlist : fiches détaillées avec breakdown scoring, croisement MM21/MM200, régression, alertes news
- Portfolio : statut de survie, KPI, graphique SVG de performance, journal des ordres
- Filtres régime (Golden/Death Cross) et zone de régression
- GitHub Actions : workflow `watchlist.yml`, cron lundi 8h UTC, déploiement GitHub Pages
