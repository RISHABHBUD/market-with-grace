"""
Stock Spotlight Reel Generator — StockDev.in
25-second vertical reel (1080x1920) for Instagram.

Timeline:
  0-2s   : Hook — punchy question flashes in
  2-5s   : Stock card — name, price, change with counter animation
  5-13s  : Chart draws + 52w high/low + volume bar
  13-18s : Key stats ticker (P/E, Mkt Cap, EPS)
  18-23s : Headline types in fast
  23-25s : Outro CTA
"""

import os, re, random, textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoClip, AudioFileClip, concatenate_videoclips
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from config import PAGE_NAME, PAGE_HANDLE

W, H, FPS = 1080, 1920, 30
DURATION   = 25
MUSIC_DIR  = os.path.join(os.path.dirname(__file__), "music")

# Palette
BG_TOP       = (232, 218, 255)
BG_BOT       = (255, 238, 250)
CARD         = (255, 255, 255)
ACCENT       = (140, 90, 210)
ACCENT2      = (180, 130, 240)
ACCENT_LIGHT = (225, 205, 255)
TEXT_DARK    = (30, 15, 65)
TEXT_MID     = (100, 75, 150)
TEXT_LIGHT   = (165, 140, 195)
GREEN        = (30, 175, 95)
RED          = (215, 55, 75)
GOLD         = (255, 195, 50)
WHITE        = (255, 255, 255)

