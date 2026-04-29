"""
Stock Spotlight Reel — StockDev.in
Cinematic midnight/neon theme matching investment_reel.py visual language.

Stock Spotlight (25s):
  0-2s  : Hook — cinematic question with orbital rings
  2-5s  : Stock card — price counter, 52w bar
  5-13s : Chart — neon line draws, stat grid
  13-18s: Headline — typewriter with glow
  18-20s: Outro CTA

Market Pulse fallback (18s):
  0-2s  : Hook
  2-11s : Nifty chart + gainers/losers
  11-16s: Headline
  16-18s: Outro
"""

import math, os, re, random, textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops
from moviepy import VideoClip, AudioFileClip, concatenate_videoclips
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.collections import LineCollection
from io import BytesIO
from config import PAGE_NAME, PAGE_HANDLE

W, H, FPS = 1080, 1920, 30
MUSIC_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music")

# ── Cinematic palette (matches investment_reel.py) ─────────────
C_BG_TOP  = (9,   8,  30)
C_BG_BOT  = (22, 12,  52)
C_PANEL   = (22, 28,  58)
C_TEXT    = (236,239, 255)
C_MUTED   = (142,153, 196)
C_CYAN    = (32, 224, 255)
C_VIOLET  = (154,106, 255)
C_GOLD    = (255,210,  92)
C_GREEN   = (0,  243, 146)
C_RED     = (255, 80, 122)

# ── Helpers ────────────────────────────────────────────────────
def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def prog(t, s, e): return clamp((t-s)/(e-s)) if e>s else float(t>=s)
def eo3(t): t=clamp(t); return 1-(1-t)**3
def eo5(t): t=clamp(t); return 1-(1-t)**5
def eio(t): t=clamp(t); return t*t*(3-2*t)
def lerp(a,b,t): return a+(b-a)*clamp(t)
def lerp_col(c1,c2,t): return tuple(int(lerp(c1[i],c2[i],t)) for i in range(3))
def spring(t,s=9,d=0.5):
    t=clamp(t)
    if t in (0,1): return t
    return 1+math.exp(-d*s*t)*math.cos(s*t*1.55)

