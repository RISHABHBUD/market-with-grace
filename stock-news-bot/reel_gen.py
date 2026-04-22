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
TICKERS = {
    "tata steel":"TATASTEEL.NS","tata power":"TATAPOWER.NS",
    "tata motors":"TATAMOTORS.NS","reliance":"RELIANCE.NS",
    "infosys":"INFY.NS","hdfc bank":"HDFCBANK.NS",
    "icici bank":"ICICIBANK.NS","wipro":"WIPRO.NS","tcs":"TCS.NS",
    "bajaj":"BAJFINANCE.NS","adani":"ADANIENT.NS","nestle":"NESTLEIND.NS",
    "hcl":"HCLTECH.NS","axis bank":"AXISBANK.NS","kotak":"KOTAKBANK.NS",
    "sbi":"SBIN.NS","maruti":"MARUTI.NS","zomato":"ZOMATO.NS",
    "vedanta":"VEDL.NS","trent":"TRENT.NS","suzlon":"SUZLON.NS",
    "ola":"OLAELEC.NS","paytm":"PAYTM.NS","groww":"GROWW.NS",
}

def detect_ticker(title):
    t = title.lower()
    for k,v in TICKERS.items():
        if k in t: return v
    return None

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

    f1 = get_font(int(88*e), bold=True)
    f2 = get_font(int(72*e), bold=True)
    fonts = [f1, f2] if len(lines) > 1 else [f1]

    total_h = sum(f.size+16 for f in fonts[:len(lines)])
    y = H//2 - total_h//2 - 80

    for i, line in enumerate(lines[:2]):
        f = fonts[min(i, len(fonts)-1)]
        # Shadow
        draw.text((cx(draw,line,f)+3, y+3), line, font=f, fill=(180,150,220))
        draw.text((cx(draw,line,f), y), line, font=f, fill=TEXT_DARK)
        y += f.size + 16

    # "STOCK SPOTLIGHT" tag at bottom
    tag = "✦  STOCK SPOTLIGHT  ✦"
    tf  = get_font(36, bold=True)
    draw.rounded_rectangle([cx(draw,tag,tf)-24, H-320,
                             cx(draw,tag,tf)+tw(draw,tag,tf)+24, H-260],
                            radius=20, fill=ACCENT)
    draw.text((cx(draw,tag,tf), H-316), tag, font=tf, fill=WHITE)

    return np.array(img)


def f_stock(t, sd):
    """2-5s: Stock card snaps in fast, price counts up."""
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
    """5-13s: Chart draws itself, stats appear below."""
    img  = base()
    draw = ImageDraw.Draw(img)
    brand_bar(draw)

    lf = get_font(38, bold=True)
    draw.text((cx(draw,"30-Day Price Chart",lf), 225),
              "30-Day Price Chart", font=lf, fill=TEXT_MID)

    # Chart card
    cy2, ch2 = 285, 500
    draw.rounded_rectangle([55, cy2, W-55, cy2+ch2], radius=24,
                            fill=CARD, outline=(200,178,240), width=2)

    reveal = min(t/(total*0.8), 1.0)
    cw2    = W-120
    ch_img = chart_img.resize((cw2, int(chart_img.height*cw2/chart_img.width)), Image.LANCZOS)
    rw     = max(4, int(cw2*reveal))
    img.paste(ch_img.crop((0,0,rw,ch_img.height)), (80, cy2+15))

    # Stats row appears after chart is 60% drawn
    if reveal > 0.6:
        stat_e = ease_out((reveal-0.6)/0.4, 1.0)
        sy = cy2 + ch2 + 30

        stats = [
            ("P/E", f"{sd['pe']:.1f}" if sd.get('pe') else "N/A"),
            ("Mkt Cap", fmt_mcap(sd.get('mcap'))),
            ("Volume", fmt_vol(sd.get('vol'))),
            ("EPS", f"₹{sd['eps']:.1f}" if sd.get('eps') else "N/A"),
        ]
        box_w = (W-110)//4
        for i,(label,val) in enumerate(stats):
            bx = 55 + i*box_w
            by = int(sy + 60*(1-stat_e))
            draw.rounded_rectangle([bx+4, by, bx+box_w-8, by+110],
                                    radius=16, fill=CARD,
                                    outline=(200,178,240), width=1)
            draw.text((bx+4+cx(draw,label,get_font(24,True),box_w-12), by+10),
                      label, font=get_font(24,True), fill=TEXT_LIGHT)
            draw.text((bx+4+cx(draw,val,get_font(34,True),box_w-12), by+46),
                      val, font=get_font(34,True), fill=TEXT_DARK)

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

# ── Main ───────────────────────────────────────────────────────
def create_reel(article, output_path):
    title = re.sub(r"[^\x00-\x7F]+", "", article["title"]).strip()
    print(f"  Creating reel: {title[:65]}")

    ticker = detect_ticker(title)
    sd     = fetch_stock(ticker) if ticker else fetch_nifty()
    if not sd:
        print("  [!] Falling back to Nifty data")
        sd = dict(name="NIFTY 50", ticker="NIFTY", current=24500.0,
                  prev=24300.0, change=0.82, hi52=26277.0, lo52=21964.0,
                  pe=None, mcap=None, vol=None, eps=None,
                  history=[24000+i*25 for i in range(30)])

    print(f"  {sd['name']} | ₹{sd['current']:,.2f} | {sd['change']:+.2f}%")
    chart_img = make_chart(sd["history"], sd["change"])
    question  = hook_question(title)

    def make_clip(fn, dur, **kw):
        return VideoClip(lambda t: fn(t, **kw).astype(np.uint8),
                         duration=dur).with_fps(FPS)

    print("  Rendering sections...")
    clips = [
        make_clip(f_hook,     2.0,  question=question),
        make_clip(f_stock,    3.0,  sd=sd),
        make_clip(f_chart,    8.0,  sd=sd, chart_img=chart_img),
        make_clip(f_headline, 5.0,  headline=title),
        make_clip(f_outro,    2.0),
    ]

    video = concatenate_videoclips(clips)

    # Music
    music_files = [f for f in os.listdir(MUSIC_DIR)
                   if f.endswith((".mp3",".wav"))] if os.path.exists(MUSIC_DIR) else []
    if music_files:
        try:
            audio = AudioFileClip(os.path.join(MUSIC_DIR, random.choice(music_files)))
            audio = audio.with_subclip(0, min(DURATION, audio.duration)).audio_fadeout(2)
            video = video.with_audio(audio)
            print(f"  Music added")
        except Exception as e:
            print(f"  [!] Music error: {e}")
    else:
        print("  [!] No music files — add MP3s to stock-news-bot/music/")

    print("  Writing video...")
    video.write_videofile(output_path, fps=FPS, codec="libx264",
                          audio_codec="aac", temp_audiofile="temp_audio.m4a",
                          remove_temp=True, logger=None, preset="ultrafast")
    print(f"  [✓] Reel saved -> {output_path}")