def get_font(size, bold=False):
    for p in (["arialbd.ttf","Arial_Bold.ttf","DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
               if bold else
               ["arial.ttf","Arial.ttf","DejaVuSans.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]):
        try: return ImageFont.truetype(p, size)
        except: continue
    return ImageFont.load_default()

def tw(draw, text, font):
    b = draw.textbbox((0,0), text, font=font); return b[2]-b[0]

def cx(draw, text, font, width=W):
    return (width - tw(draw, text, font)) // 2

def grad(w, h, top, bot):
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        t = y/h
        arr[y] = [int(top[i]+(bot[i]-top[i])*t) for i in range(3)]
    return arr

def ease_out(t, total): return 1-(1-min(t/max(total,0.001),1))**3
def ease_in_out(t, total):
    p = min(t/max(total,0.001),1)
    return p*p*(3-2*p)

def base(draw_fn=None):
    img = Image.fromarray(grad(W, H, BG_TOP, BG_BOT))
    # Soft blobs
    d = ImageDraw.Draw(img)
    d.ellipse([W-280,-120,W+80,240], fill=(210,185,250))
    d.ellipse([-80,H-280,240,H+80], fill=(225,200,255))
    if draw_fn: draw_fn(d, img)
    return img

def brand_bar(draw, y=55, h=145):
    draw.rounded_rectangle([55,y,W-55,y+h], radius=26, fill=ACCENT)
    draw.text((cx(draw,PAGE_NAME,get_font(58,True)),y+18),
              PAGE_NAME, font=get_font(58,True), fill=WHITE)
    draw.text((cx(draw,PAGE_HANDLE,get_font(32)),y+88),
              PAGE_HANDLE, font=get_font(32), fill=ACCENT_LIGHT)

# ── Stock data ─────────────────────────────────────────────────

# ── Dynamic stock detection ────────────────────────────────────
# Words to strip from title before searching
SKIP_WORDS = {
    "share","price","stock","shares","today","nse","bse","market",
    "india","indian","quarter","results","q4","q3","q2","q1","fy",
    "profit","loss","revenue","dividend","bonus","target","buy","sell",
    "hold","rating","analyst","report","jumps","surges","falls","drops",
    "rises","gains","rallies","crashes","hits","high","low","week","year",
    "52","percent","%","rs","crore","lakh","billion","million","the","a",
    "an","in","on","at","of","for","to","and","or","is","are","was","were",
    "its","this","that","with","from","after","before","as","by","how",
    "why","what","which","who","should","will","can","may","might","here",
    "new","latest","top","best","big","strong","weak","record","all","time",
    "set","board","meeting","date","declare","allotment","check","status",
    "online","ipo","listing","debut","trading","session","day","week",
    "month","april","march","february","january","2026","2025","2024",
}

def extract_candidates(title):
    """Extract potential company name candidates from title."""
    # Clean title
    clean = re.sub(r"[^\w\s]", " ", title)
    words = [w for w in clean.split() if len(w) > 2
             and w.lower() not in SKIP_WORDS
             and not w.isdigit()]

    candidates = []
    # Try 3-word, 2-word, 1-word combinations from the start
    for size in [4, 3, 2, 1]:
        for i in range(len(words) - size + 1):
            phrase = " ".join(words[i:i+size])
            if phrase not in candidates:
                candidates.append(phrase)
    return candidates[:12]  # limit API calls


# General market titles — skip stock search, go straight to Market Pulse
MARKET_GENERAL_TERMS = {
    "nifty 50","nifty50","sensex","nifty bank","bank nifty",
    "stock market","share market","market crash","market rally",
    "market today","market update","market live","market falls",
    "market rises","market gains","market drops","bull run","bear market",
    "market breadth","india vix","vix","advance decline","fii","dii",
    "foreign investor","domestic investor","market outlook","market analysis",
    "market wrap","closing bell","opening bell","pre market","post market",
    "global market","us market","wall street","dow jones","nasdaq",
    "market holiday","trading halt","circuit breaker","upper circuit","lower circuit",
}

def is_general_market_title(title):
    t = title.lower()
    return any(term in t for term in MARKET_GENERAL_TERMS)


def detect_ticker_dynamic(title):
    """Search Yahoo Finance dynamically for any Indian stock."""
    # Skip if it's a general market article
    if is_general_market_title(title):
        print("  General market title detected — skipping stock search")
        return None

    candidates = extract_candidates(title)
    print(f"  Searching tickers for candidates: {candidates[:5]}")

    for candidate in candidates:
        try:
            results = yf.Search(candidate, max_results=8).quotes
            for r in results:
                sym   = r.get("symbol", "")
                qtype = r.get("quoteType", "")
                # Only NSE/BSE EQUITY — strictly no ETF, MF, INDEX
                if (sym.endswith(".NS") or sym.endswith(".BO")) and qtype == "EQUITY":
                    print(f"  Found: {sym} for '{candidate}'")
                    return sym
        except Exception:
            continue
    return None


def fetch_top_movers():
    """Fetch top 3 Nifty gainers and losers for Market Pulse reel."""
    nifty50 = [
        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
        "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
        "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS",
        "BAJFINANCE.NS","WIPRO.NS","HCLTECH.NS","ULTRACEMCO.NS","NESTLEIND.NS",
    ]
    movers = []
    for sym in nifty50[:15]:  # check top 15 for speed
        try:
            t    = yf.Ticker(sym)
            hist = t.history(period="2d")
            if len(hist) < 2: continue
            cur  = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
            chg  = (cur - prev) / prev * 100
            name = sym.replace(".NS","")
            movers.append(dict(name=name, change=chg, price=cur))
        except:
            continue
    movers.sort(key=lambda x: x["change"], reverse=True)
    gainers = movers[:3]
    losers  = movers[-3:][::-1]
    return gainers, losers

def fetch_stock(ticker):
    try:
        s    = yf.Ticker(ticker)
        hist = s.history(period="60d")
        info = s.info
        if hist.empty: return None
        cur  = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2]
        chg  = (cur-prev)/prev*100
        hi52 = info.get("fiftyTwoWeekHigh", max(hist["Close"]))
        lo52 = info.get("fiftyTwoWeekLow",  min(hist["Close"]))
        pe   = info.get("trailingPE")
        mcap = info.get("marketCap")
        vol  = hist["Volume"].iloc[-1]
        eps  = info.get("trailingEps")
        name = info.get("shortName", ticker.replace(".NS",""))
        return dict(name=name, ticker=ticker.replace(".NS",""),
                    current=cur, prev=prev, change=chg,
                    hi52=hi52, lo52=lo52, pe=pe, mcap=mcap,
                    vol=vol, eps=eps,
                    history=hist["Close"].tolist()[-30:])
    except Exception as e:
        print(f"  [!] Stock fetch failed: {e}"); return None

def fetch_nifty():
    try:
        s    = yf.Ticker("^NSEI")
        hist = s.history(period="30d")
        if hist.empty: return None
        cur  = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2]
        return dict(name="NIFTY 50", ticker="NIFTY",
                    current=cur, prev=prev, change=(cur-prev)/prev*100,
                    hi52=max(hist["Close"]), lo52=min(hist["Close"]),
                    pe=None, mcap=None, vol=None, eps=None,
                    history=hist["Close"].tolist())
    except: return None

def fmt_mcap(v):
    if not v: return "N/A"
    if v >= 1e12: return f"₹{v/1e12:.1f}T"
    if v >= 1e9:  return f"₹{v/1e9:.1f}B"
    return f"₹{v/1e6:.0f}M"

def fmt_vol(v):
    if not v: return "N/A"
    if v >= 1e7: return f"{v/1e7:.1f}Cr"
    if v >= 1e5: return f"{v/1e5:.1f}L"
    return str(int(v))

def hook_question(title):
    t = title.lower()
    if any(x in t for x in ["jump","surge","soar","rally","gain","rise","up"]):
        return "Is this the breakout\nyou've been waiting for?"
    if any(x in t for x in ["fall","drop","crash","down","loss","decline"]):
        return "Should you be\nworried about this stock?"
    if any(x in t for x in ["result","profit","earnings","q4","q3","q2","q1"]):
        return "Results are in.\nWhat does it mean for you?"
    if any(x in t for x in ["dividend","bonus"]):
        return "Free money alert!\nHere's what's happening."
    if any(x in t for x in ["buy","target","bullish"]):
        return "Analysts are bullish.\nShould you follow?"
    return "Big news in the\nstock market today."

# ── Chart ──────────────────────────────────────────────────────
def make_chart(prices, change, w=940, h=400):
    color = "#1EAF5F" if change >= 0 else "#D73748"
    fig, ax = plt.subplots(figsize=(w/100, h/100), dpi=100)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F5F0FF")
    x = list(range(len(prices)))
    ax.plot(x, prices, color=color, linewidth=3.5, zorder=3)
    ax.fill_between(x, prices, min(prices)*0.997, color=color, alpha=0.18, zorder=2)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#D0C8E8"); ax.spines["bottom"].set_color("#D0C8E8")
    ax.tick_params(colors="#9080B8", labelsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,_: f"₹{v:,.0f}"))
    ax.grid(axis="y", color="#EAE4F8", linewidth=0.8, zorder=1)
    plt.tight_layout(pad=0.4)
    from io import BytesIO
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor="#FFFFFF")
    plt.close(fig); buf.seek(0)
    return Image.open(buf).convert("RGB")

