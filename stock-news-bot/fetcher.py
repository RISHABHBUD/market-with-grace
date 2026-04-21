import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.livemint.com/market/stock-market-news"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

SKIP_PHRASES = [
    "log in", "sign up", "subscribe", "advertisement",
    "most traded", "stocks to watch today", "top losers", "top gainers",
    "live updates", "market live", "sensex live", "nifty live"
]


def clean(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    # Remove rupee symbol and other non-ASCII but keep digits/punctuation
    text = text.replace("\u20b9", "Rs").replace("\u2019", "'").replace("\u2018", "'")
    text = re.sub(r"[^\x00-\x7F]+", " ", text).strip()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_all_articles():
    print(f"  Fetching from Livemint stock market news...")
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [!] Request failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []
    seen = set()

    # Livemint uses <h2> tags for headlines, with optional <p> summary nearby
    for h2 in soup.find_all("h2"):
        a = h2.find("a", href=True)
        if not a:
            continue

        title = clean(a.get_text())
        href  = a.get("href", "")

        # Must be a real article link
        if not href or "/market/stock-market-news/" not in href:
            continue

        # Skip short or nav-like titles
        if len(title) < 25:
            continue

        # Skip generic listing/live pages
        if any(p in title.lower() for p in SKIP_PHRASES):
            continue

        key = title[:60].lower()
        if key in seen:
            continue
        seen.add(key)

        # Look for summary: check parent container for a <p> tag
        summary = ""
        parent = h2.find_parent()
        if parent:
            p_tag = parent.find("p")
            if p_tag:
                summary = clean(p_tag.get_text())

        # If no summary in parent, check grandparent
        if not summary:
            gp = h2.find_parent() and h2.find_parent().find_parent()
            if gp:
                p_tag = gp.find("p")
                if p_tag:
                    summary = clean(p_tag.get_text())

        articles.append({
            "title":   title,
            "summary": summary,
            "source":  "Indian Stock Market",
            "link":    href if href.startswith("http") else "https://www.livemint.com" + href,
        })

        if len(articles) >= 30:
            break

    print(f"  [✓] Found {len(articles)} articles")
    return articles
