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
    ax.tick_params(colors="#C0C8E0", labelsize=10, length=0)  # bright tick labels
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
    """0-3s: Clean aesthetic intro — readable, elegant."""
    img = make_canvas()
    d   = ImageDraw.Draw(img)

    # Subtle center glow
    for r in range(5, 0, -1):
        radius = 180 + r*55
        a      = int(14*r/5)
        ov     = Image.new("RGBA", img.size, (0,0,0,0))
        od     = ImageDraw.Draw(ov)
        od.ellipse([W//2-radius, H//2-radius-80,
                    W//2+radius, H//2+radius-80], fill=(20,40,100,a))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        d   = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 3], fill=C_GOLD)
    d.rectangle([0, H-3, W, H], fill=C_GOLD)

    # "IF YOU HAD INVESTED" — bright white, not muted
    p1  = ease_out3(progress(t, 0.0, 0.7))
    tf  = font(42)
    t1  = "IF YOU HAD INVESTED"
    t1y = int(H//2 - 310 + 30*(1-p1))
    d.text((cx(d,t1,tf), t1y), t1, font=tf,
           fill=(*C_WHITE, int(230*p1)))

    # "Rs 1 LAKH" — gold, bold
    p2  = ease_out3(progress(t, 0.15, 0.85))
    rf  = font(80, bold=True)
    r1  = "Rs 1 LAKH"
    r1y = int(H//2 - 210 + 25*(1-p2))
    d.text((cx(d,r1,rf), r1y), r1, font=rf,
           fill=(*C_GOLD, int(255*p2)))

    # Divider
    p3  = ease_out3(progress(t, 0.3, 0.9))
    dw  = int((W-160)*p3)
    d.rectangle([W//2-dw//2, H//2-105, W//2+dw//2, H//2-103],
                fill=(*C_GOLD, 160))

    # Stock name — white, large
    p4  = ease_out5(progress(t, 0.4, 1.1))
    for ns in [104, 88, 74, 62, 52]:
        nf_ = font(ns, bold=True)
        if tw(d, name, nf_) <= W-80: break
    ny  = int(H//2 - 65 + 40*(1-p4))
    d.text((cx(d,name,nf_), ny), name, font=nf_,
           fill=(*C_WHITE, int(255*p4)))

    # "X Years Ago → Today" — highlight the number in gold
    p5   = ease_out3(progress(t, 0.65, 1.3))
    yf_  = font(44)
    yf_b = font(44, bold=True)
    yr_n = str(int(years))
    yr_r = " Years Ago  →  Today"
    # Draw number in gold, rest in white
    yr_full = yr_n + yr_r
    yr_y    = int(H//2 + 80 + 20*(1-p5))
    total_w = tw(d, yr_full, yf_)
    start_x = (W - total_w) // 2
    d.text((start_x, yr_y), yr_n, font=yf_b,
           fill=(*C_GOLD, int(255*p5)))
    d.text((start_x + tw(d,yr_n,yf_b), yr_y), yr_r, font=yf_,
           fill=(*C_WHITE, int(230*p5)))

    # Brand
    p6 = ease_out3(progress(t, 0.9, 1.6))
    bf = font(34, bold=True)
    d.text((cx(d,PAGE_NAME,bf), H-90), PAGE_NAME, font=bf,
           fill=(*C_GOLD, int(255*p6)))

    return np.array(img)



def frame_chart(t, data, cache, total=11.0):
    """3-14s: Chart centered on screen, synced counter, full-screen milestone flash."""
    reveal  = ease_io(progress(t, 0, total*0.88))
    is_up   = data["ev"] >= data["inv"]
    col     = C_GREEN if is_up else C_RED
    glow_c  = C_GLOW_G if is_up else C_GLOW_R

    # Background tints
    tint = reveal * 0.07
    bg1  = lerp_col(C_BG1, glow_c, tint)
    bg2  = lerp_col(C_BG2, glow_c, tint*0.4)
    arr  = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        arr[y] = lerp_col(bg1, bg2, y/H)
    img = Image.fromarray(arr)
    d   = ImageDraw.Draw(img)

    # ── Header — compact at top ────────────────────────────────
    name = data.get("dn", data["sym"].replace(".NS",""))
    nf_  = font(50, bold=True)
    d.text((cx(d,name,nf_), 38), name, font=nf_, fill=C_WHITE)
    sub = f"{data['sd'].year}  →  {data['ed'].year}   |   Rs 1 Lakh Journey"
    d.text((cx(d,sub,font(26)), 100), sub, font=font(26), fill=C_WHITE)
    d.rectangle([80, 140, W-80, 142], fill=(*C_GOLD, 80))

    # ── Chart — CENTERED on screen ─────────────────────────────
    cw, ch  = 1020, 700   # taller chart
    chart_y = (H - ch) // 2 - 60  # vertically centered, slightly above middle

    key = int(reveal * 200)
    if key not in cache:
        cache[key] = make_chart(data, reveal=reveal, w=1020, h=700)

    chart_img = cache[key].resize((cw, ch), Image.LANCZOS)
    zoom   = lerp(1.06, 1.0, ease_out3(progress(t, 0, 3.0)))
    zw, zh = int(cw*zoom), int(ch*zoom)
    zoomed = chart_img.resize((zw, zh), Image.LANCZOS)
    ox, oy = (zw-cw)//2, (zh-ch)//2
    img.paste(zoomed.crop((ox, oy, ox+cw, oy+ch)), ((W-cw)//2, chart_y))

    chart_bot = chart_y + ch

    # ── Value counter — TRUE sync with chart ───────────────────
    # Find actual value at current reveal position in the data
    vals    = data["vals"]
    n_shown = max(1, int(len(vals) * reveal))
    cur_val = vals[n_shown-1][1]  # actual value at chart tip
    val_str = fmt_money_ascii(cur_val)
    vf_     = font(82, bold=True)
    val_y   = chart_bot + 20
    for r in [6, 3]:
        d.text((cx(d,val_str,vf_), val_y), val_str, font=vf_,
               fill=(*col, 20//r))
    d.text((cx(d,val_str,vf_), val_y), val_str, font=vf_, fill=col)

    # ── Milestone badges at bottom ─────────────────────────────
    ms_list = milestones(data["inv"], data["ev"])
    badge_y = val_y + 96
    shown   = []
    for m in ms_list:
        target = data["inv"] * m
        for i,(dd,v) in enumerate(vals):
            if v >= target:
                if i/len(vals) <= reveal:
                    shown.append((m, i/len(vals)))
                break

    if shown:
        bw = (W-80) // max(len(shown), 1)
        for idx, (m, frac) in enumerate(shown[-5:]):
            pop_p = progress(reveal, frac, frac+0.06)
            sp_e  = clamp(spring(pop_p, s=14, d=0.35))
            bx    = 40 + idx*bw
            bh_   = int(76 * sp_e)
            if bh_ < 6: continue
            d.rounded_rectangle([bx+6, badge_y, bx+bw-6, badge_y+bh_],
                                  radius=14, fill=C_BG3)
            d.rounded_rectangle([bx+6, badge_y, bx+bw-6, badge_y+5],
                                  radius=14, fill=col)
            lbl = f"{m}x"
            lf_ = font(int(36*min(sp_e,1.0)), bold=True)
            if bh_ > 32:
                d.text((bx+6+cx(d,lbl,lf_,bw-12), badge_y+int(18*min(sp_e,1.0))),
                       lbl, font=lf_, fill=col)

    # ── Full-screen milestone FLASH ────────────────────────────
    # When a new milestone is just crossed, flash the whole screen
    for m, frac in shown:
        flash_p = progress(reveal, frac, frac+0.04)
        if 0 < flash_p < 1:
            flash_e = 1 - flash_p  # fades out quickly
            # Full screen color flash
            ov = Image.new("RGBA", img.size, (0,0,0,0))
            od = ImageDraw.Draw(ov)
            od.rectangle([0,0,W,H], fill=(*col, int(120*flash_e)))
            img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
            d   = ImageDraw.Draw(img)
            # Big centered milestone text
            ms_txt = f"{m}x RETURN!"
            mf     = font(int(lerp(60,140,flash_e)), bold=True)
            d.text((cx(d,ms_txt,mf), H//2-80), ms_txt, font=mf,
                   fill=(*C_GOLD, int(255*flash_e)))
            # Particle burst from center
            rng2 = random.Random(m*77)
            for _ in range(30):
                angle = rng2.uniform(0, 2*math.pi)
                dist  = int(rng2.uniform(80, 400) * (1-flash_e))
                px    = W//2 + int(math.cos(angle)*dist)
                py    = H//2 + int(math.sin(angle)*dist*0.7)
                ps    = rng2.randint(4, 12)
                pc    = C_GOLD if rng2.random() > 0.4 else col
                a_p   = int(255*flash_e)
                ov2   = Image.new("RGBA", img.size, (0,0,0,0))
                od2   = ImageDraw.Draw(ov2)
                od2.ellipse([px-ps, py-ps, px+ps, py+ps], fill=(*pc, a_p))
                img = Image.alpha_composite(img.convert("RGBA"), ov2).convert("RGB")
                d   = ImageDraw.Draw(img)
            break  # only flash the most recent milestone

    # ── Final zoom transition ──────────────────────────────────
    # When chart is 98%+ done, zoom the final value to fill screen
    if reveal >= 0.96:
        zoom_p = ease_out5(progress(reveal, 0.96, 1.0))
        if zoom_p > 0:
            final_val = fmt_money_ascii(data["ev"])
            fvs = int(lerp(82, 160, zoom_p))
            fvf = font(fvs, bold=True)
            # Fade out everything else
            fade_ov = Image.new("RGBA", img.size, (0,0,0,0))
            fade_d  = ImageDraw.Draw(fade_ov)
            fade_d.rectangle([0,0,W,H], fill=(0,0,0,int(180*zoom_p)))
            img = Image.alpha_composite(img.convert("RGBA"), fade_ov).convert("RGB")
            d   = ImageDraw.Draw(img)
            # Big final value centered
            d.text((cx(d,final_val,fvf), H//2-fvs//2), final_val,
                   font=fvf, fill=col)

    # Brand
    bf = font(30, bold=True)
    d.text((cx(d,PAGE_NAME,bf), H-68), PAGE_NAME, font=bf, fill=C_GOLD)
    d.rectangle([0, H-4, W, H], fill=C_GOLD)
    return np.array(img)


def frame_result(t, data, total=5.0):
    """
    Sequential cards centered on screen, bigger, no grey text.
    0.0-0.7s: Final value zooms in center
    0.7-1.5s: INVESTED card
    1.5-2.3s: DURATION card
    2.3-3.1s: CAGR card
    3.1-3.9s: TOTAL RETURN card
    3.9-5.0s: All 4 together centered
    """
    is_up = data["ev"] >= data["inv"]
    col   = C_GREEN if is_up else C_RED
    gc    = C_GLOW_G if is_up else C_GLOW_R

    img = make_canvas()
    d   = ImageDraw.Draw(img)

    # Glow
    for r in range(5, 0, -1):
        radius = 220 + r*55
        a      = int(14*r/5)
        ov     = Image.new("RGBA", img.size, (0,0,0,0))
        od     = ImageDraw.Draw(ov)
        od.ellipse([W//2-radius, H//2-radius, W//2+radius, H//2+radius],
                   fill=(*gc, a))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        d   = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 3], fill=C_GOLD)
    d.rectangle([0, H-3, W, H], fill=C_GOLD)

    # Stock name
    name = data.get("dn", data["sym"].replace(".NS",""))
    nf_  = font(52, bold=True)
    d.text((cx(d,name,nf_), 48), name, font=nf_, fill=C_WHITE)

    # "Rs 1 Lakh →" label
    d.text((cx(d,"Rs 1 Lakh  →",font(40,True)), 118),
           "Rs 1 Lakh  →", font=font(40,True), fill=C_WHITE)

    # Final value — zooms in
    p_val = ease_out5(progress(t, 0.0, 0.6))
    val   = fmt_money_ascii(data["ev"])
    vf_   = font(int(lerp(40,112,p_val)), bold=True)
    vy    = 200
    for r in [8, 4]:
        d.text((cx(d,val,vf_), vy), val, font=vf_, fill=(*col, 20//r))
    d.text((cx(d,val,vf_), vy), val, font=vf_, fill=col)

    # Cards — centered vertically in remaining space
    CARDS = [
        ("INVESTED",     "Rs 1 Lakh",                          C_WHITE),
        ("DURATION",     f"{data['yrs']:.0f} Years",           C_WHITE),
        ("CAGR",         f"{data['cagr']:.1f}%",               C_GOLD),
        ("TOTAL RETURN", f"{(data['ev']/data['inv']-1)*100:.0f}%", col),
    ]
    SHOW_ALL_FROM = 3.9

    card_w  = W - 100   # wider cards
    card_x  = 50
    card_h  = 220       # taller cards
    # Center of remaining screen below value
    screen_mid = (H - 380) // 2 + 380  # midpoint of lower 2/3

    if t >= SHOW_ALL_FROM:
        # All 4 in 2x2 grid, centered
        p_all = ease_out3(progress(t, SHOW_ALL_FROM, total))
        bw4   = (W-120)//2
        bh4   = 200
        grid_h = bh4*2 + 20
        grid_y = (H - grid_h) // 2 + 80  # centered
        for i,(lbl,val2,vc) in enumerate(CARDS):
            row = i//2; c2 = i%2
            bx  = 50 + c2*(bw4+20)
            by  = int(grid_y + row*(bh4+20) + 30*(1-p_all))
            d.rounded_rectangle([bx, by, bx+bw4, by+bh4],
                                  radius=22, fill=C_BG3)
            d.rounded_rectangle([bx, by, bx+bw4, by+8],
                                  radius=22, fill=vc)
            lf2 = font(28, bold=True)
            d.text((bx+cx(d,lbl,lf2,bw4), by+18), lbl, font=lf2, fill=C_WHITE)
            for vs in [60, 50, 42]:
                vf2 = font(vs, bold=True)
                if tw(d,val2,vf2) <= bw4-24: break
            d.text((bx+cx(d,val2,vf2,bw4), by+68), val2, font=vf2, fill=vc)
    else:
        # Sequential — one card at a time, centered
        slot_dur = 0.8
        card_idx = int((t-0.7) / slot_dur) if t >= 0.7 else -1
        if 0 <= card_idx < len(CARDS):
            slot_t = t - 0.7 - card_idx*slot_dur
            if slot_t < 0.2:
                p_in  = ease_out3(slot_t/0.2)
                alpha = int(255*p_in)
                dy    = int(80*(1-p_in))
            elif slot_t < 0.55:
                alpha = 255; dy = 0
            else:
                p_out = ease_in2((slot_t-0.55)/0.25)
                alpha = int(255*(1-p_out))
                dy    = int(-60*p_out)

            lbl, val2, vc = CARDS[card_idx]
            # Center card vertically
            by = screen_mid - card_h//2 + dy
            d.rounded_rectangle([card_x, by, card_x+card_w, by+card_h],
                                  radius=28, fill=C_BG3)
            d.rounded_rectangle([card_x, by, card_x+card_w, by+10],
                                  radius=28, fill=vc)
            # Label
            lf2 = font(36, bold=True)
            d.text((cx(d,lbl,lf2), by+22), lbl, font=lf2,
                   fill=(*C_WHITE, alpha))
            # Value — big
            for vs in [96, 80, 68, 56]:
                vf2 = font(vs, bold=True)
                if tw(d,val2,vf2) <= card_w-60: break
            d.text((cx(d,val2,vf2), by+80), val2, font=vf2,
                   fill=(*vc, alpha))

    # Brand
    bf = font(32, bold=True)
    d.text((cx(d,PAGE_NAME,bf), H-80), PAGE_NAME, font=bf, fill=C_GOLD)
    return np.array(img)


def frame_outro(t, total=2.0):
    """19-21s: Clean cinematic outro."""
    img = make_canvas()
    d   = ImageDraw.Draw(img)

    # Subtle center glow
    for r in range(5, 0, -1):
        radius = 200 + r*50
        a      = int(15*r/5)
        ov     = Image.new("RGBA", img.size, (0,0,0,0))
        od     = ImageDraw.Draw(ov)
        od.ellipse([W//2-radius, H//2-radius-80,
                    W//2+radius, H//2+radius-80], fill=(*C_GOLD, a))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        d   = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 3], fill=C_GOLD)
    d.rectangle([0, H-3, W, H], fill=C_GOLD)

    # Brand name — fixed size, always fits
    p_b = ease_out5(progress(t, 0.1, 0.8))
    bf  = font(88, bold=True)
    # Auto-shrink if needed
    for bs in [88, 76, 64, 54]:
        bf = font(bs, bold=True)
        if tw(d, PAGE_NAME, bf) <= W - 80:
            break
    by_ = int(H//2 - 220 + 30*(1-p_b))
    d.text((cx(d, PAGE_NAME, bf), by_), PAGE_NAME, font=bf,
           fill=(*C_GOLD, int(255*p_b)))

    # Handle
    p_h = ease_out3(progress(t, 0.35, 1.0))
    hf  = font(38)
    d.text((cx(d, PAGE_HANDLE, hf), H//2-100),
           PAGE_HANDLE, font=hf, fill=(*C_MUTED, int(220*p_h)))

    # Divider
    p_div = ease_out3(progress(t, 0.4, 0.9))
    dw    = int((W-160)*p_div)
    d.rectangle([W//2-dw//2, H//2-50, W//2+dw//2, H//2-48],
                fill=(*C_GOLD, 140))

    # CTA
    p_c = ease_out3(progress(t, 0.5, 1.2))
    for i, line in enumerate(["Follow for daily stock", "investment insights!"]):
        cf = font(46)
        cy_ = int(H//2 + 10 + i*64 + 20*(1-p_c))
        d.text((cx(d, line, cf), cy_), line, font=cf,
               fill=(*C_WHITE, int(255*p_c)))

    # Subscribe button
    p_s = progress(t, 0.9, 1.6)
    if p_s > 0:
        se   = clamp(spring(p_s))
        bw_, bh_ = 360, 76
        bx   = W//2 - bw_//2
        by   = H//2 + 180
        d.rounded_rectangle([bx, by, bx+bw_, by+bh_], radius=38, fill=C_RED)
        sf_  = font(40, bold=True)
        sub  = "SUBSCRIBE"
        d.text((bx + (bw_-tw(d,sub,sf_))//2,
                by + (bh_-th(d,sub,sf_))//2),
               sub, font=sf_, fill=C_WHITE)

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
