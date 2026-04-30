"""
portfolio_agent.py — Agent de gestion du portefeuille fictif WatchRadar
Lit watchlist.json, prend des décisions d'achat/vente, génère portfolio.json.

Règles de survie :
- Aucune vente avant 90 jours (sauf signal fondamental majeur)
- Maximum 30% sur un seul titre
- Zéro ajustement si CAC40 chute > 5% sur la semaine
- Deux trimestres négatifs vs CAC40 = remise à zéro publique
"""

import yfinance as yf
import json
from datetime import date, datetime, timedelta

CAPITAL_INITIAL = 10000.0
POIDS_MAX       = 0.30
POIDS_CIBLE     = 0.04
JOURS_MIN_HOLD  = 90
SEUIL_PANIQUE   = -0.05
TICKER_CAC40    = "^FCHI"
TICKER_MSCI     = "URTH"

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def portfolio_vide():
    return {
        "updated_at": str(date.today()), "week": semaine(),
        "capital_initial": CAPITAL_INITIAL, "capital_actuel": CAPITAL_INITIAL,
        "performance": 0.0, "benchmark_cac40": 0.0, "benchmark_msci": 0.0,
        "vs_benchmark": 0.0, "statut_survie": "en_vie",
        "trimestres_negatifs": 0, "positions": [],
        "liquidites": CAPITAL_INITIAL, "ordres": [], "biais_detectes": [],
    }

def semaine():
    d = date.today()
    return f"Sem. {d.isocalendar()[1]} · {d.year}"

def get_prix(ticker):
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        return round(float(hist["Close"].iloc[-1]), 2) if not hist.empty else None
    except:
        return None

def get_perf_semaine(ticker):
    try:
        hist = yf.Ticker(ticker).history(period="10d")["Close"]
        return float((hist.iloc[-1] - hist.iloc[0]) / hist.iloc[0]) if len(hist) >= 2 else 0.0
    except:
        return 0.0

def get_perf_depuis_debut():
    """Performance CAC40 et MSCI depuis le 1er jan de l'année courante."""
    annee = date.today().year
    debut = f"{annee}-01-01"
    resultats = {}
    for label, ticker in [("cac40", TICKER_CAC40), ("msci", TICKER_MSCI)]:
        try:
            hist = yf.Ticker(ticker).history(start=debut)["Close"]
            if len(hist) >= 2:
                resultats[label] = round((float(hist.iloc[-1]) - float(hist.iloc[0])) / float(hist.iloc[0]) * 100, 2)
            else:
                resultats[label] = 0.0
        except:
            resultats[label] = 0.0
    return resultats

def expliquer_achat(stock, prix, quantite, montant):
    """Génère une explication détaillée d'une décision d'achat."""
    nom    = stock.get("name") or stock.get("nom", stock["ticker"])
    score  = stock.get("score", 0)
    sector = stock.get("sector", "")
    justif = stock.get("justification", "")
    bd     = stock.get("breakdown", {})

    raisons = []

    # Score global
    raisons.append(f"Score {score}/100")

    # Détail momentum
    momentum = bd.get("momentum", 0)
    if momentum >= 30:
        raisons.append(f"momentum technique fort ({momentum}/40)")
    elif momentum >= 20:
        raisons.append(f"momentum technique correct ({momentum}/40)")

    # Fondamentaux
    fondamentaux = bd.get("fondamentaux", 0)
    if fondamentaux >= 30:
        raisons.append(f"fondamentaux solides ({fondamentaux}/40)")

    # Croissance
    rev = bd.get("rev_growth_pct", 0)
    if rev > 10:
        raisons.append(f"croissance CA {rev:.0f}%/an")

    # Marge
    margin = bd.get("net_margin_pct", 0)
    if margin > 10:
        raisons.append(f"marge nette {margin:.0f}%")

    # Sources
    sources = bd.get("sources", ["Yahoo Finance"])
    src_str = " + ".join(sources)

    explication = f"{' · '.join(raisons[:4])}. Sources : {src_str}."
    if justif and len(justif) < 150:
        explication = justif

    return {
        "date":        str(date.today()),
        "type":        "ACHAT",
        "ticker":      stock["ticker"],
        "nom":         nom,
        "qte":         quantite,
        "prix":        prix,
        "montant":     montant,
        "raison":      explication,
        "score":       score,
        "breakdown":   bd,
    }

