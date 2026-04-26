"""
Investment Reel — StockDev.in
Premium cinematic design. Concept: Rs 1 Lakh growth story.

Timeline:
  0-3s  : Dramatic intro — stock name reveal with cinematic zoom
  3-14s : Premium chart animation with smooth line draw
  14-19s: Result reveal — big number impact moment
  19-21s: Outro
"""

import os, re, random, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from moviepy import VideoClip, AudioFileClip, concatenate_videoclips
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from io import BytesIO
from datetime import datetime, timedelta
from config import PAGE_NAME, PAGE_HANDLE

W, H, FPS = 1080, 1920, 30
MUSIC_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music")

# ── Premium palette — deep space + gold ───────────────────────
C_BG1    = ( 4,   4,  12)   # near black
C_BG2    = ( 8,  10,  28)   # deep navy
C_BG3    = (12,  16,  44)   # card bg
C_GOLD   = (212, 175,  55)   # real gold
C_GOLD2  = (255, 215,   0)   # bright gold
C_WHITE  = (240, 240, 255)   # warm white
C_MUTED  = ( 90, 100, 130)   # muted blue-grey
C_GREEN  = ( 0,  230, 118)   # vivid green
C_RED    = (255,  60,  80)   # vivid red
C_ACCENT = ( 99, 102, 241)   # indigo accent
C_GLOW_G = ( 0,  255, 120)   # green glow
C_GLOW_R = (255,  50,  70)   # red glow

# ── Easing functions ───────────────────────────────────────────
def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def ease_out3(t):  t=clamp(t); return 1-(1-t)**3
def ease_out5(t):  t=clamp(t); return 1-(1-t)**5
def ease_in2(t):   t=clamp(t); return t*t
def ease_io(t):    t=clamp(t); return t*t*(3-2*t)
def spring(t, s=8, d=0.5):
    t=clamp(t)
    if t==0: return 0
    if t==1: return 1
    return 1 + (2.718**(-d*s*t)) * math.cos(s*t*1.5)
def progress(t, start, end):
    return clamp((t-start)/(end-start)) if end>start else float(t>=start)

def lerp(a, b, t): return a + (b-a)*clamp(t)
def lerp_col(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))

