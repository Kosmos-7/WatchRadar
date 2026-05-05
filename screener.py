"""
screener.py — Agent de sélection WatchRadar
Génère watchlist.json avec les 25 actions les mieux scorées.

Sources de données :
- Yahoo Finance (yfinance) : prix, indicateurs techniques, fondamentaux US
- Finnhub : validation croisée des fondamentaux (gratuit, 60 req/min)

Dépendances : pip install yfinance pandas ta numpy requests finnhub-python

─── MODÈLE TECHNIQUE ────────────────────────────────────────────────────────
Momentum (40 pts) = Croisement MM21/MM200 (20 pts)
                  + RSI (10 pts)
                  + Volume (5 pts)
                  + Régression (5 pts)

Croisement MM21/MM200 — études de référence :
  Win rate moyen après Golden Cross : 66.7 % (S&P 500, 20 ans)
  Confirmation volume (+40 %) → 72 % de précision
  Signal le plus fort : 5-10 premiers jours de bourse après le cross
  RSI optimal à l'entrée : 40-60 (ni surachat ni survente)

Droite de régression log-linéaire :
  z-score = distance du cours à sa tendance long terme en écarts-types
  Zone saine : z ∈ [-0.5σ, +1.5σ] → position idéale pour entrer
  Fenêtre : 10 ans pour tech/IA (boom récent), 20 ans pour les autres secteurs
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import time
import requests
from datetime import date
from ta.momentum import RSIIndicator

# ── FINNHUB (validation croisée) ─────────────────────────────────────────────
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

def finnhub_fundamentals(ticker):
    if not FINNHUB_KEY:
        return {}
    clean = ticker.replace(".PA","").replace(".DE","").replace(".AS","").replace(".L","").replace(".CO","")
    try:
        url = f"https://finnhub.io/api/v1/stock/metric?symbol={clean}&metric=all&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            d = r.json().get("metric", {})
            return {
                "pe_ttm":        d.get("peBasicExclExtraTTM"),
                "rev_growth_3y": d.get("revenueGrowth3Y"),
                "net_margin":    d.get("netProfitMarginTTM"),
                "roe":           d.get("roeTTM"),
                "debt_equity":   d.get("totalDebt/totalEquityAnnual"),
            }
    except:
        pass
    return {}

def valider_fondamentaux(yf_data, fh_data):
    if not fh_data:
        return (1.0, [])
    confiance, alertes = 1.0, []
    try:
        yf_m = yf_data.get("profitMargins") or 0
        fh_m = (fh_data.get("net_margin") or 0) / 100 if fh_data.get("net_margin") else 0
        if fh_m and abs(yf_m - fh_m) > 0.15:
            confiance -= 0.1
            alertes.append(f"Marge nette discordante YF:{yf_m:.1%} vs FH:{fh_m:.1%}")
        yf_d = yf_data.get("debtToEquity") or 0
        fh_d = fh_data.get("debt_equity")  or 0
        if fh_d and yf_d and abs(yf_d - fh_d * 100) > 100:
            confiance -= 0.1
        rev = yf_data.get("revenueGrowth") or 0
        if rev > 3.0:
            confiance -= 0.15
            alertes.append(f"Croissance CA suspectement élevée : {rev:.0%}")
    except Exception:
        pass
    return (max(0.7, confiance), alertes)

# ── CROISEMENT MM21 / MM200 ───────────────────────────────────────────────────
def detect_cross(close_series, volume_series=None):
    """
    Détecte le dernier croisement MM21/MM200 (Golden Cross ou Death Cross).

    Golden Cross : MM21 croise MM200 à la hausse → signal haussier.
      Études : 66.7 % de win rate historique sur S&P 500 (350j de hausse moy.)
      Signal maximal dans les 5-10 premiers jours de bourse après le cross.
      Confirmation volume (+40 %) → précision portée à 72 %.

    Death Cross : MM21 croise MM200 à la baisse → signal baissier.
      Faux positifs fréquents en marché range (38 % win rate en phase choppy).

    Retourne un dict avec :
      regime            : 'golden' | 'death'
      cross_type        : type du dernier croisement observé
      days_since_cross  : jours DE BOURSE depuis ce croisement
      spread_pct        : (MM21-MM200)/MM200 en % → conviction de tendance
      slope_mm21_pct    : variation MM21 sur 5j en % → vélocité
      volume_confirmed  : True si volume > moyenne au moment du cross
    """
    try:
        mm21  = close_series.rolling(21).mean()
        mm200 = close_series.rolling(200).mean()

        # Aligner sur les points où les deux MAs sont disponibles
        valid = mm21.notna() & mm200.notna()
        mm21_v  = mm21[valid]
        mm200_v = mm200[valid]

        if len(mm21_v) < 2:
            return _cross_default()

        diff = mm21_v - mm200_v

        # Régime actuel
        regime = "golden" if float(diff.iloc[-1]) > 0 else "death"

        # Détection des croisements (changements de signe de diff)
        signs      = np.sign(diff.values)
        prev_signs = np.roll(signs, 1)
        prev_signs[0] = signs[0]
        cross_mask = (signs != prev_signs) & (prev_signs != 0)
        cross_idxs = np.where(cross_mask)[0]

        if len(cross_idxs) > 0:
            last_cross_pos  = cross_idxs[-1]
            last_cross_type = "golden" if signs[last_cross_pos] > 0 else "death"
            days_since_cross = len(diff) - 1 - last_cross_pos  # jours de bourse

            # Confirmation volume au moment du cross
            volume_confirmed = False
            if volume_series is not None:
                vol_valid = volume_series[valid]
                if last_cross_pos > 0 and len(vol_valid) > last_cross_pos:
                    vol_at_cross = float(vol_valid.iloc[last_cross_pos])
                    vol_avg      = float(vol_valid.iloc[max(0, last_cross_pos-50):last_cross_pos].mean())
                    volume_confirmed = (vol_at_cross > vol_avg * 1.40) if vol_avg > 0 else False
        else:
            last_cross_type  = regime
            days_since_cross = 999
            volume_confirmed = False

        # Spread actuel MM21 vs MM200 (% du cours) → mesure la conviction
        spread_pct = float((mm21_v.iloc[-1] - mm200_v.iloc[-1]) / mm200_v.iloc[-1] * 100)

        # Pente de MM21 sur 5 jours de bourse (%) → vélocité du signal
        slope_mm21_pct = 0.0
        if len(mm21_v) >= 6:
            slope_mm21_pct = float((mm21_v.iloc[-1] - mm21_v.iloc[-6]) / mm21_v.iloc[-6] * 100)

        return {
            "regime":           regime,
            "cross_type":       last_cross_type,
            "days_since_cross": int(days_since_cross),
            "spread_pct":       round(spread_pct, 2),
            "slope_mm21_pct":   round(slope_mm21_pct, 2),
            "volume_confirmed": volume_confirmed,
        }

    except Exception:
        return _cross_default()

def _cross_default():
    return {
        "regime": "unknown", "cross_type": None,
        "days_since_cross": 999, "spread_pct": 0.0,
        "slope_mm21_pct": 0.0, "volume_confirmed": False,
    }

def cross_score(cross_info, rsi_val):
    """
    Score du croisement MM21/MM200 (0–20 pts).
    Intègre la fraîcheur du signal, le type de régime et la confirmation RSI.

    Golden Cross (signal haussier) :
      ≤ 10j de bourse : 20 pts — signal au plus fort (fenêtre optimale)
      11-30j          : 17 pts — signal frais, encore très actionnable
      31-60j          : 14 pts — confirmé, tendance qui se maintient
      61-180j         : 10 pts — régime haussier établi
      > 180j          :  7 pts — tendance durable, signal ancien
    Death Cross (signal baissier) :
      ≤ 30j de bourse :  0 pts — signal baissier actif
      31-90j          :  2 pts — baissier confirmé, éviter
      > 90j           :  4 pts — vieux régime, retournement possible

    Bonus : +2 pts si volume confirmé à la hausse au moment du cross.
    Bonus : +1 pt si RSI dans la zone idéale [40-65] au moment du scoring.
    """
    regime = cross_info.get("regime", "unknown")
    days   = cross_info.get("days_since_cross", 999)
    vol_ok = cross_info.get("volume_confirmed", False)

    if regime == "golden":
        if   days <= 10:  pts = 20
        elif days <= 30:  pts = 17
        elif days <= 60:  pts = 14
        elif days <= 180: pts = 10
        else:             pts = 7
        if vol_ok:        pts = min(pts + 2, 20)    # bonus volume
        if 40 <= rsi_val <= 65: pts = min(pts + 1, 20)  # bonus RSI zone idéale
    elif regime == "death":
        if   days <= 30:  pts = 0
        elif days <= 90:  pts = 2
        else:             pts = 4
    else:
        pts = 4  # inconnu → neutre prudent

    return pts

def cross_label(regime, days, cross_type):
    """Label lisible pour l'affichage frontend."""
    if regime == "golden":
        if days <= 10:  return f"Golden Cross · {days}j — Signal fort"
        if days <= 30:  return f"Golden Cross · {days}j"
        if days <= 60:  return f"Golden Cross confirmé · {days}j"
        return f"Régime haussier · {days}j"
    elif regime == "death":
        if days <= 30:  return f"Death Cross · {days}j — Baissier"
        if days <= 90:  return f"Death Cross confirmé · {days}j"
        return f"Régime baissier · {days}j"
    return "Données insuffisantes"

