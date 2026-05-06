"""
backtest.py — Backtest momentum-only du screener Signal.

Rejoue les 40 points de Momentum (Golden Cross + RSI + Volume + Régression)
sur l'univers Signal US, avec les mêmes règles de portefeuille qu'en prod
(max 20% par titre, 15 positions max, hold 90j, stop-loss R07/R08).

Périmètre : US uniquement (univers + benchmark SPY) pour éviter les
complications de change. Aucun look-ahead bias : à chaque date, seules
les données antérieures sont utilisées pour scorer.

Limitation honnête : 60 % du score Signal (Fondamentaux + Analystes) NON
testé — Yahoo n'expose pas les fondamentaux historiques point-in-time.
Ce backtest mesure uniquement la composante technique.

Usage : python backtest.py
Output : backtest_results.json + console
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import time
from datetime import date, datetime, timedelta
from ta.momentum import RSIIndicator

# Réutilisation du screener pour garantir la cohérence avec la prod
from screener import detect_cross, cross_score, calcul_regression

# ── CONFIG ───────────────────────────────────────────────────────────────────
YEAR_START          = 2019    # début du backtest
YEAR_END            = 2025    # fin (exclusif)
INITIAL_CAPITAL     = 20000.0  # USD pour cohérence avec benchmark US
MAX_POSITIONS       = 15
POIDS_MAX           = 0.20
TOP_N_BUY           = 25      # top N scores éligibles à l'achat
HOLD_DAYS_MIN       = 90
STOP_LOSS_PCT       = -15.0
STOP_LOSS_CATA_PCT  = -25.0
BENCHMARK_TICKER    = "SPY"   # S&P 500 ETF — proxy MSCI USA, USD natif

# Univers US uniquement (filtré depuis screener.UNIVERS — pas de suffixes)
UNIVERS_US = [
    "AAPL","NVDA","MSFT","GOOGL","AMZN","META","AVGO","TSLA","LLY",
    "V","MA","JPM","UNH","XOM","PG","HD","MRK","ABBV","COST",
    "CRM","NFLX","AMD","ORCL","ACN","TMO","ABT","ISRG","GS",
    "BLK","QCOM","TXN","AMAT","NOW","PANW","INTU","AXP","SPGI",
    "HON","ETN","SYK","VRTX","ADI","REGN","MMC","CI","PLD",
    "ADBE","MCD","NEE","PFE","WMT","AMGN",
    "TSM","SE","SONY",
]

# ── FETCH ────────────────────────────────────────────────────────────────────
def fetch_all_history(tickers, start, end):
    """Télécharge tout l'historique en une fois — accès séquentiel par ticker.
    Retourne dict {ticker: DataFrame}."""
    data = {}
    print(f"📥 Téléchargement de {len(tickers)} tickers ({start} → {end})...")
    for i, t in enumerate(tickers):
        try:
            df = yf.Ticker(t).history(start=start, end=end, auto_adjust=True)
            if len(df) > 200:
                data[t] = df
                print(f"  [{i+1}/{len(tickers)}] {t} — {len(df)} jours OK")
            else:
                print(f"  [{i+1}/{len(tickers)}] {t} — IGNORÉ (historique trop court)")
        except Exception as e:
            print(f"  [{i+1}/{len(tickers)}] {t} — ERREUR : {e}")
    return data

# ── SCORING MOMENTUM POINT-IN-TIME ───────────────────────────────────────────
def score_momentum_at(df, target_date):
    """Calcule le score momentum (0-40) pour un ticker à une date précise.
    Utilise UNIQUEMENT les données ≤ target_date (anti look-ahead)."""
    hist = df[df.index <= target_date]
    if len(hist) < 250:  # min 1 an d'historique
        return None

    close = hist["Close"]
    volume = hist["Volume"]

    # Indicateurs court terme : 2 ans glissants
    close_2y = close.iloc[-504:] if len(close) > 504 else close
    volume_2y = volume.iloc[-504:] if len(volume) > 504 else volume

    try:
        rsi = float(RSIIndicator(close=close_2y, window=14).rsi().iloc[-1])
        if not np.isfinite(rsi):
            return None
    except Exception:
        return None

    cross_info = detect_cross(close_2y, volume_2y)
    cross_pts = cross_score(cross_info, rsi)

    # RSI gradué
    if 40 <= rsi <= 60:
        rsi_pts = 10
    elif 35 <= rsi <= 65:
        rsi_pts = 5
    else:
        rsi_pts = 0

    # Volume récent vs moyen
    vol_recent = float(volume_2y.tail(20).mean())
    vol_annual = float(volume_2y.mean())
    vol_pts = 5 if vol_recent > vol_annual else 0

    # Régression long terme (la fonction screener applique déjà holdout 20j)
    z, _ = calcul_regression(close)
    reg_pts = 5 if -0.5 <= z <= 1.5 else 0

    momentum = cross_pts + rsi_pts + vol_pts + reg_pts

    # Pénalité Death Cross récent (non compensable)
    if cross_info["regime"] == "death":
        d = cross_info["days_since_cross"]
        if d <= 30:
            momentum -= 5
        elif d <= 60:
            momentum -= 3

    return max(0, momentum), float(close.iloc[-1])

# ── PORTFOLIO ENGINE ─────────────────────────────────────────────────────────
def get_price_at(df, target_date):
    """Prix de clôture le jour target_date (ou jour ouvré précédent le plus proche)."""
    hist = df[df.index <= target_date]
    if hist.empty:
        return None
    return float(hist["Close"].iloc[-1])

def simulate_backtest(data):
    """Simule la stratégie momentum-only sur l'univers + comparaison benchmark."""
    bench_df = data.get(BENCHMARK_TICKER)
    if bench_df is None:
        print(f"❌ Benchmark {BENCHMARK_TICKER} indisponible — abandon")
        return None

    universe_tickers = [t for t in UNIVERS_US if t in data]
    print(f"\n🎯 Univers exploitable : {len(universe_tickers)}/{len(UNIVERS_US)} tickers")

    # Dates de rebalancement : tous les lundis dans la fenêtre
    bench_dates = bench_df.index
    rebal_dates = [
        d for d in bench_dates
        if YEAR_START <= d.year < YEAR_END and d.weekday() == 0
    ]
    print(f"📅 {len(rebal_dates)} rebalancements hebdomadaires ({rebal_dates[0].date()} → {rebal_dates[-1].date()})")

    # État du portefeuille
    cash = INITIAL_CAPITAL
    positions = {}  # ticker -> dict(qty, prix_achat, date_achat)
    history = []    # (date, total_value, bench_value, n_pos, cash)
    trades = []     # historique des ordres

    # Valeur initiale du benchmark pour normalisation
    bench_initial = get_price_at(bench_df, rebal_dates[0])
    bench_units = INITIAL_CAPITAL / bench_initial  # achat virtuel buy & hold

    for i, rebal_date in enumerate(rebal_dates):
        # ── Mise à jour des prix actuels
        for ticker, pos in list(positions.items()):
            prix = get_price_at(data[ticker], rebal_date)
            if prix is not None:
                pos["prix_actuel"] = prix
                pos["valeur"] = prix * pos["qty"]
                pos["perf"] = (prix - pos["prix_achat"]) / pos["prix_achat"] * 100

        capital = cash + sum(p.get("valeur", 0) for p in positions.values())

        # ── R08 — Stop-loss catastrophe (sans condition de durée)
        for ticker in list(positions.keys()):
            pos = positions[ticker]
            if pos.get("perf", 0) <= STOP_LOSS_CATA_PCT:
                cash += pos.get("valeur", 0)
                trades.append({
                    "date": str(rebal_date.date()), "type": "VENTE",
                    "ticker": ticker, "perf": round(pos["perf"], 2),
                    "raison": "R08 catastrophe", "jours": (rebal_date - pos["date_achat"]).days
                })
                del positions[ticker]

        # ── R07 — Stop-loss standard (≥ 90j)
        for ticker in list(positions.keys()):
            pos = positions[ticker]
            jours = (rebal_date - pos["date_achat"]).days
            if pos.get("perf", 0) <= STOP_LOSS_PCT and jours >= HOLD_DAYS_MIN:
                cash += pos.get("valeur", 0)
                trades.append({
                    "date": str(rebal_date.date()), "type": "VENTE",
                    "ticker": ticker, "perf": round(pos["perf"], 2),
                    "raison": "R07 stop-loss", "jours": jours
                })
                del positions[ticker]

        # ── Score tous les tickers de l'univers à cette date
        scores = []
        for ticker in universe_tickers:
            r = score_momentum_at(data[ticker], rebal_date)
            if r is not None:
                score, prix = r
                if prix > 0:
                    scores.append((ticker, score, prix))
        scores.sort(key=lambda x: -x[1])
        top_buy = scores[:TOP_N_BUY]

        # ── Vente : titres qui ne sont plus dans le top et détenus ≥ 90j
        top_tickers = {t for t, _, _ in top_buy}
        for ticker in list(positions.keys()):
            pos = positions[ticker]
            jours = (rebal_date - pos["date_achat"]).days
            # Vente si sorti du top + détenu ≥ 90j (Règle 01 simulée)
            if ticker not in top_tickers and jours >= HOLD_DAYS_MIN:
                cash += pos.get("valeur", 0)
                trades.append({
                    "date": str(rebal_date.date()), "type": "VENTE",
                    "ticker": ticker, "perf": round(pos.get("perf", 0), 2),
                    "raison": "rotation", "jours": jours
                })
                del positions[ticker]

        # ── Achat : top scores non détenus, jusqu'à MAX_POSITIONS
        capital = cash + sum(p.get("valeur", 0) for p in positions.values())
        slots = MAX_POSITIONS - len(positions)
        if slots > 0 and cash > 100:
            candidates = [(t, s, p) for t, s, p in top_buy if t not in positions]
            achats = candidates[:slots]
            if achats:
                budget_par_titre = min(
                    cash / len(achats),
                    capital * POIDS_MAX,
                )
                for ticker, score, prix in achats:
                    if budget_par_titre < 100 or prix <= 0:
                        continue
                    qty = int(budget_par_titre / prix)
                    if qty < 1:
                        continue
                    cost = qty * prix
                    if cost > cash:
                        continue
                    cash -= cost
                    positions[ticker] = {
                        "qty": qty, "prix_achat": prix, "prix_actuel": prix,
                        "valeur": cost, "perf": 0.0,
                        "date_achat": rebal_date, "score_entree": score,
                    }
                    trades.append({
                        "date": str(rebal_date.date()), "type": "ACHAT",
                        "ticker": ticker, "score": score, "prix": round(prix, 2),
                        "qty": qty, "montant": round(cost, 2)
                    })

        # ── Snapshot
        total_value = cash + sum(p.get("valeur", 0) for p in positions.values())
        bench_value = bench_units * get_price_at(bench_df, rebal_date)
        history.append({
            "date": str(rebal_date.date()),
            "portfolio": round(total_value, 2),
            "benchmark": round(bench_value, 2),
            "n_positions": len(positions),
            "cash": round(cash, 2),
        })

        if i % 26 == 0 or i == len(rebal_dates) - 1:
            perf_p = (total_value / INITIAL_CAPITAL - 1) * 100
            perf_b = (bench_value / INITIAL_CAPITAL - 1) * 100
            print(f"  {rebal_date.date()} | Portfolio ${total_value:>9,.0f} ({perf_p:+5.1f}%) "
                  f"| {BENCHMARK_TICKER} ${bench_value:>9,.0f} ({perf_b:+5.1f}%) "
                  f"| α={perf_p-perf_b:+5.1f}pp | {len(positions)} pos")

    return {
        "history": history,
        "trades": trades,
        "final_positions": [
            {"ticker": t, **{k: (str(v) if isinstance(v, datetime) else v) for k, v in p.items()}}
            for t, p in positions.items()
        ],
    }

