"""
portfolio_agent.py — Agent de portefeuille piloté par Claude API
C'est Claude qui raisonne sur les décisions d'achat/vente chaque semaine.

Il reçoit :
- L'état actuel du portefeuille (positions, performance, liquidités)
- La watchlist de la semaine (25 actions scorées)
- Le contexte de marché (CAC40, performances sectorielles)
- Les règles de survie

Il décide :
- Quoi acheter, quoi vendre, quoi conserver — et pourquoi

Dépendances : pip install yfinance pandas ta requests anthropic
"""

import yfinance as yf
import json
import os
import requests
from datetime import date, datetime, timedelta
from anthropic import Anthropic

# ── CONFIG ───────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY", "")
FINNHUB_KEY          = os.getenv("FINNHUB_API_KEY", "")
CAPITAL_INITIAL_DEF  = 10000.0   # valeur par défaut uniquement pour portefeuille vide
CAPITAL_INITIAL      = CAPITAL_INITIAL_DEF  # sera écrasé au runtime par la valeur du JSON
POIDS_MAX            = 0.30
STOP_LOSS_PCT        = -15.0     # seuil de stop-loss en % (Règle 07)
MAX_POSITIONS        = 15        # nb max de lignes simultanées
TICKER_CAC40         = "^FCHI"
TICKER_MSCI          = "URTH"

client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

# ── UTILITAIRES ──────────────────────────────────────────────────────────────
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def semaine():
    d = date.today()
    return f"Sem. {d.isocalendar()[1]} · {d.year}"