# ── RÉGRESSION LOG-LINÉAIRE ───────────────────────────────────────────────────
def calcul_regression(close_series):
    """
    Régression linéaire sur log(prix) — mesure l'écart du cours
    à sa tendance long terme en nombre d'écarts-types (z-score).

    z > +2  : surachat marqué (risque de retour vers la moyenne)
    +1..+2  : au-dessus de la tendance — normal pour actions en forte hausse
    -0.5..+1: zone neutre / saine — position idéale pour entrer
    < -1.5  : survente relative — rebond possible ou déclin structurel
    """
    try:
        prices = close_series.values.astype(float)
        if len(prices) < 30:
            return 0.0, 0.0
        log_p = np.log(prices)
        x = np.arange(len(log_p), dtype=float)
        slope, intercept = np.polyfit(x, log_p, 1)
        fitted    = intercept + slope * x
        residuals = log_p - fitted
        std_r = float(np.std(residuals, ddof=1))
        if std_r < 1e-8:
            return 0.0, round(slope * 252 * 100, 1)
        z_score        = float(residuals[-1]) / std_r
        pente_annuelle = slope * 252 * 100
        return round(z_score, 2), round(pente_annuelle, 1)
    except Exception:
        return 0.0, 0.0

def reg_signal_label(z):
    if   z >  2.0: return "surachat"
    elif z >  1.0: return "au-dessus"
    elif z > -0.5: return "neutre"
    elif z > -1.5: return "sous tendance"
    else:          return "survente"

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
    points = []

    # Signal de croisement (priorité haute)
    regime = details.get("cross_regime", "")
    days   = details.get("cross_days", 999)
    vol_c  = details.get("cross_vol_confirmed", False)
    vol_txt = " (volume confirmé)" if vol_c else ""

    if regime == "golden":
        if days <= 10:
            points.append(f"Golden Cross frais ({days}j){vol_txt} — fenêtre signal optimale")
        elif days <= 30:
            points.append(f"Golden Cross récent ({days}j){vol_txt}")
        elif days <= 60:
            points.append(f"Golden Cross confirmé ({days}j)")
    elif regime == "death" and days <= 30:
        points.append(f"⚠ Death Cross récent ({days}j) — signal baissier actif")

    # Régression
    reg_sig = details.get("reg_signal", "")
    reg_z   = details.get("reg_z", 0)
    if reg_sig == "neutre":
        points.append("cours proche de sa droite de régression")
    elif reg_sig == "au-dessus":
        points.append(f"légèrement au-dessus de sa régression (+{reg_z:.1f}σ)")
    elif reg_sig == "surachat":
        points.append(f"prix en surachat régression (+{reg_z:.1f}σ) — prudence")
    elif reg_sig in ("sous tendance", "survente"):
        points.append(f"prix sous sa droite de régression ({reg_z:.1f}σ)")

    # RSI
    if details.get("rsi_ok"):
        points.append("RSI en zone favorable")

    # Fondamentaux
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

    justif = f"Score {score}/100 — " + ", ".join(points[:4]) + "."
    if alertes:
        justif += f" ⚠ {alertes[0]}"
    return justif