def font(size, bold=False):
    for p in (["arialbd.ttf","Arial_Bold.ttf","DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
               if bold else
               ["arial.ttf","Arial.ttf","DejaVuSans.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]):
        try: return ImageFont.truetype(p, size)
        except: pass
    return ImageFont.load_default()

def tw(d,t,f): b=d.textbbox((0,0),t,font=f); return b[2]-b[0]
def cx(d,t,f,w=W): return (w-tw(d,t,f))//2

def fmt_mcap(v):
    if not v: return "N/A"
    if v>=1e12: return f"Rs{v/1e12:.1f}T"
    if v>=1e9:  return f"Rs{v/1e9:.1f}B"
    return f"Rs{v/1e6:.0f}M"

def fmt_vol(v):
    if not v: return "N/A"
    if v>=1e7: return f"{v/1e7:.1f}Cr"
    if v>=1e5: return f"{v/1e5:.1f}L"
    return str(int(v))

def base_canvas(t=0.0, tint=None):
    arr = np.zeros((H,W,3), dtype=np.uint8)
    for y in range(H):
        arr[y] = lerp_col(C_BG_TOP, C_BG_BOT, y/H)
    img = Image.fromarray(arr)
    d   = ImageDraw.Draw(img)
    # Diagonal light sweeps
    for i in range(6):
        x = int((W*0.18*i + (t*130)%(W*1.2)) - W*0.2)
        d.polygon([(x,0),(x+120,0),(x-260,H),(x-380,H)], fill=(40,30,82,36))
    # Film grain
    rng   = np.random.default_rng(int(t*1000)+42)
    noise = rng.integers(0,18,size=(H,W),dtype=np.uint8)
    layer = Image.fromarray(noise,"L").convert("RGB")
    img   = ImageChops.screen(img, layer)
    if tint:
        ov = Image.new("RGBA", img.size, (0,0,0,0))
        od = ImageDraw.Draw(ov)
        for r in range(6,0,-1):
            rad = 180+r*60; a = int(18*(r/6))
            od.ellipse([W-rad-60,80-rad,W+rad-60,80+rad], fill=(*tint,a))
        img = Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")
    return img

def hud_grid(img, t, alpha=28):
    d = ImageDraw.Draw(img)
    step = 120
    xs = int((t*40)%step); ys = int((t*26)%step)
    for x in range(-step,W+step,step):
        d.line([(x+xs,0),(x+xs,H)], fill=(70,86,145,alpha), width=1)
    for y in range(-step,H+step,step):
        d.line([(0,y+ys),(W,y+ys)], fill=(70,86,145,alpha), width=1)
    return img

def soft_glow(img, x, y, radius, color):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    od = ImageDraw.Draw(ov)
    for r in range(6,0,-1):
        rr=radius+(6-r)*22; a=int(70*r/6)
        od.ellipse([x-rr,y-rr,x+rr,y+rr], fill=(*color,a))
    return Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")

def glow_text(img, txt, f, x, y, color, glow):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    od = ImageDraw.Draw(ov)
    for r in [8,5,3]:
        od.text((x,y), txt, font=f, fill=(*glow, 80//max(1,r//2)))
    img = Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")
    ImageDraw.Draw(img).text((x,y), txt, font=f, fill=color)
    return img

def cracker_burst(img, cx0, cy0, t, dur, color, seed=1, n=60):
    p = prog(t, 0, dur)
    if p<=0: return img
    rng = random.Random(seed)
    ov  = Image.new("RGBA", img.size, (0,0,0,0))
    od  = ImageDraw.Draw(ov)
    for _ in range(n):
        ang = rng.uniform(0, math.tau)
        dist = rng.uniform(80,400)*eo3(p)
        px = int(cx0+math.cos(ang)*dist)
        py = int(cy0+math.sin(ang)*dist*0.75)
        r  = rng.randint(2,8)
        a  = int(255*(1-p)*rng.uniform(0.4,1.0))
        col = color if rng.random()>0.35 else C_GOLD
        od.ellipse([px-r,py-r,px+r,py+r], fill=(*col,a))
        if rng.random()>0.8:
            sx=int(px+math.cos(ang)*rng.uniform(8,22))
            sy=int(py+math.sin(ang)*rng.uniform(8,22))
            od.line([(px,py),(sx,sy)], fill=(*col,a), width=2)
    return Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")

def hud_footer(d, img):
    """Branded footer bar."""
    d.rounded_rectangle([46,H-148,W-46,H-54], radius=26, fill=C_PANEL)
    d.rectangle([46,H-148,W-46,H-142], fill=C_CYAN)
    d.text((74,H-128), PAGE_NAME, font=font(38,True), fill=C_TEXT)
    hf = font(28)
    d.text((W-74-tw(d,PAGE_HANDLE,hf),H-120), PAGE_HANDLE, font=hf, fill=C_MUTED)

# ── Stock data (unchanged logic) ──────────────────────────────
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
MARKET_GENERAL_TERMS = {
    "nifty 50","nifty50","sensex","nifty bank","bank nifty",
    "stock market","share market","market crash","market rally",
    "market today","market update","market live","market falls",
    "market rises","market gains","market drops","bull run","bear market",
    "market breadth","india vix","vix","advance decline","fii","dii",
    "foreign investor","domestic investor","market outlook","market analysis",
    "market wrap","closing bell","opening bell","pre market","post market",
    "global market","us market","wall street","dow jones","nasdaq",
}

def is_general(title):
    t = title.lower()
    return any(term in t for term in MARKET_GENERAL_TERMS)

def extract_candidates(title):
    clean = re.sub(r"[^\w\s]"," ",title)
    words = [w for w in clean.split() if len(w)>2
             and w.lower() not in SKIP_WORDS and not w.isdigit()]
    cands = []
    for size in [4,3,2,1]:
        for i in range(len(words)-size+1):
            p = " ".join(words[i:i+size])
            if p not in cands: cands.append(p)
    return cands[:12]

def detect_ticker(title):
    if is_general(title):
        print("  General market title — Market Pulse mode")
        return None
    cands = extract_candidates(title)
    print(f"  Searching: {cands[:4]}")
    for c in cands:
        try:
            for r in yf.Search(c, max_results=8).quotes:
                sym = r.get("symbol","")
                if (sym.endswith(".NS") or sym.endswith(".BO")) and r.get("quoteType")=="EQUITY":
                    print(f"  Found: {sym}")
                    return sym
        except: continue
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
        return dict(
            name=info.get("shortName", ticker.replace(".NS","")),
            ticker=ticker.replace(".NS","").replace(".BO",""),
            current=cur, prev=prev, change=chg,
            hi52=info.get("fiftyTwoWeekHigh", max(hist["Close"])),
            lo52=info.get("fiftyTwoWeekLow",  min(hist["Close"])),
            pe=info.get("trailingPE"), mcap=info.get("marketCap"),
            vol=hist["Volume"].iloc[-1], eps=info.get("trailingEps"),
            history=hist["Close"].tolist()[-30:],
        )
    except Exception as e:
        print(f"  [!] Stock fetch: {e}"); return None

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

def fetch_top_movers():
    syms = ["RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
            "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
            "LT.NS","AXISBANK.NS","MARUTI.NS","TITAN.NS","BAJFINANCE.NS"]
    movers = []
    for sym in syms:
        try:
            h = yf.Ticker(sym).history(period="2d")
            if len(h)<2: continue
            cur=h["Close"].iloc[-1]; prev=h["Close"].iloc[-2]
            movers.append(dict(name=sym.replace(".NS",""),
                               change=(cur-prev)/prev*100, price=cur))
        except: continue
    movers.sort(key=lambda x:x["change"], reverse=True)
    return movers[:3], movers[-3:][::-1]

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

# ── Chart generators ───────────────────────────────────────────
def make_stock_chart(prices, change, w=980, h=520):
    """30-day price chart with neon glow line."""
    up  = change >= 0
    acc = np.array([0/255,243/255,146/255]) if up else np.array([1.0,80/255,122/255])
    lc  = "#00F392" if up else "#FF507A"
    gc  = "#00FF99" if up else "#FF2050"

    fig, ax = plt.subplots(figsize=(w/100,h/100), dpi=100)
    fig.patch.set_facecolor("#0A0B1D")
    ax.set_facecolor("#111530")

    x = list(range(len(prices)))
    for lw, a in [(16,0.04),(10,0.10),(5,0.28),(2.5,1.0)]:
        ax.plot(x, prices, color=lc, linewidth=lw, alpha=a,
                solid_capstyle="round", zorder=4)
    ax.fill_between(x, prices, min(prices)*0.995, color=lc, alpha=0.12, zorder=2)
    ax.axhline(y=prices[0], color="#FFFFFF", lw=1, ls="--", alpha=0.2)

    # Glowing tip
    for s,a in [(300,0.05),(120,0.18),(40,0.5),(14,1.0)]:
        ax.scatter([x[-1]], [prices[-1]], color=gc, s=s, alpha=a, zorder=6)

    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#2A3158"); ax.spines["bottom"].set_color("#2A3158")
    ax.tick_params(colors="#C7D1FF", labelsize=10, length=0)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda v,_: f"Rs{v/1e5:.0f}L" if v>=1e5 else f"Rs{v:,.0f}"))
    ax.grid(axis="y", color="#1A2040", lw=0.7, alpha=0.6)
    plt.subplots_adjust(left=0.13,right=0.98,top=0.96,bottom=0.09)
    buf = BytesIO()
    plt.savefig(buf, format="png", facecolor="#0A0B1D", dpi=100)
    plt.close(fig); buf.seek(0)
    return Image.open(buf).convert("RGB")

def make_nifty_chart(history, change, w=980, h=480):
    """Nifty index chart for Market Pulse."""
    return make_stock_chart(history, change, w, h)


# ── Frame builders ─────────────────────────────────────────────

def f_hook(t, question, total=2.0):
    """0-2s: Cinematic hook with orbital rings."""
    img = base_canvas(t, tint=C_VIOLET)
    img = hud_grid(img, t, alpha=22)
    d   = ImageDraw.Draw(img)

    # Orbital rings
    for i in range(3):
        rot = int((t*90+i*120)%360)
        rad = 200+i*44
        box = [W//2-rad, H//2-280-rad, W//2+rad, H//2-280+rad]
        d.arc(box, start=rot, end=rot+250, fill=(*C_CYAN,150), width=3)
        d.arc(box, start=rot+120, end=rot+300, fill=(*C_VIOLET,120), width=2)

    # Hook banner
    p_b = eo3(prog(t,0.0,0.8))
    by  = int(180-30*(1-p_b))
    d.rounded_rectangle([80,by,W-80,by+88], radius=26, fill=C_PANEL)
    d.rectangle([80,by,W-80,by+7], fill=C_CYAN)
    d.text((cx(d,"STOCK SPOTLIGHT",font(34,True)), by+26),
           "STOCK SPOTLIGHT", font=font(34,True), fill=C_TEXT)

    # Question text
    lines = question.split("\n")
    p_q   = eo5(prog(t,0.2,1.2))
    max_w = W-100
    for fsize in [88,76,64,54,46]:
        f1 = font(int(fsize*p_q),True)
        f2 = font(int((fsize-14)*p_q),True)
        fs = [f1,f2] if len(lines)>1 else [f1]
        if all(tw(d,l,fs[min(i,len(fs)-1)])<=max_w for i,l in enumerate(lines[:2])):
            break
    total_h = sum(f.size+14 for f in fs[:len(lines)])
    y = H//2 - total_h//2 - 60
    for i,line in enumerate(lines[:2]):
        f = fs[min(i,len(fs)-1)]
        img = glow_text(img, line, f, cx(d,line,f), y, C_TEXT, C_CYAN)
        d   = ImageDraw.Draw(img)
        y  += f.size+14

    hud_footer(d, img)
    return np.array(img)


def f_stock(t, sd, total=3.0):
    """2-5s: Stock card with price counter and 52w bar."""
    img = base_canvas(t, tint=C_CYAN if sd["change"]>=0 else C_RED)
    img = hud_grid(img, t, alpha=26)
    img = soft_glow(img, W-100, 160, 160, C_CYAN)
    d   = ImageDraw.Draw(img)

    up  = sd["change"] >= 0
    acc = C_GREEN if up else C_RED
    arr = "▲" if up else "▼"

    e = eo3(prog(t,0,0.5))

    # Card
    card_y = int(H+(260-H)*e)
    card_h = 580
    d.rounded_rectangle([46,card_y+8,W-46+8,card_y+card_h+8], radius=30, fill=(10,12,30))
    d.rounded_rectangle([46,card_y,W-46,card_y+card_h], radius=30, fill=C_PANEL)
    d.rounded_rectangle([46,card_y,W-46,card_y+10], radius=30, fill=C_CYAN)

    # Name
    name = sd["name"][:22]
    nf   = font(60,True)
    img  = glow_text(img, name, nf, cx(d,name,nf), card_y+28, C_TEXT, C_CYAN)
    d    = ImageDraw.Draw(img)

    # Ticker badge
    tick = f"NSE: {sd['ticker']}"
    tf2  = font(30)
    tw2  = tw(d,tick,tf2)+40
    d.rounded_rectangle([W//2-tw2//2,card_y+106,W//2+tw2//2,card_y+148],
                         radius=18, fill=(30,36,72))
    d.text((cx(d,tick,tf2),card_y+112), tick, font=tf2, fill=C_MUTED)

    # Price counter
    cp  = min(t/0.8,1.0)
    disp = sd["prev"]+(sd["current"]-sd["prev"])*cp
    ps  = f"Rs {disp:,.2f}"
    pf  = font(88,True)
    img = glow_text(img, ps, pf, cx(d,ps,pf), card_y+168, C_TEXT, acc)
    d   = ImageDraw.Draw(img)

    # Change badge
    cs  = f"{arr} {abs(sd['change']):.2f}%  Today"
    cf  = font(42,True)
    cw2 = tw(d,cs,cf)+52
    d.rounded_rectangle([W//2-cw2//2,card_y+300,W//2+cw2//2,card_y+358],
                         radius=26, fill=acc)
    d.text((W//2-cw2//2+26,card_y+308), cs, font=cf, fill=(8,10,24))

    # 52w bar
    bar_y = card_y+400
    d.text((80,bar_y), "52W RANGE", font=font(26,True), fill=C_MUTED)
    lo_s = f"Rs{sd['lo52']:,.0f}"; hi_s = f"Rs{sd['hi52']:,.0f}"
    d.text((80,bar_y+36), lo_s, font=font(28), fill=C_RED)
    d.text((W-80-tw(d,hi_s,font(28)),bar_y+36), hi_s, font=font(28), fill=C_GREEN)
    bx1,bx2 = 80,W-80; bw = bx2-bx1
    d.rounded_rectangle([bx1,bar_y+80,bx2,bar_y+96], radius=8, fill=(30,36,72))
    if sd["hi52"]>sd["lo52"]:
        pos = clamp((sd["current"]-sd["lo52"])/(sd["hi52"]-sd["lo52"]))
        fw  = int(bw*pos*min(t/0.6,1.0))
        d.rounded_rectangle([bx1,bar_y+80,bx1+fw,bar_y+96], radius=8, fill=acc)
        dx  = bx1+fw
        d.ellipse([dx-10,bar_y+74,dx+10,bar_y+102], fill=acc)

    hud_footer(d, img)
    return np.array(img)


def f_chart(t, sd, chart_img, total=8.0):
    """5-13s: Neon chart draws + stat grid."""
    img = base_canvas(t, tint=C_CYAN if sd["change"]>=0 else C_RED)
    img = hud_grid(img, t, alpha=24)
    d   = ImageDraw.Draw(img)

    up  = sd["change"]>=0
    acc = C_GREEN if up else C_RED

    # Header bar
    d.rounded_rectangle([46,42,W-46,210], radius=26, fill=C_PANEL)
    d.rectangle([46,42,W-46,50], fill=C_CYAN)
    d.text((74,68), sd["name"][:22], font=font(50,True), fill=C_TEXT)
    d.text((74,136), "30-Day Price Chart", font=font(28), fill=C_MUTED)

    # Chart
    chart_y = 224; cw,ch = W-80,580
    reveal  = eio(prog(t,0,total*0.75))
    key_img = chart_img.resize((cw,ch), Image.LANCZOS)
    rw      = max(4, int(cw*reveal))
    d.rounded_rectangle([40,chart_y-10,W-40,chart_y+ch+10], radius=24, fill=(11,12,30))
    img.paste(key_img.crop((0,0,rw,ch)), (40,chart_y))
    d = ImageDraw.Draw(img)

    # Stat grid after 55% drawn
    if reveal>0.55:
        se = eo3(prog(reveal,0.55,1.0))
        stats = [
            ("P/E",     f"{sd['pe']:.1f}"   if sd.get('pe')  else "N/A", C_GOLD),
            ("Mkt Cap", fmt_mcap(sd.get('mcap')),                         C_CYAN),
            ("EPS",     f"Rs{sd['eps']:.1f}" if sd.get('eps') else "N/A", C_VIOLET),
            ("52W Hi",  f"Rs{sd['hi52']:,.0f}" if sd.get('hi52') else "N/A", C_GREEN),
            ("52W Lo",  f"Rs{sd['lo52']:,.0f}" if sd.get('lo52') else "N/A", C_RED),
            ("Volume",  fmt_vol(sd.get('vol')),                            C_MUTED),
        ]
        grid_y = chart_y+ch+20
        bw3    = (W-80)//3; bh3 = 120; pad = 10
        for idx,(lbl,val,vc) in enumerate(stats):
            row=idx//3; col=idx%3
            bx = 40+col*(bw3+pad)
            by = int(grid_y+row*(bh3+pad)+30*(1-se))
            d.rounded_rectangle([bx,by,bx+bw3,by+bh3], radius=16, fill=C_PANEL)
            d.rounded_rectangle([bx,by,bx+bw3,by+6], radius=16, fill=vc)
            d.text((bx+cx(d,lbl,font(22,True),bw3),by+14), lbl, font=font(22,True), fill=C_MUTED)
            for vs in [36,30,24]:
                vf=font(vs,True)
                if tw(d,val,vf)<=bw3-16: break
            d.text((bx+cx(d,val,vf,bw3),by+48), val, font=vf, fill=vc)

    hud_footer(d, img)
    return np.array(img)


def f_headline(t, headline, total=5.0):
    """Headline types in word-by-word with glow."""
    img = base_canvas(t, tint=C_VIOLET)
    img = hud_grid(img, t, alpha=20)
    d   = ImageDraw.Draw(img)

    # "BREAKING NEWS" header
    d.rounded_rectangle([46,42,W-46,160], radius=26, fill=C_PANEL)
    d.rectangle([46,42,W-46,50], fill=C_VIOLET)
    img = glow_text(img,"BREAKING NEWS",font(44,True),
                    cx(d,"BREAKING NEWS",font(44,True)),72,C_TEXT,C_VIOLET)
    d = ImageDraw.Draw(img)

    # Headline card
    d.rounded_rectangle([46,180,W-46,H-170], radius=28, fill=C_PANEL)
    d.rounded_rectangle([46,180,58,H-170], radius=28, fill=C_VIOLET)

    words   = headline.split()
    n       = max(1, int(len(words)*min(t/(total*0.85),1.0)))
    visible = " ".join(words[:n])
    lines   = textwrap.wrap(visible, width=22)
    hf      = font(56,True)
    y       = 240
    for line in lines[:7]:
        img = glow_text(img, line, hf, cx(d,line,hf), y, C_TEXT, C_CYAN)
        d   = ImageDraw.Draw(img)
        y  += 74
    if int(t*3)%2==0 and n<len(words):
        d.rectangle([W//2-3,y,W//2+3,y+56], fill=C_VIOLET)

    hud_footer(d, img)
    return np.array(img)


def f_outro(t, total=2.0):
    """Outro CTA."""
    img = base_canvas(t, tint=C_CYAN)
    img = soft_glow(img, W//2, H//2-200, 200, C_CYAN)
    d   = ImageDraw.Draw(img)

    p = eo5(prog(t,0,total))
    img = glow_text(img, PAGE_NAME, font(88,True),
                    cx(d,PAGE_NAME,font(88,True)), H//2-220, C_TEXT, C_CYAN)
    d = ImageDraw.Draw(img)
    d.text((cx(d,PAGE_HANDLE,font(38)),H//2-110), PAGE_HANDLE, font=font(38), fill=C_MUTED)

    for i,line in enumerate(["Follow for daily","Stock Market Updates"]):
        cf = font(48,True if i==1 else False)
        d.text((cx(d,line,cf),H//2+20+i*68), line, font=cf, fill=C_TEXT)

    bw,bh = 400,84; bx=W//2-bw//2; by=H//2+200
    d.rounded_rectangle([bx,by,bx+bw,by+bh], radius=42, fill=C_VIOLET)
    d.text((bx+(bw-tw(d,"FOLLOW NOW",font(40,True)))//2,by+22),
           "FOLLOW NOW", font=font(40,True), fill=C_TEXT)

    hud_footer(d, img)
    return np.array(img)


def f_market_pulse(t, nifty, gainers, losers, chart_img, total=9.0):
    """Market Pulse fallback — Nifty chart + top movers."""
    img = base_canvas(t, tint=C_CYAN if nifty["change"]>=0 else C_RED)
    img = hud_grid(img, t, alpha=24)
    d   = ImageDraw.Draw(img)

    up  = nifty["change"]>=0
    acc = C_GREEN if up else C_RED
    arr = "▲" if up else "▼"
    reveal = eio(prog(t,0,total*0.65))

    # Header
    d.rounded_rectangle([46,42,W-46,210], radius=26, fill=C_PANEL)
    d.rectangle([46,42,W-46,50], fill=C_CYAN)
    img = glow_text(img,"MARKET PULSE",font(52,True),
                    cx(d,"MARKET PULSE",font(52,True)),68,C_TEXT,C_CYAN)
    d = ImageDraw.Draw(img)

    # Nifty bar
    nb  = f"NIFTY 50   {nifty['current']:,.0f}   {arr}{abs(nifty['change']):.2f}%"
    nf2 = font(38,True)
    nw  = min(tw(d,nb,nf2)+60,W-110)
    d.rounded_rectangle([W//2-nw//2,140,W//2+nw//2,196], radius=22, fill=acc)
    d.text((W//2-tw(d,nb,nf2)//2,146), nb, font=nf2, fill=(8,10,24))

    # Chart
    chart_y=210; cw,ch=W-80,480
    ci = chart_img.resize((cw,ch),Image.LANCZOS)
    rw = max(4,int(cw*reveal))
    d.rounded_rectangle([40,chart_y-8,W-40,chart_y+ch+8], radius=22, fill=(11,12,30))
    img.paste(ci.crop((0,0,rw,ch)), (40,chart_y))
    d = ImageDraw.Draw(img)

    # Gainers + Losers
    sec_y = chart_y+ch+20
    avail = H-sec_y-160

    if reveal>0.45:
        re2 = eo3(prog(reveal,0.45,1.0))
        d.text((80,sec_y), "TOP GAINERS", font=font(32,True), fill=C_GREEN)
        d.text((W//2+20,sec_y), "TOP LOSERS", font=font(32,True), fill=C_RED)
        d.rectangle([W//2-1,sec_y,W//2+1,H-160], fill=(*C_MUTED,60))

        n_rows = min(len(gainers),len(losers),3)
        row_h  = min((avail-52)//max(n_rows,1), 190)
        for i in range(n_rows):
            g=gainers[i]; l=losers[i]
            ry=int(sec_y+52+i*row_h+25*(1-re2))
            half=W//2-16

            # Gainer
            d.rounded_rectangle([60,ry,half,ry+row_h-10], radius=16, fill=C_PANEL)
            d.rounded_rectangle([60,ry,half,ry+7], radius=16, fill=C_GREEN)
            d.text((80,ry+16), g["name"][:13], font=font(32,True), fill=C_TEXT)
            d.text((80,ry+58), f"Rs{g['price']:,.1f}", font=font(26), fill=C_MUTED)
            d.text((80,ry+92), f"▲ {g['change']:.2f}%", font=font(34,True), fill=C_GREEN)

            # Loser
            lx=W//2+16
            d.rounded_rectangle([lx,ry,W-60,ry+row_h-10], radius=16, fill=C_PANEL)
            d.rounded_rectangle([lx,ry,W-60,ry+7], radius=16, fill=C_RED)
            d.text((lx+20,ry+16), l["name"][:13], font=font(32,True), fill=C_TEXT)
            d.text((lx+20,ry+58), f"Rs{l['price']:,.1f}", font=font(26), fill=C_MUTED)
            d.text((lx+20,ry+92), f"▼ {abs(l['change']):.2f}%", font=font(34,True), fill=C_RED)

    hud_footer(d, img)
    return np.array(img)

# ── Main ───────────────────────────────────────────────────────
def create_reel(article, output_path):
    title = re.sub(r"[^\x00-\x7F]+","",article["title"]).strip()
    print(f"  Creating reel: {title[:65]}")

    ticker = detect_ticker(title)
    sd     = fetch_stock(ticker) if ticker else None
    is_stock = sd is not None

    if not is_stock:
        print("  Market Pulse mode")

    def clip(fn, dur, **kw):
        return VideoClip(lambda t: fn(t,**kw).astype(np.uint8),
                         duration=dur).with_fps(FPS)

    if is_stock:
        print(f"  {sd['name']} | Rs{sd['current']:,.2f} | {sd['change']:+.2f}%")
        chart_img = make_stock_chart(sd["history"], sd["change"])
        question  = hook_question(title)
        clips = [
            clip(f_hook,     2.0, question=question),
            clip(f_stock,    3.0, sd=sd),
            clip(f_chart,    8.0, sd=sd, chart_img=chart_img),
            clip(f_headline, 5.0, headline=title),
            clip(f_outro,    2.0),
        ]
    else:
        nifty = fetch_nifty() or dict(name="NIFTY 50",current=24500.0,
                                       change=0.5,history=[24000+i*25 for i in range(30)])
        chart_img = make_nifty_chart(nifty["history"], nifty["change"])
        gainers, losers = fetch_top_movers()
        clips = [
            clip(f_hook,         2.0, question="What moved the\nmarket today?"),
            clip(f_market_pulse, 9.0, nifty=nifty, gainers=gainers,
                 losers=losers, chart_img=chart_img),
            clip(f_headline,     5.0, headline=title),
            clip(f_outro,        2.0),
        ]

    video = concatenate_videoclips(clips)

    # Music
    mfiles = [f for f in os.listdir(MUSIC_DIR)
              if f.endswith((".mp3",".wav"))] if os.path.exists(MUSIC_DIR) else []
    if mfiles:
        try:
            audio = AudioFileClip(os.path.join(MUSIC_DIR, random.choice(mfiles)))
            dur   = sum(c.duration for c in clips)
            audio = audio.subclipped(0, min(dur, audio.duration))
            video = video.with_audio(audio)
            print("  Music added")
        except Exception as e:
            print(f"  [!] Music: {e}")

    print("  Writing video...")
    video.write_videofile(output_path, fps=FPS, codec="libx264",
                          audio_codec="aac", temp_audiofile="temp_reel.m4a",
                          remove_temp=True, logger=None,
                          preset="medium", ffmpeg_params=["-crf","28"])
    print(f"  [✓] Saved -> {output_path}")