# ── MÉTRIQUES ────────────────────────────────────────────────────────────────
def compute_metrics(history, trades):
    """Calcule les métriques de performance standard."""
    if not history:
        return {}
    p_values = np.array([h["portfolio"] for h in history])
    b_values = np.array([h["benchmark"] for h in history])

    # Returns weekly
    p_returns = np.diff(p_values) / p_values[:-1]
    b_returns = np.diff(b_values) / b_values[:-1]

    # Total return
    p_total = (p_values[-1] / p_values[0] - 1) * 100
    b_total = (b_values[-1] / b_values[0] - 1) * 100

    # Annualized (52 weeks)
    n_weeks = len(history)
    n_years = n_weeks / 52
    p_cagr = ((p_values[-1] / p_values[0]) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0
    b_cagr = ((b_values[-1] / b_values[0]) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0

    # Volatility (annualized)
    p_vol = float(np.std(p_returns, ddof=1) * np.sqrt(52) * 100) if len(p_returns) > 1 else 0
    b_vol = float(np.std(b_returns, ddof=1) * np.sqrt(52) * 100) if len(b_returns) > 1 else 0

    # Sharpe (rf=0 simplification)
    p_sharpe = (p_cagr / p_vol) if p_vol > 0 else 0
    b_sharpe = (b_cagr / b_vol) if b_vol > 0 else 0

    # Max drawdown
    def max_dd(values):
        peaks = np.maximum.accumulate(values)
        dd = (values - peaks) / peaks * 100
        return float(dd.min())
    p_mdd = max_dd(p_values)
    b_mdd = max_dd(b_values)

    # Trades stats
    ventes = [t for t in trades if t["type"] == "VENTE" and "perf" in t]
    n_trades = len(ventes)
    if n_trades > 0:
        wins = [t for t in ventes if t["perf"] > 0]
        win_rate = len(wins) / n_trades * 100
        avg_perf = float(np.mean([t["perf"] for t in ventes]))
        avg_winner = float(np.mean([t["perf"] for t in wins])) if wins else 0
        losers = [t for t in ventes if t["perf"] <= 0]
        avg_loser = float(np.mean([t["perf"] for t in losers])) if losers else 0
    else:
        win_rate = avg_perf = avg_winner = avg_loser = 0

    return {
        "n_weeks":          n_weeks,
        "n_years":          round(n_years, 2),
        "portfolio_total":  round(p_total, 2),
        "benchmark_total":  round(b_total, 2),
        "alpha_total":      round(p_total - b_total, 2),
        "portfolio_cagr":   round(p_cagr, 2),
        "benchmark_cagr":   round(b_cagr, 2),
        "alpha_cagr":       round(p_cagr - b_cagr, 2),
        "portfolio_vol":    round(p_vol, 2),
        "benchmark_vol":    round(b_vol, 2),
        "portfolio_sharpe": round(p_sharpe, 2),
        "benchmark_sharpe": round(b_sharpe, 2),
        "portfolio_mdd":    round(p_mdd, 2),
        "benchmark_mdd":    round(b_mdd, 2),
        "n_trades":         n_trades,
        "win_rate":         round(win_rate, 1),
        "avg_perf":         round(avg_perf, 2),
        "avg_winner":       round(avg_winner, 2),
        "avg_loser":        round(avg_loser, 2),
    }

def print_report(metrics, history):
    print("\n" + "=" * 72)
    print(f"📊 BACKTEST RESULTS — Momentum-only ({YEAR_START} → {YEAR_END})")
    print("=" * 72)
    print(f"  Période               : {metrics['n_years']} ans ({metrics['n_weeks']} semaines)")
    print(f"  Capital initial       : ${INITIAL_CAPITAL:,.0f}")
    print()
    print(f"  Portfolio total       : {metrics['portfolio_total']:+8.2f}%   (CAGR {metrics['portfolio_cagr']:+5.2f}%)")
    print(f"  {BENCHMARK_TICKER} total              : {metrics['benchmark_total']:+8.2f}%   (CAGR {metrics['benchmark_cagr']:+5.2f}%)")
    print(f"  ALPHA                 : {metrics['alpha_total']:+8.2f}pp  (CAGR {metrics['alpha_cagr']:+5.2f}pp)")
    print()
    print(f"  Volatilité Portfolio  : {metrics['portfolio_vol']:5.2f}%   (annualisée)")
    print(f"  Volatilité Benchmark  : {metrics['benchmark_vol']:5.2f}%")
    print(f"  Sharpe Portfolio      : {metrics['portfolio_sharpe']:5.2f}")
    print(f"  Sharpe Benchmark      : {metrics['benchmark_sharpe']:5.2f}")
    print()
    print(f"  Max Drawdown Portfolio: {metrics['portfolio_mdd']:+8.2f}%")
    print(f"  Max Drawdown Benchmark: {metrics['benchmark_mdd']:+8.2f}%")
    print()
    print(f"  Trades fermés         : {metrics['n_trades']}")
    print(f"  Win rate              : {metrics['win_rate']:5.1f}%")
    print(f"  Perf moy / trade      : {metrics['avg_perf']:+5.2f}%   (gagnants {metrics['avg_winner']:+.1f}% / perdants {metrics['avg_loser']:+.1f}%)")
    print("=" * 72)

    # Verdict
    alpha_cagr = metrics["alpha_cagr"]
    sharpe_diff = metrics["portfolio_sharpe"] - metrics["benchmark_sharpe"]
    print("\n🎯 VERDICT")
    if alpha_cagr > 1.0 and sharpe_diff > 0:
        print(f"  ✅ Le momentum produit de l'alpha : +{alpha_cagr:.2f}pp/an avec Sharpe supérieur (+{sharpe_diff:.2f}).")
        print(f"     Le scoring technique seul (40/100) bat {BENCHMARK_TICKER} sur la période.")
    elif abs(alpha_cagr) < 1.0:
        print(f"  ⚠️  Performance équivalente au benchmark (alpha {alpha_cagr:+.2f}pp/an).")
        print(f"     Le scoring n'apporte ni ne détruit de valeur — un ETF ferait pareil.")
    else:
        print(f"  ❌ Sous-performance : {alpha_cagr:+.2f}pp/an vs {BENCHMARK_TICKER}.")
        print(f"     Le scoring momentum seul détruit de la valeur sur la période. À réviser.")
    print()

# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    t0 = time.time()
    start_str = f"{YEAR_START - 2}-01-01"  # buffer 2 ans pour MM200 + régression
    end_str = f"{YEAR_END}-01-01"

    data = fetch_all_history(UNIVERS_US + [BENCHMARK_TICKER], start_str, end_str)
    if not data:
        print("❌ Aucune donnée récupérée")
        return

    print(f"\n⚙️  Simulation rebalancements hebdomadaires...")
    result = simulate_backtest(data)
    if not result:
        return

    metrics = compute_metrics(result["history"], result["trades"])
    print_report(metrics, result["history"])

    output = {
        "config": {
            "year_start": YEAR_START, "year_end": YEAR_END,
            "initial_capital": INITIAL_CAPITAL, "max_positions": MAX_POSITIONS,
            "poids_max": POIDS_MAX, "top_n_buy": TOP_N_BUY,
            "hold_days_min": HOLD_DAYS_MIN, "stop_loss_pct": STOP_LOSS_PCT,
            "stop_loss_cata_pct": STOP_LOSS_CATA_PCT,
            "benchmark": BENCHMARK_TICKER, "universe_size": len(UNIVERS_US),
        },
        "metrics": metrics,
        "history": result["history"],
        "trades": result["trades"],
        "final_positions": result["final_positions"],
        "generated_at": str(date.today()),
        "duration_seconds": round(time.time() - t0, 1),
    }
    with open("backtest_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"💾 Résultats détaillés → backtest_results.json")
    print(f"⏱️  Durée totale : {output['duration_seconds']}s")

if __name__ == "__main__":
    main()