def expliquer_vente(pos, prix, montant, raison_type, jours):
    """Génère une explication détaillée d'une décision de vente."""
    perf = round((prix - pos["prix_achat"]) / pos["prix_achat"] * 100, 2)

    if raison_type == "sortie_watchlist":
        if perf > 0:
            raison = f"Sortie de watchlist après {jours}j détenus (+{perf:.1f}%). Score passé sous le seuil top 25 cette semaine. Règle 01 respectée (>{JOURS_MIN_HOLD}j)."
        else:
            raison = f"Sortie de watchlist après {jours}j détenus ({perf:.1f}%). Score dégradé. Règle 01 respectée (>{JOURS_MIN_HOLD}j). Erreur analysée en post-mortem."
    elif raison_type == "signal_fondamental":
        raison = f"Signal fondamental majeur détecté — exception à la Règle 01 ({jours}j détenus). Performance : {'+' if perf >= 0 else ''}{perf:.1f}%."
    else:
        raison = f"Vente après {jours}j. Performance : {'+' if perf >= 0 else ''}{perf:.1f}%."

    return {
        "date":    str(date.today()),
        "type":    "VENTE",
        "ticker":  pos["ticker"],
        "nom":     pos["nom"],
        "qte":     pos["quantite"],
        "prix":    prix,
        "montant": montant,
        "perf":    perf,
        "jours":   jours,
        "raison":  raison,
    }

