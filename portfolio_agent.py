"""
portfolio_agent.py — Agent de gestion du portefeuille fictif WatchRadar
Tourne chaque lundi après screener.py via GitHub Actions.
Lit watchlist.json, prend des décisions d'achat/vente, génère portfolio.json.

Règles de survie :
- Aucune vente avant 90 jours (sauf signal fondamental majeur)
- Maximum 30% sur un seul titre
- Zéro ajustement si CAC40 chute > 5% sur la semaine
- Deux trimestres négatifs vs CAC40 = remise à zéro publique
"""

import yfinance as yf
import json
import os
from datetime import date, datetime, timedelta

# ── CONFIG ───────────────────────────────────────────────────────────────────
CAPITAL_INITIAL    = 10000.0   # Capital fictif de départ en euros
POIDS_MAX          = 0.30      # 30% max par position
POIDS_CIBLE        = 0.04      # ~4% par position (25 actions × 4% = 100%)
JOURS_MIN_HOLD     = 90        # Règle 01 : pas de vente avant 90 jours
SEUIL_PANIQUE      = -0.05     # Règle 03 : pas d'action si CAC40 < -5% semaine
TICKER_CAC40       = "^FCHI"
TICKER_MSCI        = "URTH"    # ETF MSCI World

# ── CHARGEMENT ───────────────────────────────────────────────────────────────
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def portfolio_vide():
    return {
        "updated_at":      str(date.today()),
        "week":            semaine(),
        "capital_initial": CAPITAL_INITIAL,
        "capital_actuel":  CAPITAL_INITIAL,
        "performance":     0.0,
        "benchmark_cac40": 0.0,
        "benchmark_msci":  0.0,
        "vs_benchmark":    0.0,
        "statut_survie":   "en_vie",
        "trimestres_negatifs": 0,
        "positions":       [],
        "liquidites":      CAPITAL_INITIAL,
        "ordres":          [],
        "postmortem":      None,
    }

def semaine():
    d = date.today()
    return f"Sem. {d.isocalendar()[1]} · {d.year}"

# ── PRIX RÉELS ───────────────────────────────────────────────────────────────
def get_prix(ticker):
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="5d")
        if hist.empty:
            return None
        return round(float(hist["Close"].iloc[-1]), 2)
    except:
        return None

def get_perf_semaine(ticker):
    """Retourne la performance sur 7 jours glissants."""
    try:
        hist = yf.Ticker(ticker).history(period="10d")["Close"]
        if len(hist) < 2:
            return 0.0
        return float((hist.iloc[-1] - hist.iloc[0]) / hist.iloc[0])
    except:
        return 0.0

def get_perf_depuis(ticker, date_achat_str):
    """Retourne la perf depuis une date donnée (format YYYY-MM-DD)."""
    try:
        start = datetime.strptime(date_achat_str, "%Y-%m-%d") - timedelta(days=3)
        hist  = yf.Ticker(ticker).history(start=start.strftime("%Y-%m-%d"))["Close"]
        if len(hist) < 2:
            return 0.0
        return float((hist.iloc[-1] - hist.iloc[0]) / hist.iloc[0])
    except:
        return 0.0