def get_prix(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if hist.empty:
            print(f"  ⚠️  get_prix({ticker}) — historique vide (marché fermé ou ticker invalide)")
            return None
        prix = float(hist["Close"].iloc[-1])
        try:
            info_curr = getattr(t.fast_info, 'currency', '') or ''
        except Exception:
            info_curr = ''
        if info_curr == 'GBp':
            prix = prix / 100
        return round(prix, 4)
    except Exception as e:
        print(f"  ⚠️  get_prix({ticker}) — erreur fetch : {e}")
        return None

def get_eur_usd_rate():
    """Taux EUR/USD du jour via Yahoo Finance (EURUSD=X). Fallback 1.10."""
    try:
        hist = yf.Ticker("EURUSD=X").history(period="2d")
        return round(float(hist["Close"].iloc[-1]), 4) if not hist.empty else 1.10
    except:
        return 1.10

def detect_currency(ticker, market=""):
    """Détermine la devise native d'un ticker (EUR / USD / GBP)."""
    t = ticker.upper()
    m = (market or "").upper()
    if any(t.endswith(s) for s in [".AS", ".PA", ".DE", ".BR", ".MI", ".MC"]):
        return "EUR"
    if any(k in m for k in ["PAR", "EPA", "AMS", "EURONEXT", "FRA", "XETRA", "ETR", "GER"]):
        return "EUR"
    if t.endswith(".L") or "LSE" in m:
        return "GBP"
    return "USD"

def to_eur(montant, currency, eur_usd):
    """Convertit un montant en devise native vers EUR."""
    if currency == "USD":
        return round(montant / eur_usd, 2)
    if currency == "GBP":
        return round(montant / (eur_usd * 0.86), 2)  # approximation GBP/EUR
    return round(montant, 2)

def get_contexte_marche():
    """Récupère le contexte macro de la semaine."""
    ctx = {}
    annee = date.today().year
    debut = f"{annee}-01-01"

    for label, ticker in [("cac40", TICKER_CAC40), ("msci", TICKER_MSCI)]:
        try:
            hist = yf.Ticker(ticker).history(start=debut)["Close"]
            if len(hist) >= 2:
                perf_ytd    = round((hist.iloc[-1] - hist.iloc[0]) / hist.iloc[0] * 100, 2)
                perf_1sem   = round((hist.iloc[-1] - hist.iloc[-5]) / hist.iloc[-5] * 100, 2) if len(hist) >= 5 else 0
                ctx[label] = {"perf_ytd": perf_ytd, "perf_semaine": perf_1sem}
        except:
            ctx[label] = {"perf_ytd": 0, "perf_semaine": 0}

    # Mode panique
    cac_sem = ctx.get("cac40", {}).get("perf_semaine", 0)
    ctx["mode_panique"] = cac_sem < -5.0
    ctx["date"]         = str(date.today())
    ctx["semaine"]      = semaine()
    return ctx

_MACRO_KEYWORDS = [
    "federal reserve", "fed rate", "fed cuts", "fed hikes", "interest rate",
    "inflation", "cpi", "pce", "pmi", "unemployment", "nonfarm payroll",
    "gdp", "recession", "ecb", "european central bank", "bce",
    "tariff", "trade war", "treasury yield", "yield curve", "10-year",
    "bank of england", "boe rate", "opec",
]

def get_macro_news():
    """Récupère les 4 titres macro les plus pertinents via Finnhub /news.
    Retourne une liste de dicts {headline, date, source} ou liste vide."""
    if not FINNHUB_KEY:
        return []
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&minId=0&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return []
        articles = r.json()
        if not isinstance(articles, list):
            return []
        selected = []
        for article in articles[:60]:
            text = ((article.get("headline") or "") + " " + (article.get("summary") or "")).lower()
            if any(kw in text for kw in _MACRO_KEYWORDS):
                dt = article.get("datetime", 0)
                art_date = datetime.utcfromtimestamp(dt).strftime("%Y-%m-%d") if dt else ""
                selected.append({
                    "headline": (article.get("headline") or "")[:110],
                    "date":     art_date,
                    "source":   article.get("source", ""),
                })
                if len(selected) >= 4:
                    break
        return selected
    except Exception as e:
        print(f"  ⚠️  Macro news — exception : {e}")
        return []

def portfolio_vide():
    return {
        "updated_at": str(date.today()), "week": semaine(),
        "capital_initial": CAPITAL_INITIAL_DEF, "capital_actuel": CAPITAL_INITIAL_DEF,
        "performance": 0.0, "benchmark_cac40": 0.0, "benchmark_msci": 0.0,
        "vs_benchmark": 0.0, "statut_survie": "en_vie",
        "trimestres_negatifs": 0, "dernier_trim_check": "", "positions": [],
        "liquidites": CAPITAL_INITIAL_DEF, "ordres": [], "biais_detectes": [],
        "analyse_claude": None, "performance_history": [], "max_drawdown": 0.0,
    }

def calc_max_drawdown(history):
    """Drawdown sur valeur absolue du capital (en %).
    Utilise le champ 'capital' si disponible, sinon 'perf' en fallback.
    Évite de compter les injections de capital comme des gains."""
    if not history:
        return 0.0
    peak = float('-inf')
    max_dd = 0.0
    for h in history:
        if h.get("capital") is not None:
            v = h["capital"]
        else:
            # Fallback : 'perf' est en %, on reconstitue la valeur sur CAPITAL_INITIAL
            v = CAPITAL_INITIAL * (1 + h.get("perf", 0) / 100)
        if v > peak:
            peak = v
        if peak > 0:
            dd = (v - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd
    return round(max_dd, 2)

# ── PROMPT CLAUDE ────────────────────────────────────────────────────────────
def construire_prompt(portfolio, watchlist, contexte, macro_news=None):
    """Construit le prompt envoyé à Claude avec tout le contexte."""

    positions = portfolio.get("positions", [])
    liquidites = portfolio.get("liquidites", CAPITAL_INITIAL)
    capital = portfolio.get("capital_actuel", CAPITAL_INITIAL)
    perf = portfolio.get("performance", 0)
    bench = portfolio.get("benchmark_cac40", 0)
    vs = portfolio.get("vs_benchmark", 0)
    trim_neg = portfolio.get("trimestres_negatifs", 0)

    today = str(date.today())

    # Format positions
    pos_lines = []
    for p in positions:
        date_achat = p.get("date_achat", "")
        jours = (datetime.today() - datetime.strptime(date_achat, "%Y-%m-%d")).days if date_achat else 0
        pos_lines.append(
            f"  - {p['ticker']} ({p['nom']}) : {p['quantite']} titres, "
            f"acheté à {p['prix_achat']}€, actuel {p.get('prix_actuel', p['prix_achat'])}€, "
            f"perf {p.get('performance', 0):+.1f}%, {jours}j détenus, "
            f"score watchlist actuel: {p.get('score_entree', '?')}/100"
        )

    # Format watchlist top 10 avec signaux cross + régression
    top10_lines = []
    for s in watchlist.get("stocks", [])[:10]:
        bd = s.get("breakdown", {})
        regime = bd.get("cross_regime", "")
        cross_days = bd.get("cross_days_ago")
        z = bd.get("regression_z")
        vol_conf = bd.get("cross_volume_confirmed", False)

        regime_icon = "🟢" if regime == "golden" else "🔴" if regime == "death" else "⚪"
        cross_str = f" | {regime_icon} {regime.upper()} {cross_days}j" if cross_days is not None and regime in ("golden","death") else ""
        vol_str   = " vol✓" if vol_conf else ""
        z_str     = f" | z={z:+.1f}σ" if z is not None else ""

        top10_lines.append(
            f"  #{s['rank']} {s['ticker']} ({s['name']}) — score {s['score']}/100 — {s['sector']}"
            f"{cross_str}{vol_str}{z_str} — {s.get('justification', '')[:100]}"
        )

    # Tickers watchlist complète
    tickers_watchlist = [s["ticker"] for s in watchlist.get("stocks", [])]

    # Section macro news
    if macro_news:
        news_lines = "\n".join(f"  - [{n['date']}] {n['headline']} ({n['source']})" for n in macro_news)
        macro_news_section = f"\n## ACTUALITÉS MACRO RÉCENTES (contexte, ne pas sur-pondérer)\n{news_lines}\n"
    else:
        macro_news_section = ""

    prompt = f"""Tu es l'IA qui gère le portefeuille fictif Signal. Tu joues ta survie : tu dois battre le MSCI World sur 12 mois glissants ou tu te réinitialises publiquement.

## RÈGLES DE SURVIE (non négociables)
1. Aucune vente avant 90 jours de détention — sauf signal fondamental majeur documenté
2. Maximum 30% du capital sur un seul titre
3. Zéro ajustement en mode panique (CAC40 < -5% sur la semaine) — sauf si mode_panique = false
4. Chaque décision doit être expliquée avec les données qui la motivent
5. Les retours utilisateurs et les erreurs passées doivent influencer les décisions
6. Deux trimestres consécutifs sous le MSCI World = remise à zéro publique

## ÉTAT ACTUEL DU PORTEFEUILLE
- Date : {today}
- Capital : {capital:.0f}€ (performance YTD : {perf:+.1f}% vs MSCI World {bench:+.1f}%, soit {vs:+.1f}pp)
- Liquidités disponibles : {liquidites:.0f}€
- Trimestres négatifs vs benchmark : {trim_neg}/2
- Positions ouvertes ({len(positions)}) :
{chr(10).join(pos_lines) if pos_lines else "  Aucune position"}

## CONTEXTE DE MARCHÉ CETTE SEMAINE
- CAC40 : {contexte.get('cac40', {}).get('perf_semaine', 0):+.1f}% sur la semaine, {contexte.get('cac40', {}).get('perf_ytd', 0):+.1f}% YTD
- MSCI World : {contexte.get('msci', {}).get('perf_semaine', 0):+.1f}% sur la semaine, {contexte.get('msci', {}).get('perf_ytd', 0):+.1f}% YTD
- Mode panique : {"OUI — Règle 03 active, aucun ordre possible" if contexte.get('mode_panique') else "NON — ordres possibles"}

{macro_news_section}## WATCHLIST CETTE SEMAINE (top 10 sur 25)
{chr(10).join(top10_lines)}
Tickers watchlist complète : {', '.join(tickers_watchlist)}

## TA MISSION
Analyse la situation et décide des actions à prendre cette semaine.
Pour chaque décision, explique ton raisonnement en tenant compte :
- Du score et de la justification de l'action dans la watchlist
- Du contexte macro de la semaine
- Des règles de survie
- Des erreurs passées (positions perdantes, biais identifiés)

Réponds UNIQUEMENT en JSON valide, sans texte avant ou après, selon ce format exact :

{{
  "decisions": [
    {{
      "action": "ACHAT" | "VENTE" | "CONSERVER",
      "ticker": "XXXX",
      "nom": "Nom de l'action",
      "raison": "Explication détaillée en 2-3 phrases",
      "conviction": "forte" | "modérée" | "faible",
      "score_watchlist": 0
    }}
  ],
  "analyse_macro": "Analyse du contexte de marché en 2-3 phrases",
  "biais_detectes": ["biais 1", "biais 2"],
  "conviction_globale": "haussier" | "neutre" | "baissier",
  "message_utilisateurs": "Message transparent aux utilisateurs sur les décisions de cette semaine"
}}

N'inclus que les décisions actionnables (achats et ventes). Les positions conservées sans changement n'ont pas besoin d'apparaître, sauf si tu veux commenter spécifiquement leur situation.
"""
    return prompt

# ── EXÉCUTION DES DÉCISIONS ──────────────────────────────────────────────────
def executer_decisions(decisions_claude, portfolio, watchlist, contexte, eur_usd=1.10):
    """
    Prend les décisions de Claude et les exécute.
    Toutes les valeurs monétaires sont stockées en EUR (conversion USD→EUR via eur_usd).
    Les prix unitaires restent en devise native pour l'affichage.
    """
    positions   = portfolio.get("positions", [])
    liquidites  = portfolio.get("liquidites", CAPITAL_INITIAL)
    ordres      = portfolio.get("ordres", [])
    capital     = portfolio.get("capital_actuel", CAPITAL_INITIAL)
    nouveaux_ordres = []
    today = str(date.today())

    stock_map = {s["ticker"]: s for s in watchlist.get("stocks", [])}
    mode_panique = contexte.get("mode_panique", False)

    # Mise à jour des prix actuels — valeur_actuelle toujours en EUR
    for pos in positions:
        prix = get_prix(pos["ticker"])
        if prix:
            currency = pos.get("currency") or detect_currency(pos["ticker"], pos.get("market", ""))
            pos["currency"]       = currency
            pos["prix_actuel"]    = prix
            pos["performance"]    = round((prix - pos["prix_achat"]) / pos["prix_achat"] * 100, 2)
            pos["valeur_actuelle"] = to_eur(prix * pos["quantite"], currency, eur_usd)

    # ── Règle 07 : Stop-loss automatique ─────────────────────────────────────
    # Déclenché si perf ≤ -15% ET position détenue ≥ 90 jours ET hors mode panique
    stop_loss_tickers = set()
    if not mode_panique:
        for pos in positions:
            date_achat = pos.get("date_achat", today)
            jours = (datetime.today() - datetime.strptime(date_achat, "%Y-%m-%d")).days
            perf_pos = pos.get("performance", 0)
            if perf_pos <= STOP_LOSS_PCT and jours >= 90:
                stop_loss_tickers.add(pos["ticker"])
                print(f"  🛑 STOP-LOSS {pos['ticker']} — {perf_pos:.1f}% depuis {jours}j → ordre de vente forcé (Règle 07)")

    decisions = decisions_claude.get("decisions", [])

    # Injecter les ventes stop-loss en tête (conviction forte pour bypasser Règle 01 si besoin)
    for ticker_sl in stop_loss_tickers:
        pos_sl = next((p for p in positions if p["ticker"] == ticker_sl), None)
        if pos_sl and not any(d.get("ticker") == ticker_sl and d.get("action","").upper() == "VENTE" for d in decisions):
            decisions.insert(0, {
                "action": "VENTE",
                "ticker": ticker_sl,
                "nom": pos_sl.get("nom", ticker_sl),
                "raison": f"Stop-loss automatique Règle 07 — {pos_sl.get('performance',0):.1f}% depuis l'achat. Seuil −15% atteint après 90+ jours.",
                "conviction": "forte",
            })

    for dec in decisions:
        action = dec.get("action", "").upper()
        ticker = dec.get("ticker", "")
        raison = dec.get("raison", "")
        nom    = dec.get("nom", ticker)

        # ── VENTE
        if action == "VENTE":
            if mode_panique:
                print(f"  ⚠️  VENTE {ticker} bloquée — mode panique (Règle 03)")
                continue

            pos = next((p for p in positions if p["ticker"] == ticker), None)
            if not pos:
                print(f"  ⚠️  VENTE {ticker} — position introuvable")
                continue

            date_achat = pos.get("date_achat", today)
            jours = (datetime.today() - datetime.strptime(date_achat, "%Y-%m-%d")).days

            # Règle 01 : 90 jours minimum
            if jours < 90:
                conviction = dec.get("conviction", "modérée")
                if conviction != "forte":
                    print(f"  ⏳ VENTE {ticker} bloquée — {jours}j < 90j et conviction non forte (Règle 01)")
                    raison = f"[BLOQUÉ — Règle 01 : {jours}j détenus < 90j requis] " + raison
                    dec["raison"] = raison
                    continue

            prix_vente = get_prix(ticker) or pos.get("prix_actuel", pos["prix_achat"])
            currency   = pos.get("currency") or detect_currency(ticker, pos.get("market", ""))
            perf       = round((prix_vente - pos["prix_achat"]) / pos["prix_achat"] * 100, 2)
            montant_eur = to_eur(prix_vente * pos["quantite"], currency, eur_usd)
            liquidites  = round(liquidites + montant_eur, 2)
            positions   = [p for p in positions if p["ticker"] != ticker]

            ordre = {
                "date":     today,
                "type":     "VENTE",
                "ticker":   ticker,
                "nom":      nom,
                "qte":      pos["quantite"],
                "prix":     prix_vente,
                "currency": currency,
                "montant":  montant_eur,
                "perf":     perf,
                "jours":    jours,
                "raison":   raison,
                "conviction": dec.get("conviction", "modérée"),
                "source":   "Claude AI",
            }
            nouveaux_ordres.append(ordre)
            sym = "€" if currency == "EUR" else "$" if currency == "USD" else "£"
            print(f"  🔴 VENTE {ticker} — {pos['quantite']} titres à {prix_vente}{sym} = {montant_eur:.0f}€ ({perf:+.1f}%) — {dec.get('conviction','?')} conviction")

        # ── ACHAT
        elif action == "ACHAT":
            if mode_panique:
                print(f"  ⚠️  ACHAT {ticker} bloqué — mode panique (Règle 03)")
                continue

            # Déjà en portefeuille ?
            if any(p["ticker"] == ticker for p in positions):
                print(f"  ⚠️  ACHAT {ticker} — déjà en portefeuille, ignoré")
                continue

            # Allocation dynamique : slots calculés sur l'ensemble des achats décidés (order-independent)
            conviction    = dec.get("conviction", "modérée")
            nb_open       = len(positions)
            nb_achats_total = sum(1 for d2 in decisions if d2.get("action","").upper() == "ACHAT")
            slots_restants  = max(1, MAX_POSITIONS - nb_open - nb_achats_total)
            equal_weight   = liquidites / slots_restants

            if conviction == "forte":
                poids_cible = 0.07
            elif conviction == "modérée":
                poids_cible = 0.05
            else:
                poids_cible = 0.03

            budget = min(capital * poids_cible, capital * POIDS_MAX, equal_weight, liquidites)
            if budget < 50:
                print(f"  💰 ACHAT {ticker} — liquidités insuffisantes ({liquidites:.0f}€)")
                continue

            prix = get_prix(ticker)
            if not prix or prix <= 0:
                print(f"  ✗ ACHAT {ticker} — prix indisponible")
                continue

            stock    = stock_map.get(ticker, {})
            currency = detect_currency(ticker, stock.get("market", ""))
            prix_eur = to_eur(prix, currency, eur_usd)

            # Budget en EUR → quantité basée sur prix converti
            quantite     = max(1, int(budget / prix_eur))
            montant_eur  = round(prix_eur * quantite, 2)
            liquidites   = round(liquidites - montant_eur, 2)

            nouvelle_pos = {
                "ticker":          ticker,
                "nom":             nom,
                "market":          stock.get("market", "—"),
                "sector":          stock.get("sector", "—"),
                "currency":        currency,
                "date_achat":      today,
                "prix_achat":      prix,       # devise native (affichage)
                "prix_actuel":     prix,
                "quantite":        quantite,
                "montant_investi": montant_eur,  # en EUR
                "valeur_actuelle": montant_eur,  # en EUR
                "performance":     0.0,
                "score_entree":    stock.get("score", dec.get("score_watchlist", 0)),
            }
            positions.append(nouvelle_pos)

            sym = "€" if currency == "EUR" else "$" if currency == "USD" else "£"
            ordre = {
                "date":      today,
                "type":      "ACHAT",
                "ticker":    ticker,
                "nom":       nom,
                "qte":       quantite,
                "prix":      prix,
                "currency":  currency,
                "montant":   montant_eur,  # en EUR
                "raison":    raison,
                "conviction": conviction,
                "source":    "Claude AI",
                "score_watchlist": stock.get("score", 0),
                "breakdown": stock.get("breakdown", {}),
            }
            nouveaux_ordres.append(ordre)
            print(f"  🟢 ACHAT {ticker} — {quantite} titres à {prix}{sym} = {montant_eur:.0f}€ (conviction {conviction})")

    return positions, liquidites, nouveaux_ordres

# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    if not client:
        print("❌ ANTHROPIC_API_KEY manquante — ajoutez-la dans les secrets GitHub")
        return

    today     = str(date.today())
    watchlist = load_json("watchlist.json", {})
    portfolio = load_json("portfolio.json", portfolio_vide())

    # Lire capital_initial depuis le JSON (pas hardcodé) — corrige le bug post-injection
    global CAPITAL_INITIAL
    CAPITAL_INITIAL = portfolio.get("capital_initial", CAPITAL_INITIAL_DEF)

    if not watchlist.get("stocks"):
        print("❌ watchlist.json vide ou manquant")
        return

    print(f"🧠 Appel à Claude API pour les décisions de {semaine()}…")

    # ── Contexte de marché + taux de change + macro news
    contexte    = get_contexte_marche()
    eur_usd     = get_eur_usd_rate()
    macro_news  = get_macro_news()
    print(f"   CAC40 semaine : {contexte.get('cac40', {}).get('perf_semaine', 0):+.1f}%")
    print(f"   Mode panique  : {contexte.get('mode_panique')}")
    print(f"   EUR/USD       : {eur_usd}")
    print(f"   Macro news    : {len(macro_news)} article(s) macro sélectionné(s)")

    # ── Mise à jour des prix avant de soumettre à Claude (valeur_actuelle en EUR)
    for pos in portfolio.get("positions", []):
        prix = get_prix(pos["ticker"])
        if prix:
            currency = pos.get("currency") or detect_currency(pos["ticker"], pos.get("market", ""))
            pos["currency"]        = currency
            pos["prix_actuel"]     = prix
            pos["performance"]     = round((prix - pos["prix_achat"]) / pos["prix_achat"] * 100, 2)
            pos["valeur_actuelle"] = to_eur(prix * pos["quantite"], currency, eur_usd)

    val_pos = sum(p.get("valeur_actuelle", 0) for p in portfolio.get("positions", []))
    portfolio["capital_actuel"] = round(val_pos + portfolio.get("liquidites", CAPITAL_INITIAL), 2)
    portfolio["performance"]    = round((portfolio["capital_actuel"] - CAPITAL_INITIAL) / CAPITAL_INITIAL * 100, 2)

    # ── Appel Claude
    prompt = construire_prompt(portfolio, watchlist, contexte, macro_news)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=5000,
            system="""Tu es l'IA de gestion du portefeuille fictif Signal.
Tu raisonnes sur des décisions d'investissement fictives à partir de données réelles.
Tu es analytique, honnête sur tes erreurs, et transparent sur ton raisonnement.
Tu réponds UNIQUEMENT en JSON valide, sans aucun texte avant ou après.
Ne jamais inclure de balises markdown ou de backticks.""",
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        # Nettoyer les éventuels backticks markdown
        raw = raw.replace("```json", "").replace("```", "").strip()

        decisions_claude = json.loads(raw)
        print(f"   ✅ Claude a pris {len(decisions_claude.get('decisions', []))} décision(s)")
        print(f"   Conviction globale : {decisions_claude.get('conviction_globale', '?')}")

    except json.JSONDecodeError as e:
        print(f"❌ Erreur parsing JSON Claude : {e}")
        print(f"   Réponse brute : {raw[:200]}")
        decisions_claude = {"decisions": [], "analyse_macro": "Erreur parsing", "biais_detectes": [], "conviction_globale": "neutre"}
    except Exception as e:
        print(f"❌ Erreur appel Claude : {e}")
        decisions_claude = {"decisions": [], "analyse_macro": f"Erreur : {e}", "biais_detectes": [], "conviction_globale": "neutre"}

    # ── Exécution des décisions
    positions, liquidites, nouveaux_ordres = executer_decisions(
        decisions_claude, portfolio, watchlist, contexte, eur_usd
    )

    # ── Recalcul final — valeur_actuelle toujours en EUR
    for pos in positions:
        prix = get_prix(pos["ticker"])
        if prix:
            currency = pos.get("currency") or detect_currency(pos["ticker"], pos.get("market", ""))
            pos["currency"]        = currency
            pos["prix_actuel"]     = prix
            pos["performance"]     = round((prix - pos["prix_achat"]) / pos["prix_achat"] * 100, 2)
            pos["valeur_actuelle"] = to_eur(prix * pos["quantite"], currency, eur_usd)

    val_positions  = sum(p.get("valeur_actuelle", 0) for p in positions)
    capital_actuel = round(val_positions + liquidites, 2)
    performance    = round((capital_actuel - CAPITAL_INITIAL) / CAPITAL_INITIAL * 100, 2)

    for pos in positions:
        pos["poids"] = round(pos["valeur_actuelle"] / capital_actuel * 100, 1) if capital_actuel > 0 else 0

    # Benchmarks — MSCI World comme référence primaire (portefeuille ~70% US, global)
    bench_cac  = contexte.get("cac40", {}).get("perf_ytd", portfolio.get("benchmark_cac40", 0))
    bench_msci = contexte.get("msci",  {}).get("perf_ytd", portfolio.get("benchmark_msci", 0))
    vs_bench   = round(performance - bench_msci, 2)

    # ── Trimestres négatifs — évaluation une seule fois par trimestre ──────────
    trim_neg = portfolio.get("trimestres_negatifs", 0)
    d_today  = date.today()
    trimestre_actuel = f"{d_today.year}-Q{(d_today.month - 1) // 3 + 1}"
    dernier_trim_check = portfolio.get("dernier_trim_check", "")

    if trimestre_actuel != dernier_trim_check:
        if vs_bench < 0:
            trim_neg = min(trim_neg + 1, 2)
        else:
            trim_neg = max(trim_neg - 1, 0)
        dernier_trim_check = trimestre_actuel
    # Sinon : trimestre déjà compté, on ne change pas trim_neg cette semaine

    statut = "reinitialisation" if trim_neg >= 2 else "en_vie"

    tous_ordres = nouveaux_ordres + portfolio.get("ordres", [])

    # ── Historique de performance (une entrée par run, max 52 semaines) ──────
    history = portfolio.get("performance_history", [])
    if not any(h.get("date") == today for h in history):
        history.append({"date": today, "perf": performance, "capital": capital_actuel, "benchmark_cac40": bench_cac, "benchmark_msci": bench_msci})
    history = history[-52:]
    max_dd = calc_max_drawdown(history)

    output = {
        "updated_at":          today,
        "week":                semaine(),
        "capital_initial":     CAPITAL_INITIAL,
        "capital_actuel":      capital_actuel,
        "performance":         performance,
        "benchmark_cac40":     bench_cac,
        "benchmark_msci":      bench_msci,
        "vs_benchmark":        vs_bench,
        "statut_survie":       statut,
        "trimestres_negatifs": trim_neg,
        "dernier_trim_check":  dernier_trim_check,
        "mode_panique": bool(contexte.get("mode_panique", False)),
        "perf_cac_semaine": float(contexte.get("cac40", {}).get("perf_semaine", 0)),
        "positions":           sorted(positions, key=lambda x: -x.get("performance", 0)),
        "liquidites":          round(liquidites, 2),
        "pct_liquidites":      round(liquidites / capital_actuel * 100, 1) if capital_actuel > 0 else 0,
        "ordres":              tous_ordres[:50],
        "biais_detectes":      decisions_claude.get("biais_detectes", []),
        "nb_positions":        len(positions),
        "nb_positives":        len([p for p in positions if p.get("performance", 0) > 0]),
        "nb_negatives":        len([p for p in positions if p.get("performance", 0) < 0]),
        "nb_neutres":          len([p for p in positions if p.get("performance", 0) == 0.0]),
        # Analyse Claude — affiché dans le site
        "analyse_claude": {
            "analyse_macro":        decisions_claude.get("analyse_macro", ""),
            "conviction_globale":   decisions_claude.get("conviction_globale", "neutre"),
            "message_utilisateurs": decisions_claude.get("message_utilisateurs", ""),
            "nb_decisions":         len(decisions_claude.get("decisions", [])),
        },
        "performance_history": history,
        "max_drawdown":         max_dd,
    }

    with open("portfolio.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ portfolio.json généré par Claude")
    print(f"   Capital : {capital_actuel:.0f}€ ({performance:+.1f}%) vs CAC40 {bench_cac:+.1f}%")
    print(f"   Ordres : {len(nouveaux_ordres)} ({sum(1 for o in nouveaux_ordres if o['type']=='ACHAT')} achats, {sum(1 for o in nouveaux_ordres if o['type']=='VENTE')} ventes)")
    print(f"   Analyse : {decisions_claude.get('conviction_globale','?')} — {decisions_claude.get('analyse_macro','')[:100]}…")

if __name__ == "__main__":
    main()
