"""
screener.py — Agent de sélection WatchRadar
Tourne chaque lundi via GitHub Actions.
Génère watchlist.json avec les 25 actions les mieux scorées.

Dépendances : pip install yfinance pandas ta requests
"""

import yfinance as yf
import pandas as pd
import json
import os
from datetime import date
from ta.momentum import RSIIndicator

# ── UNIVERS ──────────────────────────────────────────────────────────────────
# CAC40 + DAX40 (sélection) + AEX25 (sélection) + S&P100 (sélection)
# ~187 valeurs couvrant marchés EU et US

UNIVERS = [
    # CAC 40
    "AIR.PA","AI.PA","ALO.PA","BN.PA","CAP.PA","CS.PA","DSY.PA",
    "ENGI.PA","EL.PA","ERF.PA","GLE.PA","HO.PA","KER.PA","LR.PA",
    "MC.PA","ML.PA","OR.PA","ORA.PA","PUB.PA","RMS.PA","SAF.PA",
    "SGO.PA","STLA.PA","STM.PA","SU.PA","TTE.PA","VIE.PA","WLN.PA",
    # DAX 40
    "ADS.DE","AIR.DE","ALV.DE","BAS.DE","BAYN.DE","BMW.DE","CBK.DE",
    "CON.DE","DB1.DE","DBK.DE","DHL.DE","DTE.DE","ENR.DE","EOAN.DE",
    "FRE.DE","HNR1.DE","IFX.DE","LIN.DE","MBG.DE","MRK.DE","MTX.DE",
    "MUV2.DE","P911.DE","PUMA.DE","RWE.DE","SAP.DE","SHL.DE","SIE.DE",
    "SRT3.DE","VOW3.DE","VNA.DE","ZAL.DE",
    # AEX 25
    "ADYEN.AS","AGN.AS","AKZA.AS","ASM.AS","ASML.AS","BESI.AS",
    "HEIA.AS","IMCD.AS","NN.AS","PHIA.AS","RAND.AS","REN.AS",
    "URW.AS","WKL.AS",
    # OMX (Nordics)
    "NOVO-B.CO","VWS.CO","NZYM-B.CO",
    # LSE
    "REL.L","LSEG.L","RIO.L","SHEL.L","AZN.L","ULVR.L",
    # S&P 100
    "NVDA","MSFT","GOOGL","AMZN","META","AVGO","TSLA","LLY",
    "V","MA","JPM","UNH","XOM","PG","HD","MRK","ABBV","COST",
    "CRM","NFLX","AMD","ORCL","ACN","TMO","ABT","ISRG","GS",
    "BLK","QCOM","TXN","AMAT","NOW","PANW","INTU","AXP","SPGI",
    "HON","ETN","SYK","VRTX","ADI","REGN","MMC","CI","PLD",
]

# ── CHANGELOG (pour détecter les entrées/sorties) ────────────────────────────
def load_previous(path="watchlist.json"):
    try:
        with open(path) as f:
            data = json.load(f)
        return {s["ticker"] for s in data.get("stocks", [])}
    except:
        return set()