# ── Font helper ────────────────────────────────────────────────
def font(size, bold=False):
    for p in (["arialbd.ttf","Arial_Bold.ttf","DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
               if bold else
               ["arial.ttf","Arial.ttf","DejaVuSans.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]):
        try: return ImageFont.truetype(p, size)
        except: pass
    return ImageFont.load_default()

def tw(d, txt, f):
    b = d.textbbox((0,0), txt, font=f); return b[2]-b[0]
def th(d, txt, f):
    b = d.textbbox((0,0), txt, font=f); return b[3]-b[1]
def cx(d, txt, f, w=W): return (w - tw(d,txt,f))//2

# ── Canvas helpers ─────────────────────────────────────────────
def make_canvas():
    """Create base gradient canvas."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        t = y/H
        arr[y] = lerp_col(C_BG1, C_BG2, t)
    return Image.fromarray(arr)

def add_grid(img, alpha=18):
    """Subtle grid lines for depth."""
    d = ImageDraw.Draw(img)
    for x in range(0, W, 90):
        d.line([(x,0),(x,H)], fill=(*C_BG3, alpha), width=1)
    for y in range(0, H, 90):
        d.line([(0,y),(W,y)], fill=(*C_BG3, alpha), width=1)
    return img

def glow_ellipse(img, cx_, cy_, rx, ry, color, layers=6):
    """Draw a soft glowing ellipse."""
    for i in range(layers, 0, -1):
        r_  = int(rx + (layers-i)*18)
        ry_ = int(ry + (layers-i)*18)
        a   = int(255 * (i/layers) * 0.12)
        ov  = Image.new("RGBA", img.size, (0,0,0,0))
        od  = ImageDraw.Draw(ov)
        od.ellipse([cx_-r_, cy_-ry_, cx_+r_, cy_+ry_], fill=(*color, a))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    return img

def draw_glow_text(d, img, txt, f, x, y, color, glow_color, glow_r=4):
    """Text with soft glow."""
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    od = ImageDraw.Draw(ov)
    for r in range(glow_r, 0, -1):
        a = int(80 * r / glow_r)
        for dx in range(-r, r+1, max(1,r//2)):
            for dy in range(-r, r+1, max(1,r//2)):
                od.text((x+dx, y+dy), txt, font=f, fill=(*glow_color, a))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d2  = ImageDraw.Draw(img)
    d2.text((x, y), txt, font=f, fill=color)
    return img, d2

def fmt_money(v):
    if v >= 1e7:  return f"₹{v/1e7:.2f} Cr"
    if v >= 1e5:  return f"₹{v/1e5:.2f} L"
    return f"₹{v:,.0f}"

def fmt_money_ascii(v):
    if v >= 1e7:  return f"Rs {v/1e7:.2f} Cr"
    if v >= 1e5:  return f"Rs {v/1e5:.2f} L"
    return f"Rs {v:,.0f}"

# ── Data ───────────────────────────────────────────────────────
def fetch_data(ticker, years=10):
    for sym in [ticker, ticker.replace(".NS",".BO")]:
        try:
            hist = yf.Ticker(sym).history(period="max")
            if hist.empty or len(hist) < 100: continue
            cutoff = datetime.now() - timedelta(days=years*365)
            h2 = hist[hist.index >= cutoff.strftime("%Y-%m-%d")]
            if len(h2) < 50: h2 = hist
            if h2.empty: continue
            sp  = h2["Close"].iloc[0]
            inv = 100000
            vals = [(d, (r["Close"]/sp)*inv) for d,r in h2.iterrows()]
            sd, ed = h2.index[0], h2.index[-1]
            ev = vals[-1][1]
            cagr = ((ev/inv)**(1/max((ed-sd).days/365,1))-1)*100
            return dict(sym=sym, vals=vals, sp=sp, ep=h2["Close"].iloc[-1],
                        sd=sd, ed=ed, inv=inv, ev=ev, cagr=cagr,
                        yrs=(ed-sd).days/365)
        except Exception as e:
            print(f"  [!] {sym}: {e}")
    return None

def milestones(inv, ev):
    return [m for m in [2,3,5,10,20,50] if ev >= inv*m]


# ── Premium chart ──────────────────────────────────────────────
def make_chart(data, reveal=1.0, w=1000, h=580):
    vals   = data["vals"]
    n      = max(2, int(len(vals)*reveal))
    shown  = vals[:n]
    dates  = [v[0] for v in shown]
    prices = [v[1] for v in shown]
    all_d  = [v[0] for v in vals]
    all_p  = [v[1] for v in vals]
    inv    = data["inv"]
    is_up  = data["ev"] >= inv
    lc     = "#00E676" if is_up else "#FF3D57"   # line color
    gc     = "#00FF88" if is_up else "#FF2040"   # glow color
    fc     = "#003320" if is_up else "#330010"   # fill color

    fig, ax = plt.subplots(figsize=(w/100, h/100), dpi=100)
    fig.patch.set_facecolor("#04040C")
    ax.set_facecolor("#06060F")

    ax.set_xlim(all_d[0], all_d[-1])
    ymin = min(all_p)*0.88
    ymax = max(all_p)*1.10
    ax.set_ylim(ymin, ymax)

    if len(dates) > 1:
        # Glow layers
        for lw, a in [(14,0.04),(9,0.10),(5,0.25),(2.5,1.0)]:
            ax.plot(dates, prices, color=lc, linewidth=lw,
                    alpha=a, solid_capstyle="round", zorder=4)
        # Fill
        ax.fill_between(dates, prices, ymin, color=fc, alpha=0.6, zorder=2)
        # Gradient fill using alpha
        ax.fill_between(dates, prices, ymin, color=lc, alpha=0.08, zorder=3)

    # Reference line
    ax.axhline(y=inv, color="#FFFFFF", lw=1.2, ls="--", alpha=0.2, zorder=1)

    # Milestone horizontal lines
    ms = milestones(inv, data["ev"])
    for m in ms:
        target = inv*m
        for i,(d,v) in enumerate(vals):
            if v >= target and i < n:
                ax.axhline(y=target, color=gc, lw=0.6, ls=":", alpha=0.35)
                break

    # Glowing tip dot
    if len(dates) > 1:
        for s,a in [(200,0.06),(100,0.15),(40,0.4),(12,1.0)]:
            ax.scatter([dates[-1]], [prices[-1]], color=gc, s=s, alpha=a, zorder=6)

    # Style
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#1A1A3A"); ax.spines["bottom"].set_color("#1A1A3A")
    ax.tick_params(colors="#404060", labelsize=8, length=0)
    ax.set_facecolor("#06060F")

    def fv(v,_):
        if v>=1e7: return f"₹{v/1e7:.0f}Cr"
        if v>=1e5: return f"₹{v/1e5:.0f}L"
        return f"₹{v:,.0f}"
    ax.yaxis.set_major_formatter(plt.FuncFormatter(fv))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
    ax.grid(axis="y", color="#0C0C20", lw=0.8, zorder=0)

    plt.tight_layout(pad=0.1)
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor="#04040C",
                dpi=100)
    plt.close(fig); buf.seek(0)
    return Image.open(buf).convert("RGB")

# ── Section frames ─────────────────────────────────────────────

def frame_intro(t, name, years, total=3.0):
    """
    0-3s: Cinematic zoom-in reveal.
    - Background: deep space with grid
    - Stock name zooms in from small → large with glow
    - Gold horizontal lines sweep across
    - Subtle vignette
    """
    img = make_canvas()
    img = add_grid(img, alpha=12)

    # Vignette
    vig = Image.new("RGBA", img.size, (0,0,0,0))
    vd  = ImageDraw.Draw(vig)
    for r in range(20, 0, -1):
        a = int(180 * (1 - r/20)**2)
        vd.ellipse([W//2-r*60, H//2-r*100, W//2+r*60, H//2+r*100],
                   fill=(0,0,0,0))
    # Simple corner vignette
    for corner_r in range(1, 8):
        a = int(30 * corner_r / 8)
        vd.rectangle([0,0,W,corner_r*30], fill=(0,0,0,a))
        vd.rectangle([0,H-corner_r*30,W,H], fill=(0,0,0,a))

    img = Image.alpha_composite(img.convert("RGBA"), vig).convert("RGB")
    d   = ImageDraw.Draw(img)

    # Gold sweep lines (horizontal bars that slide in)
    p_lines = progress(t, 0.0, 0.6)
    for i in range(3):
        lw_  = 2 if i == 1 else 1
        ly   = H//2 - 320 + i*320
        lx   = int(W * ease_out3(p_lines))
        a    = int(180 * ease_out3(p_lines))
        d.rectangle([0, ly, lx, ly+lw_], fill=(*C_GOLD, a))

    # Central glow
    p_glow = progress(t, 0.1, 0.8)
    img = glow_ellipse(img, W//2, H//2-60, int(300*ease_out3(p_glow)),
                       int(200*ease_out3(p_glow)), C_GOLD, layers=8)
    d = ImageDraw.Draw(img)

    # "WHAT IF YOU HAD" — slides up
    p_q = progress(t, 0.2, 0.9)
    eq  = ease_out3(p_q)
    qf  = font(44)
    q1  = "WHAT IF YOU HAD"
    q1y = int(H//2 - 280 + 40*(1-eq))
    d.text((cx(d,q1,qf), q1y), q1, font=qf, fill=(*C_MUTED, int(255*eq)))

    # "INVESTED Rs 1 LAKH" — zooms in
    p_inv = progress(t, 0.3, 1.0)
    ei    = ease_out5(p_inv)
    inv_size = int(lerp(30, 72, ei))
    invf  = font(inv_size, bold=True)
    inv_t = "INVESTED Rs 1 LAKH"
    inv_y = int(H//2 - 180 + 30*(1-ei))
    d.text((cx(d,inv_t,invf), inv_y), inv_t, font=invf,
           fill=(*C_GOLD, int(255*ei)))

    # Stock name — big zoom
    p_name = progress(t, 0.5, 1.2)
    en     = ease_out5(clamp(p_name))
    ns     = int(lerp(40, 110, en))
    nf_    = font(ns, bold=True)
    name_y = int(H//2 - 40 + 50*(1-en))
    # Glow behind name
    if en > 0.3:
        img = glow_ellipse(img, W//2, name_y+ns//2,
                           int(tw(d,name,nf_)//2 + 60),
                           int(ns//2 + 30),
                           C_GOLD, layers=5)
        d = ImageDraw.Draw(img)
    d.text((cx(d,name,nf_), name_y), name, font=nf_,
           fill=(*C_WHITE, int(255*en)))

    # "X YEARS AGO" — fades in
    p_yr = progress(t, 0.8, 1.5)
    yr_s = f"{int(years)} YEARS AGO" if years >= 1 else f"{int(years*12)} MONTHS AGO"
    yrf  = font(40)
    yr_y = int(H//2 + 100 + 20*(1-ease_out3(p_yr)))
    d.text((cx(d,yr_s,yrf), yr_y), yr_s, font=yrf,
           fill=(*C_MUTED, int(255*ease_out3(p_yr))))

    # Brand bottom
    bf = font(32, bold=True)
    d.text((cx(d,PAGE_NAME,bf), H-100), PAGE_NAME, font=bf, fill=C_GOLD)
    d.rectangle([0, H-4, W, H], fill=C_GOLD)

    return np.array(img)


def frame_chart(t, data, cache, total=11.0):
    """
    3-14s: Premium chart section.
    - Chart draws smoothly
    - Zoom effect: starts slightly zoomed in, pulls back
    - Milestone badges pop with spring animation
    - Value counter at bottom
    """
    reveal  = ease_io(progress(t, 0, total*0.88))
    is_up   = data["ev"] >= data["inv"]
    col     = C_GREEN if is_up else C_RED
    glow_c  = C_GLOW_G if is_up else C_GLOW_R

    # Background tints slightly toward green/red as chart fills
    tint = reveal * 0.08
    bg1  = lerp_col(C_BG1, glow_c, tint)
    bg2  = lerp_col(C_BG2, glow_c, tint*0.4)
    arr  = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        arr[y] = lerp_col(bg1, bg2, y/H)
    img = Image.fromarray(arr)
    img = add_grid(img, alpha=10)
    d   = ImageDraw.Draw(img)

    # Header — stock name
    name = data.get("dn", data["sym"].replace(".NS",""))
    nf_  = font(56, bold=True)
    d.text((cx(d,name,nf_)+2, 57), name, font=nf_, fill=(0,0,0))
    d.text((cx(d,name,nf_), 55), name, font=nf_, fill=C_WHITE)

    sub = f"{data['sd'].year}  →  {data['ed'].year}   |   Rs 1 Lakh Journey"
    sf  = font(28)
    d.text((cx(d,sub,sf), 126), sub, font=sf, fill=C_MUTED)

    # Gold divider
    d.rectangle([80, 168, W-80, 170], fill=(*C_GOLD, 80))

    # Chart with zoom effect
    key = int(reveal * 60)
    if key not in cache:
        cache[key] = make_chart(data, reveal=reveal)

    chart_img = cache[key]
    cw, ch    = 1000, 580
    chart_img = chart_img.resize((cw, ch), Image.LANCZOS)

    # Zoom: starts at 1.08x, eases to 1.0x
    zoom   = lerp(1.08, 1.0, ease_out3(progress(t, 0, 3.0)))
    zw     = int(cw * zoom)
    zh     = int(ch * zoom)
    zoomed = chart_img.resize((zw, zh), Image.LANCZOS)
    cx_    = (zw - cw) // 2
    cy_    = (zh - ch) // 2
    chart_crop = zoomed.crop((cx_, cy_, cx_+cw, cy_+ch))
    img.paste(chart_crop, ((W-cw)//2, 185))

    chart_bot = 185 + ch  # 765

    # Milestone badges — spring pop
    ms_list = milestones(data["inv"], data["ev"])
    vals    = data["vals"]
    badge_y = chart_bot + 18
    shown   = []
    for m in ms_list:
        target = data["inv"] * m
        for i,(dd,v) in enumerate(vals):
            if v >= target:
                frac = i/len(vals)
                if frac <= reveal:
                    shown.append(m)
                break

    if shown:
        bw = (W-80) // max(len(shown), 1)
        for i, m in enumerate(shown[-5:]):
            # Spring pop timing — each badge pops slightly after previous
            pop_start = 0.05 * i
            pop_p     = progress(reveal, pop_start, pop_start+0.15)
            sp_e      = clamp(spring(pop_p))
            bx        = 40 + i*bw
            bh_       = int(72 * sp_e)
            if bh_ < 4: continue
            # Badge background
            d.rounded_rectangle([bx+4, badge_y, bx+bw-4, badge_y+bh_],
                                  radius=12, fill=C_BG3)
            d.rounded_rectangle([bx+4, badge_y, bx+bw-4, badge_y+4],
                                  radius=12, fill=col)
            lbl = f"{m}x"
            lf_ = font(int(34*sp_e), bold=True)
            if bh_ > 30:
                d.text((bx+4+cx(d,lbl,lf_,bw-8), badge_y+int(18*sp_e)),
                       lbl, font=lf_, fill=col)

    # Value counter — accelerates
    accel   = reveal**0.35
    cur_val = data["inv"] + (data["ev"]-data["inv"]) * accel
    val_str = fmt_money_ascii(cur_val)
    vf_     = font(92, bold=True)
    val_y   = badge_y + 90
    # Glow
    for r in [8, 5, 2]:
        d.text((cx(d,val_str,vf_), val_y), val_str, font=vf_,
               fill=(*col, 25//r))
    d.text((cx(d,val_str,vf_), val_y), val_str, font=vf_, fill=col)

    # Stats
    stats = [f"CAGR  {data['cagr']:.1f}%",
             f"Return  {(data['ev']/data['inv']-1)*100:.0f}%",
             f"Years  {data['yrs']:.1f}"]
    row_y = val_y + 110
    bw3   = (W-80)//3
    for i, stat in enumerate(stats):
        bx = 40 + i*bw3
        d.rounded_rectangle([bx+4, row_y, bx+bw3-4, row_y+76],
                              radius=12, fill=C_BG3)
        sf2 = font(28, bold=True)
        d.text((bx+4+cx(d,stat,sf2,bw3-8), row_y+22),
               stat, font=sf2, fill=C_GOLD)

    # Brand
    bf = font(30, bold=True)
    d.text((cx(d,PAGE_NAME,bf), H-80), PAGE_NAME, font=bf, fill=C_GOLD)
    d.rectangle([0, H-4, W, H], fill=C_GOLD)
    return np.array(img)


def frame_result(t, data, total=5.0):
    """
    14-19s: The big reveal moment.
    - Card slides up with spring
    - Number counts up fast then slams to final
    - Confetti-like particles burst
    """
    is_up = data["ev"] >= data["inv"]
    col   = C_GREEN if is_up else C_RED
    gc    = C_GLOW_G if is_up else C_GLOW_R

    img = make_canvas()
    img = add_grid(img, alpha=8)

    # Burst glow
    p_glow = progress(t, 0.0, 0.8)
    eg     = ease_out5(p_glow)
    img    = glow_ellipse(img, W//2, H//2-50,
                          int(500*eg), int(400*eg), gc, layers=10)
    d = ImageDraw.Draw(img)

    # Particle burst
    rng = random.Random(42)
    p_burst = progress(t, 0.1, 1.5)
    for _ in range(60):
        angle = rng.uniform(0, 2*math.pi)
        dist  = rng.uniform(100, 500) * ease_out3(p_burst)
        size  = rng.randint(2, 6)
        px    = int(W//2 + math.cos(angle)*dist)
        py    = int(H//2 - 50 + math.sin(angle)*dist*0.7)
        a     = int(200 * (1 - ease_in2(p_burst)))
        pc    = C_GOLD if rng.random() > 0.4 else col
        d.ellipse([px-size, py-size, px+size, py+size], fill=(*pc, a))

    # Card — spring slide up
    p_card = progress(t, 0.0, 0.7)
    ec     = spring(p_card)
    card_y = int(lerp(H, H//2-420, clamp(ec)))
    card_h = 820
    d.rounded_rectangle([50, card_y, W-50, card_y+card_h],
                         radius=32, fill=C_BG3)
    # Top accent bar
    d.rounded_rectangle([50, card_y, W-50, card_y+8], radius=32, fill=col)
    # Subtle inner glow on card top
    for r in range(4, 0, -1):
        a = int(30 * r/4)
        d.rounded_rectangle([50, card_y, W-50, card_y+r*20],
                              radius=32, fill=(*col, a))

    # Stock name
    name = data.get("dn", data["sym"].replace(".NS",""))
    nf_  = font(58, bold=True)
    d.text((cx(d,name,nf_), card_y+28), name, font=nf_, fill=C_WHITE)

    # "Rs 1 Lakh Invested"
    d.text((cx(d,"Rs 1 Lakh Invested",font(44,True)), card_y+108),
           "Rs 1 Lakh Invested", font=font(44,True), fill=C_MUTED)

    # Animated arrow
    p_arr = progress(t, 0.4, 0.8)
    if p_arr > 0:
        af = font(int(lerp(20,88,ease_out3(p_arr))), bold=True)
        d.text((cx(d,"↓",af), card_y+188), "↓", font=af, fill=col)

    # Final value — slams in
    p_val = progress(t, 0.6, 1.1)
    if p_val > 0:
        ev_  = spring(p_val)
        vs   = int(lerp(40, 104, clamp(ev_)))
        vf_  = font(vs, bold=True)
        val  = fmt_money_ascii(data["ev"])
        vy   = card_y + 295
        for r in [10, 6, 3]:
            d.text((cx(d,val,vf_), vy), val, font=vf_, fill=(*col, 25//r))
        d.text((cx(d,val,vf_), vy), val, font=vf_, fill=col)

    # Stats grid
    p_stats = progress(t, 1.0, 1.6)
    if p_stats > 0:
        es = ease_out3(p_stats)
        stats = [("Invested","Rs 1 Lakh"),
                 ("Years",   f"{data['yrs']:.1f}"),
                 ("CAGR",    f"{data['cagr']:.1f}%"),
                 ("Return",  f"{(data['ev']/data['inv']-1)*100:.0f}%")]
        bw4 = (W-120)//4
        for i,(lbl,val) in enumerate(stats):
            bx = 60 + i*bw4
            by = int(card_y+440 + 30*(1-es))
            d.rounded_rectangle([bx+2, by, bx+bw4-2, by+120],
                                  radius=14, fill=(20,28,60))
            d.text((bx+2+cx(d,lbl,font(22,True),bw4-4), by+10),
                   lbl, font=font(22,True), fill=C_MUTED)
            d.text((bx+2+cx(d,val,font(36,True),bw4-4), by+48),
                   val, font=font(36,True), fill=C_WHITE)

    # Period
    period = f"{data['sd'].strftime('%b %Y')} — {data['ed'].strftime('%b %Y')}"
    d.text((cx(d,period,font(26)), card_y+590),
           period, font=font(26), fill=C_MUTED)
    d.text((cx(d,"Past performance ≠ future returns",font(20)),
            card_y+640),
           "Past performance ≠ future returns",
           font=font(20), fill=(*C_MUTED, 140))

    d.rectangle([0, H-4, W, H], fill=C_GOLD)
    return np.array(img)


def frame_outro(t, total=2.0):
    """19-21s: Clean cinematic outro."""
    img = make_canvas()
    img = add_grid(img, alpha=8)
    img = glow_ellipse(img, W//2, H//2-80, 320, 260, C_GOLD, layers=8)
    d   = ImageDraw.Draw(img)

    # Gold lines sweep
    p_l = progress(t, 0.0, 0.5)
    for i, ly in enumerate([H//2-280, H//2+200]):
        lx = int(W * ease_out3(p_l))
        d.rectangle([0, ly, lx, ly+2], fill=(*C_GOLD, 160))

    # Brand name zoom
    p_b = progress(t, 0.1, 0.8)
    eb  = ease_out5(p_b)
    bs  = int(lerp(30, 100, eb))
    bf  = font(bs, bold=True)
    bw_ = tw(d, PAGE_NAME, bf)
    d.text((W//2-bw_//2, H//2-200), PAGE_NAME, font=bf, fill=C_GOLD)

    # Handle
    p_h = progress(t, 0.4, 1.0)
    hf  = font(int(lerp(20,38,ease_out3(p_h))))
    d.text((cx(d,PAGE_HANDLE,hf), H//2-80),
           PAGE_HANDLE, font=hf, fill=C_MUTED)

    # CTA lines
    p_c = progress(t, 0.6, 1.2)
    for i, line in enumerate(["Follow for daily stock","investment insights!"]):
        cf = font(int(lerp(20,46,ease_out3(p_c))))
        d.text((cx(d,line,cf), H//2+20+i*64), line, font=cf, fill=C_WHITE)

    # Subscribe button
    p_s = progress(t, 1.0, 1.6)
    if p_s > 0:
        se  = spring(p_s)
        bw_, bh_ = 360, 76
        bx  = W//2-bw_//2
        by  = H//2+200
        d.rounded_rectangle([bx, by, bx+bw_, by+bh_], radius=38, fill=C_RED)
        sf_ = font(int(lerp(20,40,clamp(se))), bold=True)
        d.text((bx+(bw_-tw(d,"SUBSCRIBE",sf_))//2, by+(bh_-th(d,"SUBSCRIBE",sf_))//2),
               "SUBSCRIBE", font=sf_, fill=C_WHITE)

    d.rectangle([0, H-4, W, H], fill=C_GOLD)
    return np.array(img)

# ── Thumbnail ──────────────────────────────────────────────────
def create_thumbnail(data, path):
    img = make_canvas()
    img = add_grid(img, alpha=10)
    is_up = data["ev"] >= data["inv"]
    col   = C_GREEN if is_up else C_RED
    gc    = C_GLOW_G if is_up else C_GLOW_R
    img   = glow_ellipse(img, W//2, H//2-80, 420, 320, gc, layers=10)
    d     = ImageDraw.Draw(img)

    name = data.get("dn", data["sym"].replace(".NS",""))

    # Top label
    d.text((cx(d,"Rs 1 LAKH INVESTED IN",font(48,True)), 160),
           "Rs 1 LAKH INVESTED IN", font=font(48,True), fill=C_MUTED)

    # Stock name — big
    nf_ = font(96, bold=True)
    d.text((cx(d,name,nf_)+2, 232), name, font=nf_, fill=(0,0,0))
    d.text((cx(d,name,nf_), 230), name, font=nf_, fill=C_WHITE)

    # Arrow
    d.text((cx(d,"↓",font(100,True)), 360), "↓", font=font(100,True), fill=col)

    # Final value — massive
    val = fmt_money_ascii(data["ev"])
    vf_ = font(128, bold=True)
    for r in [12, 7, 3]:
        d.text((cx(d,val,vf_), 460), val, font=vf_, fill=(*col, 25//r))
    d.text((cx(d,val,vf_), 460), val, font=vf_, fill=col)

    # Years + CAGR
    yr_s = f"In {data['yrs']:.0f} Years  |  CAGR {data['cagr']:.1f}%"
    d.text((cx(d,yr_s,font(42)), 620), yr_s, font=font(42), fill=C_GOLD)

    # Brand bar
    d.rounded_rectangle([40, H-170, W-40, H-50], radius=24, fill=C_BG3)
    d.rounded_rectangle([40, H-170, W-40, H-164], radius=24, fill=C_GOLD)
    d.text((cx(d,PAGE_NAME,font(56,True)), H-152),
           PAGE_NAME, font=font(56,True), fill=C_GOLD)
    d.text((cx(d,PAGE_HANDLE,font(34)), H-88),
           PAGE_HANDLE, font=font(34), fill=C_MUTED)

    img.save(path, quality=95)
    print(f"  [✓] Thumbnail -> {path}")


# ── Main ───────────────────────────────────────────────────────
def create_investment_reel(display_name, ticker, output_path):
    print(f"  Stock: {display_name} ({ticker})")
    print("  Fetching data...")
    data = fetch_data(ticker)
    if not data:
        print(f"  [!] No data for {ticker}")
        return False

    data["dn"] = display_name
    print(f"  {data['sd'].date()} → {data['ed'].date()} | "
          f"{fmt_money_ascii(data['ev'])} | CAGR {data['cagr']:.1f}%")

    # Thumbnail
    thumb = output_path.replace(".mp4", "_thumbnail.jpg")
    create_thumbnail(data, thumb)

    cache = {}

    def clip(fn, dur, **kw):
        return VideoClip(lambda t: fn(t, **kw).astype(np.uint8),
                         duration=dur).with_fps(FPS)

    print("  Rendering...")
    clips = [
        clip(frame_intro,  3.0,  name=display_name, years=data["yrs"]),
        clip(frame_chart,  11.0, data=data, cache=cache),
        clip(frame_result, 5.0,  data=data),
        clip(frame_outro,  2.0),
    ]
    video = concatenate_videoclips(clips)

    # Music — prefer cinematic
    mfiles = sorted(
        [f for f in os.listdir(MUSIC_DIR) if f.endswith((".mp3",".wav"))],
        key=lambda x: "cinematic" in x.lower(), reverse=True
    ) if os.path.exists(MUSIC_DIR) else []
    print(f"  Music: {mfiles}")
    if mfiles:
        try:
            audio = AudioFileClip(os.path.join(MUSIC_DIR, mfiles[0]))
            dur   = sum(c.duration for c in clips)
            audio = audio.subclipped(0, min(dur, audio.duration))
            video = video.with_audio(audio)
            print("  [✓] Music embedded")
        except Exception as e:
            print(f"  [!] Music error: {e}")

    print("  Writing video...")
    video.write_videofile(output_path, fps=FPS, codec="libx264",
                          audio_codec="aac", temp_audiofile="temp_inv.m4a",
                          remove_temp=True, logger=None, preset="ultrafast")
    print(f"  [✓] Done -> {output_path}")
    return True
