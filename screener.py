"""
screener.py — Agent de sélection WatchRadar
Génère watchlist.json avec les 25 actions les mieux scorées.

Sources de données :
- Yahoo Finance (yfinance) : prix, indicateurs techniques, fondamentaux US
- Finnhub : validation croisée des fondamentaux (gratuit, 60 req/min)

Dépendances : pip install yfinance pandas ta requests finnhub-python
"""

import yfinance as yf
import pandas as pd
import json
import os
import time
import requests
from datetime import date
from ta.momentum import RSIIndicator

# ── FINNHUB (validation croisée) ─────────────────────────────────────────────
# Clé gratuite : https://finnhub.io/register (60 req/min)
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

def finnhub_fundamentals(ticker):
    """Récupère les métriques fondamentales via Finnhub pour validation croisée."""
    if not FINNHUB_KEY:
        return {}
    # Finnhub utilise des tickers sans suffixe de marché
    clean = ticker.replace(".PA", "").replace(".DE", "").replace(".AS", "").replace(".L", "").replace(".CO", "")
    try:
        url = f"https://finnhub.io/api/v1/stock/metric?symbol={clean}&metric=all&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json().get("metric", {})
            return {
                "pe_ttm":        data.get("peBasicExclExtraTTM"),
                "rev_growth_3y": data.get("revenueGrowth3Y"),
                "net_margin":    data.get("netProfitMarginTTM"),
                "roe":           data.get("roeTTM"),
                "debt_equity":   data.get("totalDebt/totalEquityAnnual"),
            }
    except:
        pass
    return {}

def valider_fondamentaux(yf_data, fh_data):
    """
    Compare les données YF et Finnhub.
    Retourne un facteur de confiance entre 0.7 et 1.0.
    Les valeurs aberrantes sont pénalisées.
    """
    if not fh_data:
        return 1.0  # Pas de données Finnhub → on fait confiance à YF

    confiance = 1.0
    alertes = []

    # Vérification marge nette
    yf_margin  = yf_data.get("profitMargins") or 0
    fh_margin  = (fh_data.get("net_margin") or 0) / 100 if fh_data.get("net_margin") else 0

    if fh_margin and abs(yf_margin - fh_margin) > 0.15:
        confiance -= 0.1
        alertes.append(f"Marge nette discordante YF:{yf_margin:.1%} vs FH:{fh_margin:.1%}")

    # Vérification dette/fonds propres
    yf_de = yf_data.get("debtToEquity") or 0
    fh_de = fh_data.get("debt_equity") or 0
    if fh_de and yf_de and abs(yf_de - fh_de * 100) > 100:
        confiance -= 0.1

    # Valeurs aberrantes YF seul (croissance > 300% suspect)
    rev_growth = yf_data.get("revenueGrowth") or 0
    if rev_growth > 3.0:
        confiance -= 0.15
        alertes.append(f"Croissance CA suspectement élevée : {rev_growth:.0%}")

    return max(0.7, confiance), alertes

# ── UNIVERS ──────────────────────────────────────────────────────────────────
UNIVERS = [
    # CAC 40
    "AIR.PA","AI.PA","ALO.PA","BN.PA","CAP.PA","CS.PA","DSY.PA",
    "ENGI.PA","EL.PA","ERF.PA","GLE.PA","HO.PA","KER.PA","LR.PA",
    "MC.PA","OR.PA","ORA.PA","PUB.PA","RMS.PA","SAF.PA",
    "SGO.PA","SU.PA","TTE.PA","VIE.PA","WLN.PA",
    # DAX 40
    "ADS.DE","ALV.DE","BAS.DE","BAYN.DE","BMW.DE","DB1.DE",
    "DBK.DE","DHL.DE","DTE.DE","EOAN.DE","FRE.DE","IFX.DE",
    "LIN.DE","MBG.DE","MRK.DE","MUV2.DE","RWE.DE","SAP.DE","SIE.DE","VOW3.DE",
    # AEX 25
    "ADYEN.AS","ASM.AS","ASML.AS","HEIA.AS","IMCD.AS","PHIA.AS","RAND.AS",
    # OMX (Nordics)
    "NOVO-B.CO","VWS.CO",
    # LSE
    "REL.L","LSEG.L","AZN.L","ULVR.L",
    # S&P 100
    "NVDA","MSFT","GOOGL","AMZN","META","AVGO","TSLA","LLY",
    "V","MA","JPM","UNH","XOM","PG","HD","MRK","ABBV","COST",
    "CRM","NFLX","AMD","ORCL","ACN","TMO","ABT","ISRG","GS",
    "BLK","QCOM","TXN","AMAT","NOW","PANW","INTU","AXP","SPGI",
    "HON","ETN","SYK","VRTX","ADI","REGN","MMC","CI","PLD",
]