# ── Frame builders ─────────────────────────────────────────────
def f_hook(t, question):
    """0-2s: Big hook question flashes in with scale effect."""
    img  = base()
    draw = ImageDraw.Draw(img)
    brand_bar(draw)

    lines = question.split("\n")
    e = ease_out(t, 0.5)

    # Pulsing background circle
    pulse = 1 + 0.04 * np.sin(t * 8)
    r = int(320 * pulse)
    draw.ellipse([W//2-r, H//2-r-80, W//2+r, H//2+r-80], fill=(215,195,250))

    # Flash effect — white overlay fades out
    if t < 0.15:
        alpha_val = int(255*(1-t/0.15))
        overlay = Image.new("RGBA", img.size, (255,255,255,alpha_val))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

    # Auto-fit font size so text never overflows W-120 margin
    max_w = W - 120
    for fsize in [88, 76, 64, 54, 46]:
        f1 = get_font(int(fsize*e), bold=True)
        f2 = get_font(int((fsize-14)*e), bold=True)
        fonts = [f1, f2] if len(lines) > 1 else [f1]
        if all(tw(draw, line, fonts[min(i,len(fonts)-1)]) <= max_w
               for i, line in enumerate(lines[:2])):
            break

    total_h = sum(f.size+16 for f in fonts[:len(lines)])
    y = H//2 - total_h//2 - 80

    for i, line in enumerate(lines[:2]):
        f = fonts[min(i, len(fonts)-1)]
        draw.text((cx(draw,line,f)+3, y+3), line, font=f, fill=(180,150,220))
        draw.text((cx(draw,line,f), y), line, font=f, fill=TEXT_DARK)
        y += f.size + 16

    # "STOCK SPOTLIGHT" tag at bottom
    tag = "STOCK SPOTLIGHT"
    tf  = get_font(36, bold=True)
    draw.rounded_rectangle([cx(draw,tag,tf)-24, H-320,
                             cx(draw,tag,tf)+tw(draw,tag,tf)+24, H-260],
                            radius=20, fill=ACCENT)
    draw.text((cx(draw,tag,tf), H-316), tag, font=tf, fill=WHITE)

    return np.array(img)


def make_company_avatar(sd):
    """
    Generate a creative company avatar image.
    Shows initials in a styled circle with performance color ring,
    mini sparkline, and sector badge. Always looks great, no external API needed.
    """
    size = 400
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    chg_col = GREEN if sd["change"] >= 0 else RED

    # Pick a unique background color per company (hash-based)
    name    = sd.get("name", "XX")
    hue_val = sum(ord(c) for c in name) % 360
    # Convert hue to RGB (simple pastel)
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(hue_val/360, 0.35, 0.95)
    bg_col  = (int(r*255), int(g*255), int(b*255), 255)

    # Outer performance ring
    ring_col = (*chg_col, 255)
    draw.ellipse([4, 4, size-4, size-4], fill=bg_col, outline=ring_col, width=12)

    # Inner circle
    pad = 28
    draw.ellipse([pad, pad, size-pad, size-pad], fill=(*bg_col[:3], 230))

    # Company initials — up to 2 chars
    words    = [w for w in name.split() if w and w[0].isupper()]
    initials = "".join(w[0] for w in words[:2]).upper() or name[:2].upper()

    # Auto-size font to fit
    for fsize in [160, 130, 110, 90]:
        f = get_font(fsize, bold=True)
        iw = tw(draw, initials, f)
        if iw < size - 80:
            break
    ih = f.size
    draw.text(((size - iw)//2, (size - ih)//2 - 10),
              initials, font=f, fill=(*ACCENT[:3], 255))

    # Mini sparkline at bottom of circle
    if sd.get("history") and len(sd["history"]) > 5:
        prices = sd["history"][-15:]
        mn, mx = min(prices), max(prices)
        if mx > mn:
            sp_x1, sp_x2 = 60, size-60
            sp_y1, sp_y2 = size-80, size-50
            pts = []
            for i, p in enumerate(prices):
                x = sp_x1 + int((sp_x2-sp_x1)*i/(len(prices)-1))
                y = sp_y2 - int((sp_y2-sp_y1)*(p-mn)/(mx-mn))
                pts.append((x, y))
            for i in range(len(pts)-1):
                draw.line([pts[i], pts[i+1]], fill=ring_col, width=4)

    # Change % badge at top
    chg_str = f"{'▲' if sd['change']>=0 else '▼'}{abs(sd['change']):.1f}%"
    cf      = get_font(32, bold=True)
    cw2     = tw(draw, chg_str, cf) + 24
    bx      = (size - cw2) // 2
    draw.rounded_rectangle([bx, 8, bx+cw2, 52], radius=20,
                            fill=(*chg_col, 230))
    draw.text((bx+12, 12), chg_str, font=cf, fill=(255,255,255,255))

    return img


def f_stock(t, sd):
    """2-4s: Stock card snaps in fast, price counts up."""
    img  = base()
    draw = ImageDraw.Draw(img)
    brand_bar(draw)

    e = ease_out(t, 0.4)
    card_y = int(H + (220 - H) * e)
    card_h = 520

    # Card shadow
    draw.rounded_rectangle([65+6, card_y+6, W-65+6, card_y+card_h+6],
                            radius=32, fill=(185,160,225))
    draw.rounded_rectangle([65, card_y, W-65, card_y+card_h],
                            radius=32, fill=CARD, outline=(195,170,240), width=2)
    draw.rounded_rectangle([65, card_y, 80, card_y+card_h], radius=32, fill=ACCENT)

    chg_col = GREEN if sd["change"] >= 0 else RED
    arrow   = "▲" if sd["change"] >= 0 else "▼"

    # Stock name
    name = sd["name"][:20]
    nf   = get_font(64, bold=True)
    draw.text((cx(draw,name,nf), card_y+28), name, font=nf, fill=TEXT_DARK)

    # Ticker badge
    tick = f"NSE: {sd['ticker']}"
    tf2  = get_font(30)
    tw2  = tw(draw,tick,tf2)+40
    draw.rounded_rectangle([W//2-tw2//2, card_y+108, W//2+tw2//2, card_y+152],
                            radius=18, fill=ACCENT_LIGHT)
    draw.text((cx(draw,tick,tf2), card_y+114), tick, font=tf2, fill=ACCENT)

    # Price counter animation
    count_progress = min(t/0.8, 1.0)
    displayed_price = sd["prev"] + (sd["current"]-sd["prev"]) * count_progress
    price_str = f"₹{displayed_price:,.2f}"
    pf = get_font(96, bold=True)
    draw.text((cx(draw,price_str,pf), card_y+172), price_str, font=pf, fill=TEXT_DARK)

    # Change badge
    chg_str = f"{arrow} {abs(sd['change']):.2f}%  Today"
    cf = get_font(44, bold=True)
    cw = tw(draw,chg_str,cf)+52
    draw.rounded_rectangle([W//2-cw//2, card_y+300, W//2+cw//2, card_y+360],
                            radius=26, fill=chg_col)
    draw.text((W//2-cw//2+26, card_y+308), chg_str, font=cf, fill=WHITE)

    # 52w high/low mini bars
    bar_y = card_y + 400
    draw.text((90, bar_y), "52W", font=get_font(28,True), fill=TEXT_LIGHT)
    lo_str = f"L: ₹{sd['lo52']:,.0f}"
    hi_str = f"H: ₹{sd['hi52']:,.0f}"
    draw.text((90, bar_y+36), lo_str, font=get_font(30), fill=RED)
    draw.text((W//2+20, bar_y+36), hi_str, font=get_font(30), fill=GREEN)

    # Progress bar showing where current price sits between 52w lo/hi
    bar_x1, bar_x2 = 90, W-90
    bar_w = bar_x2 - bar_x1
    draw.rounded_rectangle([bar_x1, bar_y+80, bar_x2, bar_y+100],
                            radius=8, fill=ACCENT_LIGHT)
    if sd["hi52"] > sd["lo52"]:
        pos = (sd["current"]-sd["lo52"])/(sd["hi52"]-sd["lo52"])
        pos = max(0.02, min(0.98, pos))
        fill_w = int(bar_w * pos * min(t/0.6, 1.0))
        draw.rounded_rectangle([bar_x1, bar_y+80, bar_x1+fill_w, bar_y+100],
                                radius=8, fill=chg_col)
        dot_x = bar_x1 + int(bar_w * pos * min(t/0.6, 1.0))
        draw.ellipse([dot_x-10, bar_y+74, dot_x+10, bar_y+106], fill=chg_col)

    return np.array(img)

def f_chart(t, sd, chart_img, total=8.0):
    """5-12s: Chart draws itself, then 6-stat grid fills below."""
    img  = base()
    draw = ImageDraw.Draw(img)
    brand_bar(draw)

    lf = get_font(38, bold=True)
    draw.text((cx(draw,"30-Day Price Chart",lf), 225),
              "30-Day Price Chart", font=lf, fill=TEXT_MID)

    # Chart card
    cy2, ch2 = 285, 440
    draw.rounded_rectangle([55, cy2, W-55, cy2+ch2], radius=24,
                            fill=CARD, outline=(200,178,240), width=2)

    reveal = min(t/(total*0.7), 1.0)
    cw2    = W - 120
    ch_img = chart_img.resize((cw2, int(chart_img.height*cw2/chart_img.width)), Image.LANCZOS)
    rw     = max(4, int(cw2*reveal))
    img.paste(ch_img.crop((0, 0, rw, ch_img.height)), (80, cy2+15))

    # 6-stat grid — 2 rows × 3 cols — slides up after chart 50% drawn
    if reveal > 0.5:
        stat_e = ease_out((reveal-0.5)/0.5, 1.0)
        chg_col = GREEN if sd["change"] >= 0 else RED

        stats = [
            ("P/E Ratio",  f"{sd['pe']:.1f}"    if sd.get('pe')   else "N/A",  None),
            ("Market Cap", fmt_mcap(sd.get('mcap')),                            None),
            ("EPS",        f"Rs{sd['eps']:.1f}"  if sd.get('eps')  else "N/A",  None),
            ("52W High",   f"Rs{sd['hi52']:,.0f}" if sd.get('hi52') else "N/A", GREEN),
            ("52W Low",    f"Rs{sd['lo52']:,.0f}" if sd.get('lo52') else "N/A", RED),
            ("Volume",     fmt_vol(sd.get('vol')),                              None),
        ]

        cols    = 3
        rows    = 2
        pad     = 12
        box_w   = (W - 55*2 - pad*(cols-1)) // cols
        box_h   = 130
        grid_y  = cy2 + ch2 + 20

        for idx, (label, val, val_color) in enumerate(stats):
            row = idx // cols
            col = idx % cols
            bx  = 55 + col*(box_w+pad)
            by  = int(grid_y + row*(box_h+pad) + 40*(1-stat_e))

            # Card with subtle accent top strip
            draw.rounded_rectangle([bx, by, bx+box_w, by+box_h],
                                    radius=18, fill=CARD,
                                    outline=(200,178,240), width=1)
            draw.rounded_rectangle([bx, by, bx+box_w, by+6],
                                    radius=18, fill=ACCENT_LIGHT)

            # Label
            lbl_f = get_font(22, bold=True)
            draw.text((bx + (box_w-tw(draw,label,lbl_f))//2, by+14),
                      label, font=lbl_f, fill=TEXT_LIGHT)

            # Value — auto-size to fit
            for vsize in [38, 32, 26]:
                vf = get_font(vsize, bold=True)
                if tw(draw, val, vf) <= box_w - 16:
                    break
            vc = val_color if val_color else TEXT_DARK
            draw.text((bx + (box_w-tw(draw,val,vf))//2, by+50),
                      val, font=vf, fill=vc)

        # 52W range bar spanning full width below grid
        bar_y = grid_y + rows*(box_h+pad) + 16
        if sd.get('hi52') and sd.get('lo52') and sd['hi52'] > sd['lo52']:
            bar_x1, bar_x2 = 55, W-55
            bar_w2 = bar_x2 - bar_x1
            draw.rounded_rectangle([bar_x1, bar_y, bar_x2, bar_y+16],
                                    radius=8, fill=ACCENT_LIGHT)
            pos    = (sd["current"]-sd["lo52"])/(sd["hi52"]-sd["lo52"])
            pos    = max(0.02, min(0.98, pos))
            fill_w = int(bar_w2 * pos * min((reveal-0.5)/0.5, 1.0))
            if fill_w > 0:
                draw.rounded_rectangle([bar_x1, bar_y, bar_x1+fill_w, bar_y+16],
                                        radius=8, fill=chg_col)
            dot_x = bar_x1 + fill_w
            draw.ellipse([dot_x-12, bar_y-8, dot_x+12, bar_y+24], fill=chg_col)
            # Labels
            draw.text((bar_x1, bar_y+24), f"52W L", font=get_font(22), fill=RED)
            draw.text((bar_x2-tw(draw,"52W H",get_font(22)), bar_y+24),
                      "52W H", font=get_font(22), fill=GREEN)

    return np.array(img)


def f_headline(t, headline, total=5.0):
    """18-23s: Headline types in fast with word-by-word reveal."""
    img  = base()
    draw = ImageDraw.Draw(img)
    brand_bar(draw)

    lf = get_font(40, bold=True)
    draw.text((cx(draw,"Breaking News",lf), 230),
              "Breaking News", font=lf, fill=ACCENT)
    # Underline
    uw = tw(draw,"Breaking News",lf)
    draw.rectangle([W//2-uw//2, 282, W//2+uw//2, 286], fill=ACCENT)

    draw.rounded_rectangle([55,310,W-55,H-200], radius=28,
                            fill=CARD, outline=(200,178,240), width=2)
    draw.rounded_rectangle([55,310,70,H-200], radius=28, fill=ACCENT)

    words   = headline.split()
    n       = max(1, int(len(words)*min(t/(total*0.85),1.0)))
    visible = " ".join(words[:n])
    lines   = textwrap.wrap(visible, width=22)

    hf = get_font(58, bold=True)
    y  = 370
    for line in lines[:7]:
        draw.text((cx(draw,line,hf), y), line, font=hf, fill=TEXT_DARK)
        y += 74

    # Blinking cursor
    if int(t*3)%2==0 and n<len(words):
        draw.rectangle([W//2-3, y, W//2+3, y+58], fill=ACCENT)

    return np.array(img)


def f_outro(t, total=2.0):
    """23-25s: Fast CTA snap."""
    img  = base()
    draw = ImageDraw.Draw(img)

    e = ease_out(t, 0.35)
    cy3 = int(H+(H*0.28-H)*e)

    draw.rounded_rectangle([55,cy3,W-55,cy3+300], radius=32, fill=ACCENT)
    draw.text((cx(draw,PAGE_NAME,get_font(80,True)), cy3+22),
              PAGE_NAME, font=get_font(80,True), fill=WHITE)
    draw.text((cx(draw,PAGE_HANDLE,get_font(38)), cy3+120),
              PAGE_HANDLE, font=get_font(38), fill=ACCENT_LIGHT)
    draw.text((cx(draw,"Where markets meet technology",get_font(30)), cy3+172),
              "Where markets meet technology", font=get_font(30), fill=ACCENT_LIGHT)

    cta1 = "Follow for daily"
    cta2 = "Stock Market Updates"
    draw.text((cx(draw,cta1,get_font(54,True)), cy3+340),
              cta1, font=get_font(54,True), fill=TEXT_DARK)
    draw.text((cx(draw,cta2,get_font(58,True)), cy3+410),
              cta2, font=get_font(58,True), fill=ACCENT)

    like = "Like  •  Share  •  Save  •  Follow"
    lf2  = get_font(36)
    draw.text((cx(draw,like,lf2), cy3+510), like, font=lf2, fill=TEXT_LIGHT)

    draw.rounded_rectangle([55,H-130,W-55,H-40], radius=22, fill=ACCENT)
    tag = "stockdev.in  |  Daily Market Intelligence"
    draw.text((cx(draw,tag,get_font(34,True)), H-112),
              tag, font=get_font(34,True), fill=WHITE)

    return np.array(img)

def f_market_pulse(t, nifty, gainers, losers, chart_img, total=9.0):
    """Fallback reel — Market Pulse. Fills full 1080x1920 canvas."""
    img  = base()
    draw = ImageDraw.Draw(img)
    brand_bar(draw)   # 55-200px

    reveal  = min(t / (total * 0.7), 1.0)
    chg_col = GREEN if nifty["change"] >= 0 else RED
    arrow   = "▲" if nifty["change"] >= 0 else "▼"

    # ── Section title ──────────────────────────────────────────
    draw.text((cx(draw,"Market Pulse",get_font(48,True)), 218),
              "Market Pulse", font=get_font(48,True), fill=ACCENT)

    # ── Nifty bar ──────────────────────────────────────────────
    nbar = f"NIFTY 50   {nifty['current']:,.0f}   {arrow}{abs(nifty['change']):.2f}%"
    nf2  = get_font(40, bold=True)
    nw   = min(tw(draw, nbar, nf2) + 60, W - 110)
    draw.rounded_rectangle([W//2-nw//2, 278, W//2+nw//2, 338],
                            radius=24, fill=chg_col)
    draw.text((W//2 - tw(draw,nbar,nf2)//2, 284), nbar, font=nf2, fill=WHITE)

    # ── Chart card — fixed height, clipped properly ────────────
    cy2  = 355
    ch2  = 420   # chart card height
    draw.rounded_rectangle([55, cy2, W-55, cy2+ch2],
                            radius=22, fill=CARD, outline=(200,178,240), width=2)

    cw2     = W - 130   # chart width inside card
    target_h = ch2 - 20
    # Resize chart to fit exactly inside card
    ch_img  = chart_img.resize((cw2, target_h), Image.LANCZOS)
    rw      = max(4, int(cw2 * reveal))
    # Crop and paste — guaranteed to stay inside card
    cropped = ch_img.crop((0, 0, rw, target_h))
    img.paste(cropped, (80, cy2 + 10))

    # ── Gainers + Losers — fills rest of screen ────────────────
    section_y = cy2 + ch2 + 22   # ~797px
    available = H - section_y - 55  # space until footer (~1068px)

    if reveal > 0.45:
        row_e = ease_out((reveal - 0.45) / 0.55, 1.0)

        # Headers
        hf = get_font(34, bold=True)
        draw.text((90, section_y), "TOP GAINERS", font=hf, fill=GREEN)
        draw.text((W//2 + 20, section_y), "TOP LOSERS", font=hf, fill=RED)

        # Divider line between columns
        draw.rectangle([W//2-1, section_y, W//2+1, H-55], fill=ACCENT_LIGHT)

        n_rows  = min(len(gainers), len(losers), 3)
        row_h   = (available - 52) // n_rows   # dynamic row height
        row_h   = min(row_h, 200)              # cap at 200px

        for i in range(n_rows):
            g  = gainers[i]
            l  = losers[i]
            ry = int(section_y + 52 + i * row_h + 30*(1-row_e))

            half = W//2 - 20

            # ── Gainer card ────────────────────────────────────
            draw.rounded_rectangle([65, ry, half, ry+row_h-12],
                                    radius=18, fill=(230,255,238),
                                    outline=(180,240,200), width=1)
            # Green top strip
            draw.rounded_rectangle([65, ry, half, ry+8], radius=18, fill=GREEN)

            gname = g["name"][:14]
            gprice = f"Rs{g['price']:,.1f}"
            gchg   = f"▲ {g['change']:.2f}%"

            nf3 = get_font(34, bold=True)
            pf3 = get_font(28)
            cf3 = get_font(36, bold=True)

            draw.text((85, ry+18), gname,  font=nf3, fill=TEXT_DARK)
            draw.text((85, ry+60), gprice, font=pf3, fill=TEXT_MID)
            draw.text((85, ry+96), gchg,   font=cf3, fill=GREEN)

            # ── Loser card ─────────────────────────────────────
            lx = W//2 + 20
            draw.rounded_rectangle([lx, ry, W-65, ry+row_h-12],
                                    radius=18, fill=(255,230,232),
                                    outline=(240,180,185), width=1)
            draw.rounded_rectangle([lx, ry, W-65, ry+8], radius=18, fill=RED)

            lname  = l["name"][:14]
            lprice = f"Rs{l['price']:,.1f}"
            lchg   = f"▼ {abs(l['change']):.2f}%"

            draw.text((lx+20, ry+18), lname,  font=nf3, fill=TEXT_DARK)
            draw.text((lx+20, ry+60), lprice, font=pf3, fill=TEXT_MID)
            draw.text((lx+20, ry+96), lchg,   font=cf3, fill=RED)

    # ── Footer brand bar ───────────────────────────────────────
    draw.rounded_rectangle([55, H-145, W-55, H-38], radius=24, fill=ACCENT)
    draw.text((cx(draw,PAGE_NAME,get_font(42,True)), H-128),
              PAGE_NAME, font=get_font(42,True), fill=WHITE)
    draw.text((cx(draw,PAGE_HANDLE,get_font(28)), H-76),
              PAGE_HANDLE, font=get_font(28), fill=ACCENT_LIGHT)

    return np.array(img)


# ── Main ───────────────────────────────────────────────────────
def create_reel(article, output_path):
    title = re.sub(r"[^\x00-\x7F]+", "", article["title"]).strip()
    print(f"  Creating reel: {title[:65]}")

    # Dynamic ticker detection
    ticker = detect_ticker_dynamic(title)
    sd     = fetch_stock(ticker) if ticker else None
    is_stock_reel = sd is not None

    if not is_stock_reel:
        print("  No specific stock found — using Market Pulse fallback")

    question  = hook_question(title)
    chart_img = make_chart(
        sd["history"] if sd else fetch_nifty()["history"],
        sd["change"]  if sd else 0
    )

    def make_clip(fn, dur, **kw):
        return VideoClip(lambda t: fn(t, **kw).astype(np.uint8),
                         duration=dur).with_fps(FPS)

    print("  Rendering sections...")

    if is_stock_reel:
        print(f"  {sd['name']} | Rs{sd['current']:,.2f} | {sd['change']:+.2f}%")

        clips = [
            make_clip(f_hook,     2.0, question=question),
            make_clip(f_stock,    2.0, sd=sd),
            make_clip(f_chart,    8.0, sd=sd, chart_img=chart_img),
            make_clip(f_headline, 5.0, headline=title),
            make_clip(f_outro,    2.0),
        ]
    else:
        # Market Pulse fallback
        nifty = fetch_nifty() or dict(name="NIFTY 50", current=24500.0,
                                       change=0.5, history=[])
        chart_img = make_chart(nifty["history"], nifty["change"])
        print("  Fetching top movers...")
        gainers, losers = fetch_top_movers()

        mq = "What moved the\nmarket today?"
        clips = [
            make_clip(f_hook,         2.0, question=mq),
            make_clip(f_market_pulse, 9.0, nifty=nifty, gainers=gainers,
                      losers=losers, chart_img=chart_img),            make_clip(f_headline,     5.0, headline=title),
            make_clip(f_outro,        2.0),
        ]

    video = concatenate_videoclips(clips)

    # Music
    music_files = [f for f in os.listdir(MUSIC_DIR)
                   if f.endswith((".mp3",".wav"))] if os.path.exists(MUSIC_DIR) else []
    if music_files:
        try:
            audio = AudioFileClip(os.path.join(MUSIC_DIR, random.choice(music_files)))
            dur   = sum(c.duration for c in clips)
            audio = audio.with_subclip(0, min(dur, audio.duration)).audio_fadeout(2)
            video = video.with_audio(audio)
            print("  Music added")
        except Exception as e:
            print(f"  [!] Music error: {e}")
    else:
        print("  [!] No music files — add MP3s to stock-news-bot/music/")

    print("  Writing video...")
    video.write_videofile(output_path, fps=FPS, codec="libx264",
                          audio_codec="aac", temp_audiofile="temp_audio.m4a",
                          remove_temp=True, logger=None, preset="ultrafast")
    print(f"  [✓] Reel saved -> {output_path}")
