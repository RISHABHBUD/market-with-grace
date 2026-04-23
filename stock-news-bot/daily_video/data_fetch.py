"""
Fetches all market data needed for the daily video.
"""

import yfinance as yf
from fetcher import fetch_all_articles

NIFTY50_STOCKS = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
    "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
    "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
    "BAJFINANCE.NS","WIPRO.NS","HCLTECH.NS","ULTRACEMCO.NS","NESTLEIND.NS",
    "ADANIENT.NS","TATAMOTORS.NS","TATASTEEL.NS","SUNPHARMA.NS","ONGC.NS",
    "NTPC.NS","POWERGRID.NS","COALINDIA.NS","JSWSTEEL.NS","BAJAJFINSV.NS",
]

SECTORS = [
    ("IT",      ["INFY.NS","TCS.NS","WIPRO.NS","HCLTECH.NS"]),
    ("Banking", ["HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","AXISBANK.NS","KOTAKBANK.NS"]),
    ("Auto",    ["MARUTI.NS","TATAMOTORS.NS","BAJAJ-AUTO.NS"]),
    ("Pharma",  ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS"]),
    ("Energy",  ["RELIANCE.NS","ONGC.NS","NTPC.NS","POWERGRID.NS"]),
    ("Metal",   ["TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS"]),
]


def fetch_index(ticker):
    try:
        t    = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if len(hist) < 2:
            return None
        cur  = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2]
        chg  = cur - prev
        pct  = chg / prev * 100
        return dict(current=cur, change=chg, change_pct=pct,
                    high=hist["High"].iloc[-1], low=hist["Low"].iloc[-1],
                    history=hist["Close"].tolist())
    except Exception as e:
        print(f"  [!] Index fetch failed {ticker}: {e}")
        return None


def fetch_movers():
    movers = []
    for sym in NIFTY50_STOCKS:
        try:
            t    = yf.Ticker(sym)
            hist = t.history(period="2d")
            if len(hist) < 2:
                continue
            cur  = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
            pct  = (cur - prev) / prev * 100
            name = sym.replace(".NS", "").replace(".BO", "")
            movers.append(dict(name=name, change_pct=pct, price=cur, ticker=sym))
        except:
            continue

    movers.sort(key=lambda x: x["change_pct"], reverse=True)
    return movers[:5], movers[-5:][::-1]


def fetch_sectors():
    results = []
    for name, tickers in SECTORS:
        changes = []
        for sym in tickers:
            try:
                t    = yf.Ticker(sym)
                hist = t.history(period="2d")
                if len(hist) < 2:
                    continue
                cur  = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2]
                changes.append((cur - prev) / prev * 100)
            except:
                continue
        if changes:
            avg = sum(changes) / len(changes)
            results.append(dict(name=name, change_pct=avg))

    results.sort(key=lambda x: x["change_pct"], reverse=True)
    return results


def fetch_all_data():
    print("  Fetching Nifty 50...")
    nifty = fetch_index("^NSEI")

    print("  Fetching Sensex...")
    sensex = fetch_index("^BSESN")

    print("  Fetching top movers...")
    gainers, losers = fetch_movers()

    print("  Fetching sector data...")
    sectors = fetch_sectors()

    print("  Fetching news...")
    articles = fetch_all_articles()

    return dict(
        nifty=nifty   or dict(current=24500, change=100, change_pct=0.4,
                               high=24600, low=24400, history=[]),
        sensex=sensex or dict(current=80000, change=300, change_pct=0.37,
                               high=80200, low=79800, history=[]),
        top_gainers=gainers,
        top_losers=losers,
        sectors=sectors,
        news=articles[:5],
    )