# ── JUSTIFICATION ─────────────────────────────────────────────────────────────
def generer_justification(nom, score, details, alertes):
    """Génère une explication lisible du score en 1-2 phrases."""
    points = []

    if details.get("au_dessus_mm200") and details.get("au_dessus_mm50"):
        points.append("momentum haussier confirmé (MM50 et MM200)")
    elif details.get("au_dessus_mm200"):
        points.append("tendance long terme positive (MM200)")

    if details.get("rsi_ok"):
        points.append("RSI en zone favorable")

    rev = details.get("rev_growth", 0)
    if rev > 0.15:
        points.append(f"croissance CA solide ({rev:.0%}/an)")
    elif rev > 0.05:
        points.append(f"croissance CA modérée ({rev:.0%}/an)")

    margin = details.get("net_margin", 0)
    if margin > 0.15:
        points.append(f"marges excellentes ({margin:.0%})")
    elif margin > 0:
        points.append("marges positives")

    reco = details.get("reco", 3)
    if reco < 2.0:
        points.append("consensus analystes très favorable")
    elif reco < 2.5:
        points.append("consensus analystes positif")

    if not points:
        return f"Score de {score}/100 — données partielles disponibles."

    justif = f"Score {score}/100 — " + ", ".join(points[:3]) + "."

    if alertes:
        justif += f" ⚠ {alertes[0]}"

    return justif

# ── SCORING ──────────────────────────────────────────────────────────────────
def score_ticker(ticker):
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

        info = data.info

        # ── Fondamentaux Yahoo Finance
        rev_growth = info.get("revenueGrowth") or 0
        margins    = info.get("profitMargins")  or 0
        peg        = info.get("pegRatio")        or 0
        debt_eq    = info.get("debtToEquity")    or 0
        reco       = info.get("recommendationMean") or 3.5

        # ── Validation croisée Finnhub
        fh_data = finnhub_fundamentals(ticker)
        confiance, alertes = valider_fondamentaux(info, fh_data)

        # ── Calcul du score
        score = 0
        details = {}

        # Momentum technique (40 pts)
        au_dessus_mm200 = prix > mm200
        au_dessus_mm50  = prix > mm50
        rsi_ok          = 50 <= rsi <= 70
        vol_ok          = vol_r > vol_o

        if au_dessus_mm200: score += 10
        if au_dessus_mm50:  score += 10
        if rsi_ok:          score += 10
        if vol_ok:          score += 10

        details["au_dessus_mm200"] = au_dessus_mm200
        details["au_dessus_mm50"]  = au_dessus_mm50
        details["rsi_ok"]          = rsi_ok
        details["rsi"]             = round(rsi, 1)

        # Fondamentaux (40 pts)
        if rev_growth > 0.10:   score += 15
        elif rev_growth > 0.05: score += 8
        if margins > 0.10:      score += 10
        elif margins > 0:       score += 5
        if 0 < peg < 2:         score += 10
        elif 2 <= peg < 3:      score += 5
        if 0 < debt_eq < 100:   score += 5

        details["rev_growth"] = rev_growth
        details["net_margin"] = margins
        details["peg"]        = peg
        details["reco"]       = reco

        # Consensus analystes (20 pts)
        if reco < 2.0:   score += 20
        elif reco < 2.5: score += 12
        elif reco < 3.0: score += 6

        # Bonus sectoriel (3 pts)
        sector = info.get("sector", "")
        bonus_sectors = ["Technology", "Healthcare", "Industrials", "Financial Services"]
        if sector in bonus_sectors:
            score = min(score + 3, 100)

        # Application du facteur de confiance
        score = round(score * confiance)

        stars = 5 if score >= 80 else 4 if score >= 65 else 3 if score >= 50 else 2

        # Badges
        exchange = info.get("exchange", "")
        eu_exc   = ["PAR","EPA","AMS","FRA","XETRA","CPH","OMX","LSE","AEB","ETR"]
        badge    = "EU" if any(ex in exchange.upper() for ex in eu_exc) else None

        # Secteur FR
        sector_map = {
            "Technology": "Technologie", "Healthcare": "Santé",
            "Industrials": "Industrie", "Financial Services": "Finance",
            "Consumer Cyclical": "Conso. cycl.", "Consumer Defensive": "Conso. staples",
            "Energy": "Énergie", "Basic Materials": "Matériaux",
            "Communication Services": "Médias & IA", "Real Estate": "Immobilier",
            "Utilities": "Services pub.",
        }
        sector_fr = sector_map.get(sector, sector[:14] if sector else "—")

        # Score breakdown lisible
        breakdown = {
            "momentum":      min(40, (10 if au_dessus_mm200 else 0) + (10 if au_dessus_mm50 else 0) + (10 if rsi_ok else 0) + (10 if vol_ok else 0)),
            "fondamentaux":  min(40, (15 if rev_growth > 0.10 else 8 if rev_growth > 0.05 else 0) + (10 if margins > 0.10 else 5 if margins > 0 else 0) + (10 if 0 < peg < 2 else 5 if peg < 3 else 0) + (5 if 0 < debt_eq < 100 else 0)),
            "analystes":     min(20, 20 if reco < 2.0 else 12 if reco < 2.5 else 6 if reco < 3.0 else 0),
            "rsi":           round(rsi, 1),
            "rev_growth_pct": round(rev_growth * 100, 1),
            "net_margin_pct": round(margins * 100, 1),
            "confiance":     round(confiance, 2),
            "sources":       ["Yahoo Finance"] + (["Finnhub"] if fh_data else []),
        }

        nom = info.get("shortName") or info.get("longName") or ticker

        return {
            "ticker":        ticker,
            "name":          nom[:22],
            "market":        info.get("exchange", "—")[:10],
            "sector":        sector_fr,
            "score":         score,
            "stars":         stars,
            "badge":         badge,
            "change":        "stable",
            "breakdown":     breakdown,
            "justification": generer_justification(nom, score, details, alertes),
        }

    except Exception as e:
        print(f"  ✗ {ticker}: {e}")
        return None

