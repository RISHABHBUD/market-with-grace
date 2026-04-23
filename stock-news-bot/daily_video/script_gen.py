"""
Generates Hindi narration script from market data.
"""

from datetime import datetime


def get_hindi_script(data):
    """
    data = {
        nifty: {current, change, change_pct, high, low},
        sensex: {current, change, change_pct},
        top_gainers: [{name, change_pct, price}],
        top_losers:  [{name, change_pct, price}],
        sectors:     [{name, change_pct}],
        news:        [{title, summary}],
    }
    Returns dict of section -> hindi text
    """
    today    = datetime.now().strftime("%d %B %Y")
    weekday  = datetime.now().strftime("%A")
    weekdays = {"Monday":"Somvar","Tuesday":"Mangalvar","Wednesday":"Budhvar",
                "Thursday":"Guruvar","Friday":"Shukravar",
                "Saturday":"Shanivar","Sunday":"Ravivar"}
    hindi_day = weekdays.get(weekday, weekday)

    n  = data["nifty"]
    s  = data["sensex"]
    up = n["change_pct"] >= 0

    mood      = "teji" if up else "mandi"
    mood_word = "badha" if up else "gira"
    arrow     = "upar" if up else "neeche"

    scripts = {}

    # ── Intro ──────────────────────────────────────────────────
    scripts["intro"] = (
        f"Namaskar doston! Swagat hai aapka StockDev dot in mein. "
        f"Aaj hai {hindi_day}, {today}. "
        f"Main hoon aapka digital market analyst. "
        f"Aaj ke is episode mein hum dekhenge "
        f"aaj ke share bazaar ka poora haal, "
        f"top gainers aur losers, "
        f"sector performance, "
        f"aur aaj ki sabse important khabrein. "
        f"Toh chaliye shuru karte hain!"
    )

    # ── Market Overview ────────────────────────────────────────
    nifty_line = (
        f"Nifty pachaas aaj {mood_word} aur {abs(n['change_pct']):.2f} percent "
        f"ki {mood} ke saath {n['current']:,.0f} par band hua. "
        f"Aaj ka high tha {n['high']:,.0f} aur low tha {n['low']:,.0f}."
    )
    sensex_line = (
        f"Sensex bhi {mood_word} aur {abs(s['change_pct']):.2f} percent "
        f"ki badlaav ke saath {s['current']:,.0f} par band hua."
    )
    scripts["market"] = (
        f"Sabse pehle baat karte hain aaj ke overall market ki. "
        f"{nifty_line} "
        f"{sensex_line} "
        f"Aaj ka market {mood} mein raha aur investors ke liye "
        f"{'achha' if up else 'thoda mushkil'} din raha."
    )

    # ── Top Movers ─────────────────────────────────────────────
    gainers_text = ""
    for i, g in enumerate(data["top_gainers"][:3], 1):
        gainers_text += (
            f"Number {i} par hai {g['name']}, "
            f"jo aaj {g['change_pct']:.2f} percent upar gaya "
            f"aur {g['price']:,.2f} rupaye par band hua. "
        )

    losers_text = ""
    for i, l in enumerate(data["top_losers"][:3], 1):
        losers_text += (
            f"Number {i} par hai {l['name']}, "
            f"jo aaj {abs(l['change_pct']):.2f} percent neeche aaya "
            f"aur {l['price']:,.2f} rupaye par band hua. "
        )

    scripts["movers"] = (
        f"Ab baat karte hain aaj ke top gainers ki. "
        f"{gainers_text}"
        f"Ab dekhte hain aaj ke top losers ko. "
        f"{losers_text}"
    )

    # ── Sectors ────────────────────────────────────────────────
    sector_text = ""
    for sec in data["sectors"][:5]:
        direction = "upar" if sec["change_pct"] >= 0 else "neeche"
        sector_text += (
            f"{sec['name']} sector {abs(sec['change_pct']):.2f} percent {direction} raha. "
        )

    scripts["sectors"] = (
        f"Ab baat karte hain aaj ke sector performance ki. "
        f"{sector_text}"
        f"In sectors ko dhyan mein rakhein apni investment strategy banate waqt."
    )

    # ── News ───────────────────────────────────────────────────
    news_text = ""
    for i, item in enumerate(data["news"][:4], 1):
        title   = item["title"][:80]
        summary = item.get("summary", "")[:100]
        news_text += f"Khabar number {i}: {title}. {summary} "

    scripts["news"] = (
        f"Ab dekhte hain aaj ki sabse important khabrein. "
        f"{news_text}"
    )

    # ── Outro ──────────────────────────────────────────────────
    scripts["outro"] = (
        f"Toh doston, yeh tha aaj ka market update. "
        f"Agar aapko yeh video pasand aayi toh like karein, "
        f"channel ko subscribe karein, "
        f"aur apne doston ke saath share karein. "
        f"Hum milte hain kal ek naye market update ke saath. "
        f"Tab tak ke liye, invest karo samajhdaari se. "
        f"Jai Hind!"
    )

    return scripts