# ── LOGIQUE PRINCIPALE ───────────────────────────────────────────────────────
def main():
    today     = str(date.today())
    watchlist = load_json("watchlist.json", {})
    portfolio = load_json("portfolio.json", portfolio_vide())

    stocks_watchlist = watchlist.get("stocks", [])
    tickers_watchlist = {s["ticker"] for s in stocks_watchlist}

    positions   = portfolio.get("positions", [])
    liquidites  = portfolio.get("liquidites", CAPITAL_INITIAL)
    ordres      = portfolio.get("ordres", [])

    nouveaux_ordres = []
    biais_detectes  = []

    # ── Règle 03 : vérifier panique de marché ─────────────────────────────
    perf_cac_semaine = get_perf_semaine(TICKER_CAC40)
    mode_panique = perf_cac_semaine < SEUIL_PANIQUE

    if mode_panique:
        print(f"⚠️  Mode panique activé (CAC40 semaine : {perf_cac_semaine:.1%}) — aucun ordre.")
        biais_detectes.append(f"Mode panique : CAC40 à {perf_cac_semaine:.1%} cette semaine. Zéro ajustement appliqué (Règle 03).")

    # ── Mise à jour des prix des positions existantes ─────────────────────
    valeur_positions = 0.0
    positions_mises_a_jour = []

    for pos in positions:
        prix_actuel = get_prix(pos["ticker"])
        if prix_actuel is None:
            prix_actuel = pos.get("prix_actuel", pos["prix_achat"])

        perf = round((prix_actuel - pos["prix_achat"]) / pos["prix_achat"] * 100, 2)
        valeur = round(prix_actuel * pos["quantite"], 2)
        valeur_positions += valeur

        pos["prix_actuel"] = prix_actuel
        pos["performance"] = perf
        pos["valeur_actuelle"] = valeur
        positions_mises_a_jour.append(pos)
        print(f"  📊 {pos['ticker']} : {prix_actuel:.2f}€ ({perf:+.1f}%)")

    positions = positions_mises_a_jour
    capital_total = round(valeur_positions + liquidites, 2)

    # ── Ventes : positions hors watchlist depuis > 90 jours ───────────────
    if not mode_panique:
        positions_a_garder = []
        for pos in positions:
            date_achat = datetime.strptime(pos["date_achat"], "%Y-%m-%d")
            jours_detenus = (datetime.today() - date_achat).days
            dans_watchlist = pos["ticker"] in tickers_watchlist

            if not dans_watchlist and jours_detenus >= JOURS_MIN_HOLD:
                prix_vente = pos["prix_actuel"]
                montant    = round(prix_vente * pos["quantite"], 2)
                liquidites += montant
                capital_total = round(valeur_positions - pos["valeur_actuelle"] + liquidites, 2)

                ordre = {
                    "date":    today,
                    "type":    "VENTE",
                    "ticker":  pos["ticker"],
                    "nom":     pos["nom"],
                    "qte":     pos["quantite"],
                    "prix":    prix_vente,
                    "montant": montant,
                    "raison":  f"Sortie de watchlist après {jours_detenus}j — Règle 01 respectée"
                }
                nouveaux_ordres.append(ordre)
                print(f"  🔴 VENTE {pos['ticker']} — {jours_detenus}j détenus, hors watchlist")
            else:
                if not dans_watchlist and jours_detenus < JOURS_MIN_HOLD:
                    print(f"  ⏳ {pos['ticker']} hors watchlist mais {jours_detenus}j < {JOURS_MIN_HOLD}j — conservé (Règle 01)")
                positions_a_garder.append(pos)

        positions = positions_a_garder

    # ── Achats : nouvelles entrées dans la watchlist ───────────────────────
    if not mode_panique:
        tickers_en_portefeuille = {p["ticker"] for p in positions}

        for stock in stocks_watchlist:
            if stock["ticker"] in tickers_en_portefeuille:
                continue

            # Budget cible pour cette position
            budget = round(capital_total * POIDS_CIBLE, 2)
            budget = min(budget, capital_total * POIDS_MAX)

            if liquidites < budget * 0.5:
                print(f"  💰 Liquidités insuffisantes pour {stock['ticker']} ({liquidites:.0f}€ dispo)")
                continue

            budget = min(budget, liquidites)
            prix   = get_prix(stock["ticker"])
            if prix is None or prix <= 0:
                print(f"  ✗ Prix indisponible pour {stock['ticker']}")
                continue

            quantite = max(1, int(budget / prix))
            montant  = round(prix * quantite, 2)
            liquidites = round(liquidites - montant, 2)

            nouvelle_pos = {
                "ticker":         stock["ticker"],
                "nom":            stock["nom"],
                "market":         stock["market"],
                "sector":         stock["sector"],
                "date_achat":     today,
                "prix_achat":     prix,
                "prix_actuel":    prix,
                "quantite":       quantite,
                "montant_investi": montant,
                "valeur_actuelle": montant,
                "performance":    0.0,
                "score_entree":   stock["score"],
            }
            positions.append(nouvelle_pos)

            ordre = {
                "date":    today,
                "type":    "ACHAT",
                "ticker":  stock["ticker"],
                "nom":     stock["nom"],
                "qte":     quantite,
                "prix":    prix,
                "montant": montant,
                "raison":  f"Entrée watchlist — score {stock['score']}/100 · {stock['sector']}"
            }
            nouveaux_ordres.append(ordre)
            print(f"  🟢 ACHAT {stock['ticker']} — {quantite} titres à {prix:.2f}€ = {montant:.0f}€")

    # ── Recalcul valeur totale ─────────────────────────────────────────────
    valeur_positions = sum(p["valeur_actuelle"] for p in positions)
    capital_actuel   = round(valeur_positions + liquidites, 2)
    performance      = round((capital_actuel - CAPITAL_INITIAL) / CAPITAL_INITIAL * 100, 2)

    # ── Poids de chaque position ───────────────────────────────────────────
    for pos in positions:
        pos["poids"] = round(pos["valeur_actuelle"] / capital_actuel * 100, 1) if capital_actuel > 0 else 0

    # ── Benchmark CAC40 ───────────────────────────────────────────────────
    try:
        cac_hist = yf.Ticker(TICKER_CAC40).history(start="2026-01-01")["Close"]
        if len(cac_hist) >= 2:
            bench_cac = round((float(cac_hist.iloc[-1]) - float(cac_hist.iloc[0])) / float(cac_hist.iloc[0]) * 100, 2)
        else:
            bench_cac = portfolio.get("benchmark_cac40", 0.0)
    except:
        bench_cac = portfolio.get("benchmark_cac40", 0.0)

    try:
        msci_hist = yf.Ticker(TICKER_MSCI).history(start="2026-01-01")["Close"]
        if len(msci_hist) >= 2:
            bench_msci = round((float(msci_hist.iloc[-1]) - float(msci_hist.iloc[0])) / float(msci_hist.iloc[0]) * 100, 2)
        else:
            bench_msci = portfolio.get("benchmark_msci", 0.0)
    except:
        bench_msci = portfolio.get("benchmark_msci", 0.0)

    vs_benchmark = round(performance - bench_cac, 2)

    # ── Statut de survie ──────────────────────────────────────────────────
    trimestres_negatifs = portfolio.get("trimestres_negatifs", 0)
    if vs_benchmark < 0:
        trimestres_negatifs = min(trimestres_negatifs + 1, 2)
    else:
        trimestres_negatifs = max(trimestres_negatifs - 1, 0)

    statut = "reinitialisation" if trimestres_negatifs >= 2 else "en_vie"
    if statut == "reinitialisation":
        biais_detectes.append("⚠️ Deux trimestres consécutifs sous le CAC40. Remise à zéro de la méthodologie en cours.")

    # ── Historique des ordres ─────────────────────────────────────────────
    tous_ordres = nouveaux_ordres + ordres
    tous_ordres = tous_ordres[:50]  # Garder les 50 derniers

    # ── Biais auto-détectés ───────────────────────────────────────────────
    positions_perdantes = [p for p in positions if p["performance"] < -10]
    if len(positions_perdantes) > 3:
        biais_detectes.append(f"{len(positions_perdantes)} positions en perte > 10% — vérifier si le scoring sous-estime le risque macro.")

    poids_max_pos = max((p["poids"] for p in positions), default=0)
    if poids_max_pos > 25:
        biais_detectes.append(f"Concentration excessive détectée ({poids_max_pos:.1f}% sur une position) — surveiller la Règle 02.")

    # ── Sauvegarde ────────────────────────────────────────────────────────
    output = {
        "updated_at":            today,
        "week":                  semaine(),
        "capital_initial":       CAPITAL_INITIAL,
        "capital_actuel":        capital_actuel,
        "performance":           performance,
        "benchmark_cac40":       bench_cac,
        "benchmark_msci":        bench_msci,
        "vs_benchmark":          vs_benchmark,
        "statut_survie":         statut,
        "trimestres_negatifs":   trimestres_negatifs,
        "mode_panique":          mode_panique,
        "perf_cac_semaine":      round(perf_cac_semaine * 100, 2),
        "positions":             sorted(positions, key=lambda x: -x.get("performance", 0)),
        "liquidites":            round(liquidites, 2),
        "pct_liquidites":        round(liquidites / capital_actuel * 100, 1) if capital_actuel > 0 else 0,
        "ordres":                tous_ordres,
        "biais_detectes":        biais_detectes,
        "nb_positions":          len(positions),
        "nb_positives":          len([p for p in positions if p["performance"] > 0]),
        "nb_negatives":          len([p for p in positions if p["performance"] < 0]),
    }

    with open("portfolio.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ portfolio.json généré")
    print(f"   Capital : {capital_actuel:.0f}€ ({performance:+.1f}%) vs CAC40 {bench_cac:+.1f}%")
    print(f"   Positions : {len(positions)} · Liquidités : {liquidites:.0f}€")
    print(f"   Ordres cette semaine : {len(nouveaux_ordres)}")
    print(f"   Statut survie : {statut}")

if __name__ == "__main__":
    main()
