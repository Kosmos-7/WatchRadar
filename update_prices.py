"""
update_prices.py — Refresh quotidien des prix portfolio (M-V après close US).

NE FAIT PAS :
  - Pas de scoring (screener pas relancé)
  - Pas de décisions Claude (zéro appel API Anthropic)
  - Pas d'achat/vente
  - Pas de modification de positions ouvertes ni de liquidités

FAIT UNIQUEMENT :
  - Récupère les prix actuels des positions ouvertes (yfinance)
  - Met à jour valeur_actuelle, performance, prix_actuel par position
  - Recalcule capital_actuel et performance globale
  - Met à jour benchmark MSCI World et alpha
  - Upsert l'entrée du jour dans performance_history
  - Recalcule max_drawdown
  - Persiste dans portfolio.json

But : le site reflète la performance la plus récente chaque jour ouvré, sans
toucher à la méthodologie hebdomadaire (décisions Claude, watchlist, scoring).

Usage : python update_prices.py
"""

import json
import yfinance as yf
from datetime import date, datetime

# Réutilise les fonctions du portfolio_agent pour cohérence stricte
from portfolio_agent import (
    get_eur_usd_rate, get_eur_gbp_rate, maj_position,
    calc_max_drawdown, TICKER_CAC40, TICKER_MSCI, CAPITAL_INITIAL_DEF,
)


def main():
    today = str(date.today())

    # ── Charge portfolio
    try:
        with open("portfolio.json", encoding="utf-8") as f:
            portfolio = json.load(f)
    except FileNotFoundError:
        print("❌ portfolio.json introuvable — abandon")
        return
    except json.JSONDecodeError as e:
        print(f"❌ portfolio.json invalide : {e} — abandon")
        return

    capital_initial = portfolio.get("capital_initial", CAPITAL_INITIAL_DEF)
    positions       = portfolio.get("positions", [])
    liquidites      = portfolio.get("liquidites", capital_initial)

    if not positions:
        print("ℹ️  Aucune position ouverte — refresh inutile, sortie")
        return

    print(f"💱 Refresh quotidien des prix — {today}")
    print(f"   {len(positions)} position(s) ouverte(s)")

    # ── Taux de change
    eur_usd = get_eur_usd_rate()
    eur_gbp = get_eur_gbp_rate()
    print(f"   EUR/USD : {eur_usd} · EUR/GBP : {eur_gbp}")

    # ── Refresh des prix par position (réutilise maj_position : EUR cohérent)
    success = 0
    for pos in positions:
        if maj_position(pos, eur_usd, eur_gbp):
            success += 1
        else:
            print(f"   ⚠️  {pos['ticker']} : prix indisponible (gardé valeur précédente)")

    print(f"   ✓ {success}/{len(positions)} prix mis à jour")

    # ── Recalcule capital et performance globale
    val_positions   = sum(p.get("valeur_actuelle", 0) for p in positions)
    capital_actuel  = round(val_positions + liquidites, 2)
    performance     = round((capital_actuel - capital_initial) / capital_initial * 100, 2)

    # ── Met à jour les poids
    for pos in positions:
        pos["poids"] = round(pos["valeur_actuelle"] / capital_actuel * 100, 1) if capital_actuel > 0 else 0

    # ── Benchmarks YTD (rerécupère pour fraîcheur)
    annee = date.today().year
    debut = f"{annee}-01-01"
    bench_cac, bench_msci = portfolio.get("benchmark_cac40", 0), portfolio.get("benchmark_msci", 0)
    for label, ticker in [("cac40", TICKER_CAC40), ("msci", TICKER_MSCI)]:
        try:
            hist = yf.Ticker(ticker).history(start=debut)["Close"]
            if len(hist) >= 2:
                ytd = round((hist.iloc[-1] - hist.iloc[0]) / hist.iloc[0] * 100, 2)
                if label == "cac40":
                    bench_cac = ytd
                else:
                    bench_msci = ytd
        except Exception as e:
            print(f"   ⚠️  Benchmark {label} : {e} — valeur précédente conservée")

    vs_benchmark = round(performance - bench_msci, 2)

    # ── Trie les positions par performance EUR (cohérent avec portfolio_agent)
    positions_sorted = sorted(positions, key=lambda x: -x.get("performance", 0))

    # ── Upsert performance_history pour aujourd'hui
    history = portfolio.get("performance_history", [])
    today_entry = {
        "date":            today,
        "perf":            performance,
        "capital":         capital_actuel,
        "benchmark_cac40": bench_cac,
        "benchmark_msci":  bench_msci,
    }
    idx_today = next((i for i, h in enumerate(history) if h.get("date") == today), None)
    if idx_today is not None:
        # Préserve la note (injection de capital, etc.) si elle existait
        if "note" in history[idx_today]:
            today_entry["note"] = history[idx_today]["note"]
        history[idx_today] = today_entry
    else:
        history.append(today_entry)
    history = history[-52:]  # cap à 52 entrées (1 an)

    max_dd = calc_max_drawdown(history)

    # ── Met à jour le portfolio (sans toucher aux champs hebdo)
    portfolio["updated_at"]      = today
    portfolio["capital_actuel"]  = capital_actuel
    portfolio["performance"]     = performance
    portfolio["benchmark_cac40"] = bench_cac
    portfolio["benchmark_msci"]  = bench_msci
    portfolio["vs_benchmark"]    = vs_benchmark
    portfolio["positions"]       = positions_sorted
    portfolio["pct_liquidites"]  = round(liquidites / capital_actuel * 100, 1) if capital_actuel > 0 else 0
    portfolio["nb_positives"]    = len([p for p in positions if p.get("performance", 0) > 0])
    portfolio["nb_negatives"]    = len([p for p in positions if p.get("performance", 0) < 0])
    portfolio["nb_neutres"]      = len([p for p in positions if p.get("performance", 0) == 0.0])
    portfolio["performance_history"] = history
    portfolio["max_drawdown"]    = max_dd
    # Note : on ne touche PAS à : week, ordres, biais_detectes, regles_actives,
    # analyse_claude, macro_news, nb_positions (= len(positions), inchangé)

    # ── Persiste
    with open("portfolio.json", "w", encoding="utf-8") as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)

    print(f"\n✓ portfolio.json refreshé")
    print(f"  Capital   : {capital_actuel:.0f}€ ({performance:+.2f}% YTD)")
    print(f"  vs MSCI   : {vs_benchmark:+.2f}pp (MSCI {bench_msci:+.2f}%)")
    print(f"  Max DD    : {max_dd:+.2f}%")


if __name__ == "__main__":
    main()
