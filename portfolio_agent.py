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
from datetime import date, datetime, timedelta
from anthropic import Anthropic

# ── CONFIG ───────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CAPITAL_INITIAL   = 10000.0
POIDS_MAX         = 0.30
TICKER_CAC40      = "^FCHI"
TICKER_MSCI       = "URTH"

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
        hist = yf.Ticker(ticker).history(period="5d")
        return round(float(hist["Close"].iloc[-1]), 2) if not hist.empty else None
    except:
        return None

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

def portfolio_vide():
    return {
        "updated_at": str(date.today()), "week": semaine(),
        "capital_initial": CAPITAL_INITIAL, "capital_actuel": CAPITAL_INITIAL,
        "performance": 0.0, "benchmark_cac40": 0.0, "benchmark_msci": 0.0,
        "vs_benchmark": 0.0, "statut_survie": "en_vie",
        "trimestres_negatifs": 0, "positions": [],
        "liquidites": CAPITAL_INITIAL, "ordres": [], "biais_detectes": [],
        "analyse_claude": None,
    }

# ── PROMPT CLAUDE ────────────────────────────────────────────────────────────
def construire_prompt(portfolio, watchlist, contexte):
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

    # Format watchlist top 10
    top10_lines = []
    for s in watchlist.get("stocks", [])[:10]:
        top10_lines.append(
            f"  #{s['rank']} {s['ticker']} ({s['name']}) — score {s['score']}/100 — {s['sector']} — {s.get('justification', '')}"
        )

    # Tickers watchlist complète
    tickers_watchlist = [s["ticker"] for s in watchlist.get("stocks", [])]

    prompt = f"""Tu es l'IA qui gère le portefeuille fictif WatchRadar. Tu joues ta survie : tu dois battre le CAC40 sur 12 mois glissants ou tu te réinitialises publiquement.

## RÈGLES DE SURVIE (non négociables)
1. Aucune vente avant 90 jours de détention — sauf signal fondamental majeur documenté
2. Maximum 30% du capital sur un seul titre
3. Zéro ajustement en mode panique (CAC40 < -5% sur la semaine) — sauf si mode_panique = false
4. Chaque décision doit être expliquée avec les données qui la motivent
5. Les retours utilisateurs et les erreurs passées doivent influencer les décisions
6. Deux trimestres consécutifs sous le CAC40 = remise à zéro publique

## ÉTAT ACTUEL DU PORTEFEUILLE
- Date : {today}
- Capital : {capital:.0f}€ (performance YTD : {perf:+.1f}% vs CAC40 {bench:+.1f}%, soit {vs:+.1f}pp)
- Liquidités disponibles : {liquidites:.0f}€
- Trimestres négatifs vs benchmark : {trim_neg}/2
- Positions ouvertes ({len(positions)}) :
{chr(10).join(pos_lines) if pos_lines else "  Aucune position"}

## CONTEXTE DE MARCHÉ CETTE SEMAINE
- CAC40 : {contexte.get('cac40', {}).get('perf_semaine', 0):+.1f}% sur la semaine, {contexte.get('cac40', {}).get('perf_ytd', 0):+.1f}% YTD
- MSCI World : {contexte.get('msci', {}).get('perf_semaine', 0):+.1f}% sur la semaine, {contexte.get('msci', {}).get('perf_ytd', 0):+.1f}% YTD
- Mode panique : {"OUI — Règle 03 active, aucun ordre possible" if contexte.get('mode_panique') else "NON — ordres possibles"}

## WATCHLIST CETTE SEMAINE (top 10 sur 25)
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
def executer_decisions(decisions_claude, portfolio, watchlist, contexte):
    """
    Prend les décisions de Claude et les exécute :
    - Calcule les quantités et montants
    - Vérifie les règles hard (90j, 30%, panique)
    - Met à jour le portefeuille
    """
    positions   = portfolio.get("positions", [])
    liquidites  = portfolio.get("liquidites", CAPITAL_INITIAL)
    ordres      = portfolio.get("ordres", [])
    capital     = portfolio.get("capital_actuel", CAPITAL_INITIAL)
    nouveaux_ordres = []
    today = str(date.today())

    stock_map = {s["ticker"]: s for s in watchlist.get("stocks", [])}
    mode_panique = contexte.get("mode_panique", False)

    # Mise à jour des prix actuels
    for pos in positions:
        prix = get_prix(pos["ticker"])
        if prix:
            pos["prix_actuel"]    = prix
            pos["performance"]    = round((prix - pos["prix_achat"]) / pos["prix_achat"] * 100, 2)
            pos["valeur_actuelle"] = round(prix * pos["quantite"], 2)

    decisions = decisions_claude.get("decisions", [])

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
            montant    = round(prix_vente * pos["quantite"], 2)
            perf       = round((prix_vente - pos["prix_achat"]) / pos["prix_achat"] * 100, 2)
            liquidites = round(liquidites + montant, 2)
            positions  = [p for p in positions if p["ticker"] != ticker]

            ordre = {
                "date":    today,
                "type":    "VENTE",
                "ticker":  ticker,
                "nom":     nom,
                "qte":     pos["quantite"],
                "prix":    prix_vente,
                "montant": montant,
                "perf":    perf,
                "jours":   jours,
                "raison":  raison,
                "conviction": dec.get("conviction", "modérée"),
                "source":  "Claude AI",
            }
            nouveaux_ordres.append(ordre)
            print(f"  🔴 VENTE {ticker} — {pos['quantite']} titres à {prix_vente}€ ({perf:+.1f}%) — {dec.get('conviction','?')} conviction")

        # ── ACHAT
        elif action == "ACHAT":
            if mode_panique:
                print(f"  ⚠️  ACHAT {ticker} bloqué — mode panique (Règle 03)")
                continue

            # Déjà en portefeuille ?
            if any(p["ticker"] == ticker for p in positions):
                print(f"  ⚠️  ACHAT {ticker} — déjà en portefeuille, ignoré")
                continue

            # Calcul du budget selon la conviction
            conviction = dec.get("conviction", "modérée")
            if conviction == "forte":
                poids_cible = 0.06
            elif conviction == "modérée":
                poids_cible = 0.04
            else:
                poids_cible = 0.025

            budget  = min(capital * poids_cible, capital * POIDS_MAX, liquidites)
            if budget < 50:
                print(f"  💰 ACHAT {ticker} — liquidités insuffisantes ({liquidites:.0f}€)")
                continue

            prix = get_prix(ticker)
            if not prix or prix <= 0:
                print(f"  ✗ ACHAT {ticker} — prix indisponible")
                continue

            quantite   = max(1, int(budget / prix))
            montant    = round(prix * quantite, 2)
            liquidites = round(liquidites - montant, 2)

            stock = stock_map.get(ticker, {})
            nouvelle_pos = {
                "ticker":          ticker,
                "nom":             nom,
                "market":          stock.get("market", "—"),
                "sector":          stock.get("sector", "—"),
                "date_achat":      today,
                "prix_achat":      prix,
                "prix_actuel":     prix,
                "quantite":        quantite,
                "montant_investi": montant,
                "valeur_actuelle": montant,
                "performance":     0.0,
                "score_entree":    stock.get("score", dec.get("score_watchlist", 0)),
            }
            positions.append(nouvelle_pos)

            ordre = {
                "date":      today,
                "type":      "ACHAT",
                "ticker":    ticker,
                "nom":       nom,
                "qte":       quantite,
                "prix":      prix,
                "montant":   montant,
                "raison":    raison,
                "conviction": conviction,
                "source":    "Claude AI",
                "score_watchlist": stock.get("score", 0),
                "breakdown": stock.get("breakdown", {}),
            }
            nouveaux_ordres.append(ordre)
            print(f"  🟢 ACHAT {ticker} — {quantite} titres à {prix}€ = {montant:.0f}€ (conviction {conviction})")

    return positions, liquidites, nouveaux_ordres

# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    if not client:
        print("❌ ANTHROPIC_API_KEY manquante — ajoutez-la dans les secrets GitHub")
        return

    today     = str(date.today())
    watchlist = load_json("watchlist.json", {})
    portfolio = load_json("portfolio.json", portfolio_vide())

    if not watchlist.get("stocks"):
        print("❌ watchlist.json vide ou manquant")
        return

    print(f"🧠 Appel à Claude API pour les décisions de {semaine()}…")

    # ── Contexte de marché
    contexte = get_contexte_marche()
    print(f"   CAC40 semaine : {contexte.get('cac40', {}).get('perf_semaine', 0):+.1f}%")
    print(f"   Mode panique : {contexte.get('mode_panique')}")

    # ── Mise à jour des prix avant de soumettre à Claude
    for pos in portfolio.get("positions", []):
        prix = get_prix(pos["ticker"])
        if prix:
            pos["prix_actuel"]    = prix
            pos["performance"]    = round((prix - pos["prix_achat"]) / pos["prix_achat"] * 100, 2)
            pos["valeur_actuelle"] = round(prix * pos["quantite"], 2)

    val_pos = sum(p.get("valeur_actuelle", 0) for p in portfolio.get("positions", []))
    portfolio["capital_actuel"] = round(val_pos + portfolio.get("liquidites", CAPITAL_INITIAL), 2)
    portfolio["performance"]    = round((portfolio["capital_actuel"] - CAPITAL_INITIAL) / CAPITAL_INITIAL * 100, 2)

    # ── Appel Claude
    prompt = construire_prompt(portfolio, watchlist, contexte)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system="""Tu es l'IA de gestion du portefeuille fictif WatchRadar.
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
        decisions_claude, portfolio, watchlist, contexte
    )

    # ── Recalcul final
    for pos in positions:
        prix = get_prix(pos["ticker"])
        if prix:
            pos["prix_actuel"]     = prix
            pos["performance"]     = round((prix - pos["prix_achat"]) / pos["prix_achat"] * 100, 2)
            pos["valeur_actuelle"] = round(prix * pos["quantite"], 2)

    val_positions  = sum(p.get("valeur_actuelle", 0) for p in positions)
    capital_actuel = round(val_positions + liquidites, 2)
    performance    = round((capital_actuel - CAPITAL_INITIAL) / CAPITAL_INITIAL * 100, 2)

    for pos in positions:
        pos["poids"] = round(pos["valeur_actuelle"] / capital_actuel * 100, 1) if capital_actuel > 0 else 0

    # Benchmarks
    bench_cac  = contexte.get("cac40", {}).get("perf_ytd", portfolio.get("benchmark_cac40", 0))
    bench_msci = contexte.get("msci",  {}).get("perf_ytd", portfolio.get("benchmark_msci", 0))
    vs_bench   = round(performance - bench_cac, 2)

    trim_neg = portfolio.get("trimestres_negatifs", 0)
    if vs_bench < 0:
        trim_neg = min(trim_neg + 1, 2)
    else:
        trim_neg = max(trim_neg - 1, 0)

    statut = "reinitialisation" if trim_neg >= 2 else "en_vie"

    tous_ordres = nouveaux_ordres + portfolio.get("ordres", [])

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
        "mode_panique":        contexte.get("mode_panique", False),
        "perf_cac_semaine":    contexte.get("cac40", {}).get("perf_semaine", 0),
        "positions":           sorted(positions, key=lambda x: -x.get("performance", 0)),
        "liquidites":          round(liquidites, 2),
        "pct_liquidites":      round(liquidites / capital_actuel * 100, 1) if capital_actuel > 0 else 0,
        "ordres":              tous_ordres[:50],
        "biais_detectes":      decisions_claude.get("biais_detectes", []),
        "nb_positions":        len(positions),
        "nb_positives":        len([p for p in positions if p.get("performance", 0) > 0]),
        "nb_negatives":        len([p for p in positions if p.get("performance", 0) < 0]),
        # Analyse Claude — affiché dans le site
        "analyse_claude": {
            "analyse_macro":      decisions_claude.get("analyse_macro", ""),
            "conviction_globale": decisions_claude.get("conviction_globale", "neutre"),
            "message_utilisateurs": decisions_claude.get("message_utilisateurs", ""),
            "nb_decisions":       len(decisions_claude.get("decisions", [])),
        },
    }

    with open("portfolio.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ portfolio.json généré par Claude")
    print(f"   Capital : {capital_actuel:.0f}€ ({performance:+.1f}%) vs CAC40 {bench_cac:+.1f}%")
    print(f"   Ordres : {len(nouveaux_ordres)} ({sum(1 for o in nouveaux_ordres if o['type']=='ACHAT')} achats, {sum(1 for o in nouveaux_ordres if o['type']=='VENTE')} ventes)")
    print(f"   Analyse : {decisions_claude.get('conviction_globale','?')} — {decisions_claude.get('analyse_macro','')[:100]}…")

if __name__ == "__main__":
    main()