# ── CHANGELOG ────────────────────────────────────────────────────────────────
def load_previous(path="watchlist.json"):
    try:
        with open(path, encoding="utf-8") as f:
            return {s["ticker"]: s for s in json.load(f).get("stocks", [])}
    except:
        return {}

# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print(f"🔍 Analyse de {len(UNIVERS)} actions…")
    if FINNHUB_KEY:
        print(f"✓ Finnhub activé (validation croisée)")
    else:
        print(f"⚠ Finnhub non configuré — ajoutez FINNHUB_API_KEY dans les secrets GitHub")

    previous = load_previous()
    resultats = []

    for i, ticker in enumerate(UNIVERS):
        print(f"  [{i+1}/{len(UNIVERS)}] {ticker}…", end=" ")
        r = score_ticker(ticker)
        if r:
            resultats.append(r)
            conf = r["breakdown"].get("confiance", 1.0)
            src  = "+".join(r["breakdown"].get("sources", ["YF"]))
            print(f"score {r['score']} (confiance {conf:.0%}, sources: {src})")
        else:
            print("ignoré")

        # Respect rate limit Finnhub (60 req/min)
        if FINNHUB_KEY and (i + 1) % 50 == 0:
            time.sleep(3)

    # Top 25
    resultats.sort(key=lambda x: -x["score"])
    top25 = resultats[:25]
    current_tickers = {s["ticker"] for s in top25}

    # Changelog
    entrees  = [s for s in top25 if s["ticker"] not in previous]
    sorties  = [t for t in previous if t not in current_tickers]

    for s in top25:
        if s["ticker"] not in previous:
            s["change"] = "new"
        elif s["score"] > previous[s["ticker"]].get("score", 0) + 3:
            s["change"] = "up"
        elif s["score"] < previous[s["ticker"]].get("score", 0) - 3:
            s["change"] = "down"

    changelog = []
    for s in entrees[:5]:
        changelog.append({
            "action": "in",
            "ticker": s["ticker"],
            "name":   s["name"],
            "score":  s["score"],
            "reason": s["justification"],
        })
    for t in sorties[:5]:
        prev = previous[t]
        changelog.append({
            "action": "out",
            "ticker": t,
            "name":   prev.get("name", t),
            "score":  prev.get("score", 0),
            "reason": "Score insuffisant pour rester dans le top 25 cette semaine.",
        })

    for i, s in enumerate(top25):
        s["rank"] = i + 1

    d = date.today()
    output = {
        "updated_at":    str(d),
        "week":          f"Sem. {d.isocalendar()[1]} · {d.year}",
        "universe_size": len(resultats),
        "finnhub_active": bool(FINNHUB_KEY),
        "stocks":        top25,
        "changelog":     changelog,
    }

    with open("watchlist.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    top1 = top25[0]
    print(f"\n✅ watchlist.json — {len(top25)} actions")
    print(f"   #1 : {top1['name']} ({top1['score']}/100) — {top1['justification']}")

if __name__ == "__main__":
    main()