def main():
    today     = str(date.today())
    watchlist = load_json("watchlist.json", {})
    portfolio = load_json("portfolio.json", portfolio_vide())

    stocks_watchlist  = watchlist.get("stocks", [])
    tickers_watchlist = {s["ticker"] for s in stocks_watchlist}
    stock_map         = {s["ticker"]: s for s in stocks_watchlist}

    positions  = portfolio.get("positions", [])
    liquidites = portfolio.get("liquidites", CAPITAL_INITIAL)
    ordres     = portfolio.get("ordres", [])

    nouveaux_ordres = []
    biais_detectes  = []

    # ── Règle 03 : panique de marché ─────────────────────────────────────
    perf_cac_semaine = get_perf_semaine(TICKER_CAC40)
    mode_panique = perf_cac_semaine < SEUIL_PANIQUE

    if mode_panique:
        biais_detectes.append(f"Mode panique activé (CAC40 : {perf_cac_semaine:.1%} cette semaine). Règle 03 : aucun ordre exécuté.")
        print(f"⚠️  Mode panique — CAC40 semaine : {perf_cac_semaine:.1%}")

    # ── Mise à jour prix des positions ────────────────────────────────────
    valeur_positions = 0.0
    positions_mises_a_jour = []

    for pos in positions:
        prix_actuel = get_prix(pos["ticker"]) or pos.get("prix_actuel", pos["prix_achat"])
        perf  = round((prix_actuel - pos["prix_achat"]) / pos["prix_achat"] * 100, 2)
        valeur = round(prix_actuel * pos["quantite"], 2)
        valeur_positions += valeur
        pos["prix_actuel"]    = prix_actuel
        pos["performance"]    = perf
        pos["valeur_actuelle"] = valeur
        positions_mises_a_jour.append(pos)
        print(f"  📊 {pos['ticker']} : {prix_actuel:.2f}€ ({perf:+.1f}%)")

    positions = positions_mises_a_jour
    capital_total = round(valeur_positions + liquidites, 2)

    # ── Ventes ────────────────────────────────────────────────────────────
    if not mode_panique:
        positions_a_garder = []
        for pos in positions:
            date_achat    = datetime.strptime(pos["date_achat"], "%Y-%m-%d")
            jours_detenus = (datetime.today() - date_achat).days
            dans_watchlist = pos["ticker"] in tickers_watchlist

            if not dans_watchlist and jours_detenus >= JOURS_MIN_HOLD:
                prix_vente = pos["prix_actuel"]
                montant    = round(prix_vente * pos["quantite"], 2)
                liquidites = round(liquidites + montant, 2)
                valeur_positions -= pos["valeur_actuelle"]

                ordre = expliquer_vente(pos, prix_vente, montant, "sortie_watchlist", jours_detenus)
                nouveaux_ordres.append(ordre)
                print(f"  🔴 VENTE {pos['ticker']} — {jours_detenus}j, hors watchlist ({ordre['perf']:+.1f}%)")
            else:
                if not dans_watchlist:
                    print(f"  ⏳ {pos['ticker']} hors watchlist mais {jours_detenus}j < {JOURS_MIN_HOLD}j — conservé (Règle 01)")
                positions_a_garder.append(pos)

        positions = positions_a_garder

    # ── Achats ────────────────────────────────────────────────────────────
    if not mode_panique:
        tickers_en_portefeuille = {p["ticker"] for p in positions}
        capital_total = round(sum(p["valeur_actuelle"] for p in positions) + liquidites, 2)

        for stock in stocks_watchlist:
            if stock["ticker"] in tickers_en_portefeuille:
                continue

            budget  = min(capital_total * POIDS_CIBLE, capital_total * POIDS_MAX)
            budget  = min(budget, liquidites)

            if budget < 50:
                continue

            prix = get_prix(stock["ticker"])
            if not prix or prix <= 0:
                continue

            quantite = max(1, int(budget / prix))
            montant  = round(prix * quantite, 2)
            liquidites = round(liquidites - montant, 2)

            nom = stock.get("name") or stock.get("nom", stock["ticker"])

            nouvelle_pos = {
                "ticker":          stock["ticker"],
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
                "score_entree":    stock.get("score", 0),
            }
            positions.append(nouvelle_pos)

            ordre = expliquer_achat(stock, prix, quantite, montant)
            nouveaux_ordres.append(ordre)
            print(f"  🟢 ACHAT {stock['ticker']} — {quantite} titres à {prix:.2f}€ = {montant:.0f}€")

    # ── Recalcul final ────────────────────────────────────────────────────
    valeur_positions = sum(p["valeur_actuelle"] for p in positions)
    capital_actuel   = round(valeur_positions + liquidites, 2)
    performance      = round((capital_actuel - CAPITAL_INITIAL) / CAPITAL_INITIAL * 100, 2)

    for pos in positions:
        pos["poids"] = round(pos["valeur_actuelle"] / capital_actuel * 100, 1) if capital_actuel > 0 else 0

    # ── Benchmarks ────────────────────────────────────────────────────────
    benchmarks = get_perf_depuis_debut()
    bench_cac  = portfolio.get("benchmark_cac40", benchmarks["cac40"]) if not benchmarks["cac40"] else benchmarks["cac40"]
    bench_msci = portfolio.get("benchmark_msci", benchmarks["msci"]) if not benchmarks["msci"] else benchmarks["msci"]
    vs_bench   = round(performance - bench_cac, 2)

    # ── Statut survie ─────────────────────────────────────────────────────
    trimestres_neg = portfolio.get("trimestres_negatifs", 0)
    if vs_bench < 0:
        trimestres_neg = min(trimestres_neg + 1, 2)
    else:
        trimestres_neg = max(trimestres_neg - 1, 0)

    statut = "reinitialisation" if trimestres_neg >= 2 else "en_vie"
    if statut == "reinitialisation":
        biais_detectes.append("⚠️ Deux trimestres consécutifs sous le CAC40. Méthodologie en cours de révision.")

    # ── Biais auto-détectés ───────────────────────────────────────────────
    perdantes = [p for p in positions if p["performance"] < -10]
    if len(perdantes) > 3:
        tickers_perdants = ", ".join(p["ticker"] for p in perdantes[:3])
        biais_detectes.append(f"{len(perdantes)} positions en perte > 10% ({tickers_perdants}…) — le scoring sous-estime peut-être un risque macro non modélisé.")

    poids_max_pos = max((p["poids"] for p in positions), default=0)
    if poids_max_pos > 25:
        biais_detectes.append(f"Concentration excessive : {poids_max_pos:.1f}% sur une position. Règle 02 sous tension.")

    # ── Historique ────────────────────────────────────────────────────────
    tous_ordres = nouveaux_ordres + ordres
    tous_ordres = tous_ordres[:50]

    nb_pos   = len(positions)
    nb_pos_p = len([p for p in positions if p["performance"] > 0])
    nb_pos_n = len([p for p in positions if p["performance"] < 0])

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
        "trimestres_negatifs": trimestres_neg,
        "mode_panique":        mode_panique,
        "perf_cac_semaine":    round(perf_cac_semaine * 100, 2),
        "positions":           sorted(positions, key=lambda x: -x.get("performance", 0)),
        "liquidites":          round(liquidites, 2),
        "pct_liquidites":      round(liquidites / capital_actuel * 100, 1) if capital_actuel > 0 else 0,
        "ordres":              tous_ordres,
        "biais_detectes":      biais_detectes,
        "nb_positions":        nb_pos,
        "nb_positives":        nb_pos_p,
        "nb_negatives":        nb_pos_n,
    }

    with open("portfolio.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ portfolio.json")
    print(f"   Capital : {capital_actuel:.0f}€ ({performance:+.1f}%) vs CAC40 {bench_cac:+.1f}%")
    print(f"   Ordres cette semaine : {len(nouveaux_ordres)} ({sum(1 for o in nouveaux_ordres if o['type']=='ACHAT')} achats, {sum(1 for o in nouveaux_ordres if o['type']=='VENTE')} ventes)")
    print(f"   Statut : {statut}")

if __name__ == "__main__":
    main()