# ── SCORING ──────────────────────────────────────────────────────────────────
def score_ticker(ticker: str) -> dict | None:
    try:
        data  = yf.Ticker(ticker)
        hist  = data.history(period="1y")
        if len(hist) < 50:
            return None

        close  = hist["Close"].squeeze()
        volume = hist["Volume"].squeeze()
        prix   = float(close.iloc[-1])
        mm50   = float(close.rolling(50).mean().iloc[-1])
        mm200  = float(close.rolling(200).mean().iloc[-1])
        rsi    = float(RSIIndicator(close=close, window=14).rsi().iloc[-1])
        vol_r  = float(volume.tail(90).mean())
        vol_o  = float(volume.head(90).mean())

        score = 0

        # ── Momentum technique (40 pts)
        if prix > mm200:              score += 10
        if prix > mm50:               score += 10
        if 50 <= rsi <= 70:           score += 10
        if vol_r > vol_o:             score += 10

        # ── Fondamentaux (40 pts)
        info = data.info
        rev_growth = info.get("revenueGrowth") or 0
        margins    = info.get("profitMargins") or 0
        peg        = info.get("pegRatio") or 0
        debt_eq    = info.get("debtToEquity") or 0

        if rev_growth > 0.10:         score += 15
        elif rev_growth > 0.05:       score += 8
        if margins > 0.10:            score += 10
        elif margins > 0:             score += 5
        if 0 < peg < 2:               score += 10
        elif 2 <= peg < 3:            score += 5
        if debt_eq < 100:             score += 5

        # ── Consensus analystes (20 pts)
        reco = info.get("recommendationMean") or 3.5
        if reco < 2.0:                score += 20
        elif reco < 2.5:              score += 12
        elif reco < 3.0:              score += 6

        # ── Bonus sectoriels (momentum sectoriel moyen)
        sector = info.get("sector", "")
        bonus_sectors = ["Technology","Healthcare","Industrials","Financial Services"]
        if sector in bonus_sectors:   score = min(score + 3, 100)

        stars = 5 if score >= 80 else 4 if score >= 65 else 3 if score >= 50 else 2

        # Détection badge EU
        exchange = info.get("exchange", "")
        eu_exchanges = ["PAR","EPA","AMS","FRA","XETRA","CPH","OMX","LSE","AEB"]
        badge = "EU" if any(ex in exchange.upper() for ex in eu_exchanges) else None

        # Secteur formaté (court)
        sector_map = {
            "Technology": "Technologie",
            "Healthcare": "Santé",
            "Industrials": "Industrie",
            "Financial Services": "Finance",
            "Consumer Cyclical": "Conso. cycl.",
            "Consumer Defensive": "Conso. staples",
            "Energy": "Énergie",
            "Basic Materials": "Matériaux",
            "Communication Services": "Médias & IA",
            "Real Estate": "Immobilier",
            "Utilities": "Services pub.",
        }
        sector_fr = sector_map.get(sector, sector[:14] if sector else "—")

        return {
            "ticker": ticker,
            "name":   info.get("shortName", ticker)[:22],
            "market": info.get("exchange", "—")[:10],
            "sector": sector_fr,
            "score":  round(score),
            "stars":  stars,
            "badge":  badge,
            "change": "stable",  # mis à jour après comparaison
        }

    except Exception as e:
        print(f"  ✗ {ticker}: {e}")
        return None

# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print(f"🔍 Analyse de {len(UNIVERS)} actions…")

    previous_tickers = load_previous()
    resultats = []

    for i, ticker in enumerate(UNIVERS):
        print(f"  [{i+1}/{len(UNIVERS)}] {ticker}…", end=" ")
        r = score_ticker(ticker)
        if r:
            resultats.append(r)
            print(f"score {r['score']}")
        else:
            print("ignoré")

    # Tri et top 25
    resultats.sort(key=lambda x: -x["score"])
    top25 = resultats[:25]

    current_tickers = {s["ticker"] for s in top25}

    # Marquer les changements
    for s in top25:
        if s["ticker"] not in previous_tickers:
            s["change"] = "new"

    # Construire le changelog
    entrees = [s for s in top25 if s["ticker"] not in previous_tickers]
    sorties_tickers = previous_tickers - current_tickers

    changelog = []
    for s in entrees[:5]:
        changelog.append({
            "action": "in",
            "ticker": s["ticker"],
            "name":   s["name"],
            "score":  s["score"],
            "reason": f"Score {s['score']}/100 — entrée dans le top 25 cette semaine"
        })
    for t in list(sorties_tickers)[:5]:
        changelog.append({
            "action": "out",
            "ticker": t,
            "name":   t,
            "score":  0,
            "reason": "Score insuffisant pour rester dans le top 25"
        })

    # Numérotation
    for i, s in enumerate(top25):
        s["rank"] = i + 1

    output = {
        "updated_at":    str(date.today()),
        "week":          f"Sem. {date.today().isocalendar()[1]} · {date.today().year}",
        "universe_size": len(resultats),
        "stocks":        top25,
        "changelog":     changelog,
    }

    with open("watchlist.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ watchlist.json généré — {len(top25)} actions · top score : {top25[0]['name']} ({top25[0]['score']})")

if __name__ == "__main__":
    main()