# Fenêtres de régression (en jours de bourse, 252/an)
_REG_DAYS_TECH = 10 * 252   # 10 ans pour tech/IA (boom récent biaiserait une fenêtre plus longue)
_REG_DAYS_STD  = 20 * 252   # 20 ans pour les autres secteurs
_TECH_SECTORS  = {"Technology", "Communication Services",
                  "Consumer Cyclical"}  # Amazon, Alphabet, Meta classés ici par yfinance

# ── SCORING ──────────────────────────────────────────────────────────────────
def score_ticker(ticker):
    try:
        data = yf.Ticker(ticker)
        # Fetch max pour avoir suffisamment d'historique pour la régression long terme
        hist = data.history(period="max", auto_adjust=True)
        if len(hist) < 50:
            return None

        close  = hist["Close"].squeeze()
        volume = hist["Volume"].squeeze()
        # yfinance retourne les prix UK en pence (GBp) — convertir en GBP
        try:
            info_curr = getattr(data.fast_info, 'currency', '') or ''
        except Exception:
            info_curr = ''
        if info_curr == 'GBp':
            close = close / 100

        # Indicateurs techniques sur les 2 dernières années (MM21/MM200/RSI/volume)
        close_2y  = close.iloc[-504:]  if len(close)  > 504 else close
        volume_2y = volume.iloc[-504:] if len(volume) > 504 else volume

        prix   = float(close.iloc[-1])
        mm21   = float(close_2y.rolling(21).mean().iloc[-1])
        mm200  = float(close_2y.rolling(200).mean().iloc[-1])
        rsi    = float(RSIIndicator(close=close_2y, window=14).rsi().iloc[-1])
        vol_r  = float(volume_2y.tail(90).mean())
        vol_o  = float(volume_2y.head(90).mean())

        # ── Croisement MM21/MM200 (2 ans suffisent)
        cross_info = detect_cross(close_2y, volume_2y)
        cross_pts  = cross_score(cross_info, rsi)

        info = data.info

        # ── Régression log-linéaire long terme
        # Tech/IA : 10 ans (le boom IA biaiserait une droite sur 20 ans)
        # Autres  : 20 ans, ou tout l'historique disponible si moins
        yf_sector   = info.get("sector", "") or ""
        reg_days    = _REG_DAYS_TECH if yf_sector in _TECH_SECTORS else _REG_DAYS_STD
        close_reg   = close.iloc[-reg_days:] if len(close) >= reg_days else close
        regression_z, reg_pente = calcul_regression(close_reg)
        reg_signal              = reg_signal_label(regression_z)
        reg_zone_saine          = -0.5 <= regression_z <= 1.5

        rev_growth = info.get("revenueGrowth")     or 0
        margins    = info.get("profitMargins")      or 0
        peg        = info.get("pegRatio")           or 0
        debt_eq    = info.get("debtToEquity")       or 0
        reco       = info.get("recommendationMean") or 3.5

        fh_data = finnhub_fundamentals(ticker)
        confiance, alertes = valider_fondamentaux(info, fh_data)

        # ── Calcul du score ──────────────────────────────────────────────────
        score   = 0
        details = {}

        # Momentum (40 pts) = cross (20) + RSI (10) + volume (5) + régression (5)
        rsi_ok        = 50 <= rsi <= 70
        vol_ok        = vol_r > vol_o

        rsi_pts = 10 if rsi_ok else 0
        vol_pts = 5  if vol_ok else 0
        reg_pts = 5  if reg_zone_saine else 0
        momentum_total = cross_pts + rsi_pts + vol_pts + reg_pts

        score += momentum_total

        details["cross_regime"]        = cross_info["regime"]
        details["cross_days"]          = cross_info["days_since_cross"]
        details["cross_vol_confirmed"] = cross_info["volume_confirmed"]
        details["rsi_ok"]              = rsi_ok
        details["rsi"]                 = round(rsi, 1)
        details["reg_z"]               = regression_z
        details["reg_signal"]          = reg_signal

        # Fondamentaux (40 pts)
        fund_pts = 0
        if rev_growth > 0.10:   fund_pts += 15
        elif rev_growth > 0.05: fund_pts += 8
        if margins > 0.10:      fund_pts += 10
        elif margins > 0:       fund_pts += 5
        if 0 < peg < 2:         fund_pts += 10
        elif 2 <= peg < 3:      fund_pts += 5
        if 0 < debt_eq < 100:   fund_pts += 5
        score += fund_pts

        details["rev_growth"] = rev_growth
        details["net_margin"] = margins
        details["peg"]        = peg
        details["reco"]       = reco

        # Consensus analystes (20 pts)
        ana_pts = 0
        if reco < 2.0:   ana_pts = 20
        elif reco < 2.5: ana_pts = 12
        elif reco < 3.0: ana_pts = 6
        score += ana_pts

        # Bonus sectoriel (3 pts)
        sector = info.get("sector", "")
        if sector in ["Technology","Healthcare","Industrials","Financial Services"]:
            score = min(score + 3, 100)

        score = round(score * confiance)
        stars = 5 if score >= 80 else 4 if score >= 65 else 3 if score >= 50 else 2

        exchange = info.get("exchange", "")
        eu_exc   = ["PAR","EPA","AMS","FRA","XETRA","CPH","OMX","LSE","AEB","ETR"]
        badge    = "EU" if any(ex in exchange.upper() for ex in eu_exc) else None

        sector_map = {
            "Technology": "Technologie", "Healthcare": "Santé",
            "Industrials": "Industrie", "Financial Services": "Finance",
            "Consumer Cyclical": "Conso. cycl.", "Consumer Defensive": "Conso. staples",
            "Energy": "Énergie", "Basic Materials": "Matériaux",
            "Communication Services": "Médias & IA", "Real Estate": "Immobilier",
            "Utilities": "Services pub.",
        }
        sector_fr = sector_map.get(sector, sector[:14] if sector else "—")

        breakdown = {
            "momentum":              min(40, momentum_total),
            "fondamentaux":          min(40, fund_pts),
            "analystes":             min(20, ana_pts),
            # Croisement MM21/MM200
            "cross_regime":          cross_info["regime"],
            "cross_type":            cross_info["cross_type"],
            "cross_days_ago":        cross_info["days_since_cross"],
            "cross_spread_pct":      cross_info["spread_pct"],
            "cross_slope_mm21_pct":  cross_info["slope_mm21_pct"],
            "cross_volume_confirmed":cross_info["volume_confirmed"],
            "cross_pts":             cross_pts,
            # Indicateurs techniques
            "rsi":                   round(rsi, 1),
            "mm21":                  round(mm21, 2),
            "mm200":                 round(mm200, 2),
            # Régression
            "regression_z":          regression_z,
            "regression_signal":     reg_signal,
            "regression_pente_pct":  reg_pente,
            "regression_window_years": 10 if yf_sector in _TECH_SECTORS else (round(len(close_reg) / 252) if len(close_reg) < _REG_DAYS_STD else 20),
            # Fondamentaux
            "rev_growth_pct":        round(rev_growth * 100, 1),
            "net_margin_pct":        round(margins * 100, 1),
            "confiance":             round(confiance, 2),
            "sources":               ["Yahoo Finance"] + (["Finnhub"] if fh_data else []),
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
    print(f"   Modèle : Golden/Death Cross MM21/MM200 + Régression + RSI + Fondamentaux")
    if FINNHUB_KEY:
        print(f"✓ Finnhub activé (validation croisée)")
    else:
        print(f"⚠ Finnhub non configuré — ajoutez FINNHUB_API_KEY dans les secrets GitHub")

    previous  = load_previous()
    resultats = []

    for i, ticker in enumerate(UNIVERS):
        print(f"  [{i+1}/{len(UNIVERS)}] {ticker}…", end=" ")
        r = score_ticker(ticker)
        if r:
            resultats.append(r)
            bd      = r["breakdown"]
            conf    = bd.get("confiance", 1.0)
            src     = "+".join(bd.get("sources", ["YF"]))
            z       = bd.get("regression_z", 0)
            regime  = bd.get("cross_regime", "?")
            days    = bd.get("cross_days_ago", "?")
            spread  = bd.get("cross_spread_pct", 0)
            regime_icon = "🟢" if regime == "golden" else "🔴" if regime == "death" else "⚪"
            print(f"score {r['score']} | {regime_icon} {regime} {days}j ({spread:+.1f}%) | z={z:+.2f}σ | {conf:.0%} conf | {src}")
        else:
            print("ignoré")

        if FINNHUB_KEY and (i + 1) % 50 == 0:
            time.sleep(3)

    resultats.sort(key=lambda x: -x["score"])
    top25 = resultats[:25]

    if not top25:
        print("❌ Aucune action scorée — vérifiez la connexion réseau ou les tickers.")
        return

    current_tickers = {s["ticker"] for s in top25}
    entrees = [s for s in top25 if s["ticker"] not in previous]
    sorties = [t for t in previous if t not in current_tickers]

    for s in top25:
        if s["ticker"] not in previous:
            s["change"] = "new"
        elif s["score"] > previous[s["ticker"]].get("score", 0) + 3:
            s["change"] = "up"
        elif s["score"] < previous[s["ticker"]].get("score", 0) - 3:
            s["change"] = "down"

    changelog = []
    for s in entrees[:5]:
        changelog.append({"action":"in","ticker":s["ticker"],"name":s["name"],"score":s["score"],"reason":s["justification"]})
    for t in sorties[:5]:
        prev = previous[t]
        changelog.append({"action":"out","ticker":t,"name":prev.get("name",t),"score":prev.get("score",0),"reason":"Score insuffisant pour rester dans le top 25 cette semaine."})

    for i, s in enumerate(top25):
        s["rank"] = i + 1

    # ── Concentration sectorielle : alerter si >5 titres dans un même secteur ─
    from collections import Counter
    sector_counts = Counter(s["sector"] for s in top25)
    concentration_alerts = [
        f"{sector} ({n} titres sur 25 — risque de corrélation sectorielle)"
        for sector, n in sector_counts.items() if n >= 5
    ]
    if concentration_alerts:
        print("\n⚠ Concentration sectorielle détectée :")
        for alert in concentration_alerts:
            print(f"   → {alert}")

    d = date.today()
    output = {
        "updated_at":              str(d),
        "week":                    f"Sem. {d.isocalendar()[1]} · {d.year}",
        "universe_size":           len(resultats),
        "finnhub_active":          bool(FINNHUB_KEY),
        "stocks":                  top25,
        "changelog":               changelog,
        "concentration_alerts":    concentration_alerts,
        "sector_distribution":     dict(sector_counts.most_common()),
    }

    with open("watchlist.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    top1 = top25[0]
    print(f"\n✅ watchlist.json — {len(top25)} actions")
    print(f"   #1 : {top1['name']} ({top1['score']}/100)")
    print(f"   {top1['justification']}")

if __name__ == "__main__":
    main()
