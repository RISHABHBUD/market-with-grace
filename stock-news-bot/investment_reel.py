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
def make_chart(data, reveal=1.0, w=1080, h=900, cur_val=None):
    """Full-width chart that always fills the entire figure."""
    vals   = data["vals"]
    n      = max(2, int(len(vals)*reveal))
    shown  = vals[:n]
    dates  = [v[0] for v in shown]
    prices = [v[1] for v in shown]
    all_d  = [v[0] for v in vals]
    all_p  = [v[1] for v in vals]
    inv    = data["inv"]

    # Color based on current tip value (not final value)
    tip_val = prices[-1] if prices else inv
    is_up   = tip_val >= inv
    lc  = "#00E676" if is_up else "#FF3D57"
    gc  = "#00FF88" if is_up else "#FF2040"
    fc  = "#003320" if is_up else "#330010"

    fig, ax = plt.subplots(figsize=(w/100, h/100), dpi=100)
    fig.patch.set_facecolor("#04040C")
    ax.set_facecolor("#06060F")

    # ALWAYS use full x and y range — chart never shrinks
    ax.set_xlim(all_d[0], all_d[-1])
    ymin = min(all_p) * 0.85
    ymax = max(all_p) * 1.12
    ax.set_ylim(ymin, ymax)

    if len(dates) > 1:
        for lw, a in [(16,0.04),(10,0.10),(5,0.28),(2.5,1.0)]:
            ax.plot(dates, prices, color=lc, linewidth=lw,
                    alpha=a, solid_capstyle="round", zorder=4)
        ax.fill_between(dates, prices, ymin, color=fc, alpha=0.55, zorder=2)
        ax.fill_between(dates, prices, ymin, color=lc, alpha=0.07, zorder=3)

    # Reference line at Rs 1 lakh
    ax.axhline(y=inv, color="#FFFFFF", lw=1.5, ls="--", alpha=0.25, zorder=1)

    # Milestone dotted lines
    for m in milestones(inv, data["ev"]):
        target = inv * m
        for i,(d,v) in enumerate(vals):
            if v >= target and i < n:
                ax.axhline(y=target, color=gc, lw=0.8, ls=":", alpha=0.3)
                break

    # Rupee symbol at chart tip instead of plain dot
    if len(dates) > 1:
        tip_x, tip_y = dates[-1], prices[-1]
        # Glow rings
        for s, a in [(400,0.04),(200,0.10),(80,0.25)]:
            ax.scatter([tip_x], [tip_y], color=gc, s=s, alpha=a, zorder=5)
        # Rs label in a circle at tip
        ax.annotate("Rs", xy=(tip_x, tip_y),
                    fontsize=14, fontweight="bold",
                    ha="center", va="center", zorder=7,
                    color="#04040C",
                    bbox=dict(boxstyle="circle,pad=0.3", fc=gc, ec="none", alpha=0.9))

    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#1A1A3A"); ax.spines["bottom"].set_color("#1A1A3A")
    ax.tick_params(colors="#C0C8E0", labelsize=11, length=0)

    def fv(v, _):
        if v >= 1e7: return f"Rs{v/1e7:.0f}Cr"
        if v >= 1e5: return f"Rs{v/1e5:.0f}L"
        return f"Rs{v:,.0f}"
    ax.yaxis.set_major_formatter(plt.FuncFormatter(fv))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
    ax.grid(axis="y", color="#0C0C20", lw=0.8, zorder=0)

    # NO bbox_inches="tight" — use fixed size so chart always fills frame
    plt.subplots_adjust(left=0.12, right=0.98, top=0.97, bottom=0.08)
    buf = BytesIO()
    plt.savefig(buf, format="png", facecolor="#04040C", dpi=100)
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
    """Chart fills the screen. Header compact top. Value + milestone below."""
    reveal  = ease_io(progress(t, 0, total * 0.92))  # slightly slower
    vals    = data["vals"]
    inv     = data["inv"]

    n_shown = max(1, int(len(vals) * reveal))
    cur_val = vals[n_shown-1][1]
    below_inv = cur_val < inv
    col    = C_RED if below_inv else C_GREEN
    glow_c = C_GLOW_R if below_inv else C_GLOW_G

    # Background
    tint = reveal * 0.06
    bg1  = lerp_col(C_BG1, glow_c, tint)
    bg2  = lerp_col(C_BG2, glow_c, tint*0.4)
    arr  = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        arr[y] = lerp_col(bg1, bg2, y/H)
    img = Image.fromarray(arr)
    d   = ImageDraw.Draw(img)

    # ── Compact header at top ──────────────────────────────────
    name  = data.get("dn", data["sym"].replace(".NS",""))
    hdr_y = 52
    nf_   = font(48, bold=True)
    # Name pill
    nw_ = tw(d, name, nf_)
    d.rounded_rectangle([W//2-nw_//2-24, hdr_y-6, W//2+nw_//2+24, hdr_y+56],
                         radius=14, fill=C_BG3)
    d.text((cx(d,name,nf_), hdr_y), name, font=nf_, fill=C_GOLD)
    # Sub line
    sub = f"{data['sd'].year} → {data['ed'].year}  |  Rs 1 Lakh Journey"
    d.text((cx(d,sub,font(26)), hdr_y+64), sub, font=font(26), fill=C_WHITE)
    d.rectangle([80, hdr_y+100, W-80, hdr_y+102], fill=(*C_GOLD, 80))

    # ── Chart — fills most of screen ──────────────────────────
    chart_y = hdr_y + 112
    cw, ch  = W, H - chart_y - 280  # full width, leaves 280px below for counter+badge

    key = int(reveal * 200)
    if key not in cache:
        cache[key] = make_chart(data, reveal=reveal, w=cw, h=ch, cur_val=cur_val)

    chart_img = cache[key].resize((cw, ch), Image.LANCZOS)
    # Zoom effect
    zoom   = lerp(1.04, 1.0, ease_out3(progress(t, 0, 3.0)))
    zw, zh = int(cw*zoom), int(ch*zoom)
    zoomed = chart_img.resize((zw, zh), Image.LANCZOS)
    ox, oy = (zw-cw)//2, (zh-ch)//2
    img.paste(zoomed.crop((ox, oy, ox+cw, oy+ch)), (0, chart_y))

    chart_bot = chart_y + ch

    # ── Value counter ──────────────────────────────────────────
    val_str = fmt_money_ascii(cur_val)
    vf_     = font(80, bold=True)
    val_y   = chart_bot + 14
    for r in [6, 3]:
        d.text((cx(d,val_str,vf_), val_y), val_str, font=vf_,
               fill=(*col, 20//r))
    d.text((cx(d,val_str,vf_), val_y), val_str, font=vf_, fill=col)

    # ── Milestone — elegant text style, not a box ──────────────
    ms_list = milestones(inv, data["ev"])
    shown   = []
    for m in ms_list:
        target = inv * m
        for i,(dd,v) in enumerate(vals):
            if v >= target and i/len(vals) <= reveal:
                shown.append((m, i/len(vals)))
                break

    if shown:
        latest_m, latest_frac = shown[-1]
        pop_p = progress(reveal, latest_frac, latest_frac+0.12)
        sp_e  = clamp(spring(pop_p, s=12, d=0.4))
        if sp_e > 0.1:
            ms_y  = val_y + 96
            # Glowing text style — no box
            ms_txt = f"✦  {latest_m}x  ✦"
            mf_    = font(int(56*min(sp_e,1.0)), bold=True)
            # Glow layers
            for r in [8, 5, 2]:
                d.text((cx(d,ms_txt,mf_), ms_y), ms_txt, font=mf_,
                       fill=(*col, 20//r))
            d.text((cx(d,ms_txt,mf_), ms_y), ms_txt, font=mf_, fill=col)
            # "RETURN" sub label
            sub_ms = "RETURN ACHIEVED"
            d.text((cx(d,sub_ms,font(28)), ms_y+int(62*min(sp_e,1.0))),
                   sub_ms, font=font(28), fill=(*C_GOLD, int(200*sp_e)))

    # ── Full-screen milestone FLASH — 2 seconds ────────────────
    for m, frac in shown:
        flash_p = progress(reveal, frac, frac+0.18)  # ~2s
        if 0 < flash_p < 1:
            flash_e = ease_out3(1 - flash_p)
            ov = Image.new("RGBA", img.size, (0,0,0,0))
            od = ImageDraw.Draw(ov)
            od.rectangle([0,0,W,H], fill=(*col, int(130*flash_e)))
            img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
            d   = ImageDraw.Draw(img)
            ms_txt = f"{m}x RETURN!"
            mf     = font(148, bold=True)
            d.text((cx(d,ms_txt,mf)+4, H//2-84), ms_txt, font=mf, fill=(0,0,0))
            d.text((cx(d,ms_txt,mf), H//2-88), ms_txt, font=mf,
                   fill=(*C_GOLD, int(255*flash_e)))
            d.text((cx(d,"Your investment multiplied!",font(44)), H//2+80),
                   "Your investment multiplied!", font=font(44),
                   fill=(*C_WHITE, int(220*flash_e)))
            rng2 = random.Random(m*77)
            for _ in range(60):
                angle = rng2.uniform(0, 2*math.pi)
                dist  = int(rng2.uniform(100, 500) * (1-flash_e))
                px    = W//2 + int(math.cos(angle)*dist)
                py    = H//2 + int(math.sin(angle)*dist*0.7)
                ps    = rng2.randint(5, 18)
                pc    = C_GOLD if rng2.random() > 0.4 else col
                ov2   = Image.new("RGBA", img.size, (0,0,0,0))
                od2   = ImageDraw.Draw(ov2)
                od2.ellipse([px-ps, py-ps, px+ps, py+ps],
                            fill=(*pc, int(255*flash_e)))
                img = Image.alpha_composite(img.convert("RGBA"), ov2).convert("RGB")
                d   = ImageDraw.Draw(img)
            break

    # ── Final zoom transition at 100% ─────────────────────────
    if reveal >= 1.0:
        zoom_p = ease_out5(progress(t, total*0.92, total))
        if zoom_p > 0:
            final_val = fmt_money_ascii(data["ev"])
            fvs = int(lerp(80, 168, zoom_p))
            fvf = font(fvs, bold=True)
            fade_ov = Image.new("RGBA", img.size, (0,0,0,0))
            fade_d  = ImageDraw.Draw(fade_ov)
            fade_d.rectangle([0,0,W,H], fill=(0,0,0,int(210*zoom_p)))
            img = Image.alpha_composite(img.convert("RGBA"), fade_ov).convert("RGB")
            d   = ImageDraw.Draw(img)
            d.text((cx(d,final_val,fvf), H//2-fvs//2), final_val,
                   font=fvf, fill=col)

    bf = font(28, bold=True)
    d.text((cx(d,PAGE_NAME,bf), H-60), PAGE_NAME, font=bf, fill=C_GOLD)
    d.rectangle([0, H-4, W, H], fill=C_GOLD)
    return np.array(img)


def frame_result(t, data, total=5.0):
    """
    Sequential square cards. 5 cards total.
    Each card has unique color theme.
    Company name styled with gradient-like effect.
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

    # ── Company name — big, styled, with decorative underline ─
    name = data.get("dn", data["sym"].replace(".NS",""))
    hdr_y = 90
    # Auto-size
    for ns in [80, 68, 58, 50]:
        nf_ = font(ns, bold=True)
        if tw(d, name, nf_) <= W-80: break
    # Gold shadow for depth
    d.text((cx(d,name,nf_)+3, hdr_y+3), name, font=nf_, fill=(100,80,0))
    d.text((cx(d,name,nf_), hdr_y), name, font=nf_, fill=C_GOLD)
    # Decorative line under name
    nw_ = tw(d, name, nf_)
    d.rectangle([W//2-nw_//2, hdr_y+ns+8, W//2+nw_//2, hdr_y+ns+12],
                fill=C_GOLD)
    # Small dots at ends
    d.ellipse([W//2-nw_//2-10, hdr_y+ns+4, W//2-nw_//2+2, hdr_y+ns+16],
              fill=C_GOLD)
    d.ellipse([W//2+nw_//2-2, hdr_y+ns+4, W//2+nw_//2+10, hdr_y+ns+16],
              fill=C_GOLD)

    # ── Price display — stylish arrow ─────────────────────────
    price_y = hdr_y + ns + 30
    # "Rs 1 Lakh" on left, arrow center, current value on right
    p_val = ease_out5(progress(t, 0.0, 0.6))
    inv_str = "Rs 1 Lakh"
    val_str = fmt_money_ascii(data["ev"])
    inv_f   = font(44)
    arr_f   = font(60, bold=True)
    val_f   = font(int(lerp(30,88,p_val)), bold=True)

    inv_w = tw(d, inv_str, inv_f)
    arr_w = tw(d, "→", arr_f)
    val_w = tw(d, val_str, val_f)
    total_w = inv_w + arr_w + val_w + 60
    sx = (W - total_w) // 2

    d.text((sx, price_y+8), inv_str, font=inv_f, fill=C_WHITE)
    d.text((sx+inv_w+20, price_y), "→", font=arr_f, fill=C_GOLD)
    # Value with glow
    vx = sx + inv_w + arr_w + 40
    for r in [6, 3]:
        d.text((vx, price_y+8), val_str, font=val_f, fill=(*col, 20//r))
    d.text((vx, price_y+8), val_str, font=val_f, fill=col)

    # ── 5 Cards with unique color themes ──────────────────────
    # (label, value, border_color, has_burst)
    C_BLUE   = (80,  160, 255)   # blue for invested
    C_PURPLE = (160, 100, 255)   # purple for duration
    C_TEAL   = (0,   200, 180)   # teal for current price
    CARDS = [
        ("INVESTED",      "Rs 1 Lakh",                           C_BLUE,   False),
        ("DURATION",      f"{data['yrs']:.0f} Years",            C_PURPLE, False),
        ("CURRENT VALUE", fmt_money_ascii(data["ev"]),            col,      False),
        ("CAGR",          f"{data['cagr']:.1f}%",                C_GOLD,   True),
        ("TOTAL RETURN",  f"{(data['ev']/data['inv']-1)*100:.0f}%", col,   True),
    ]
    # In "all cards" view, replace INVESTED with CURRENT VALUE
    CARDS_ALL = [
        ("CURRENT VALUE", fmt_money_ascii(data["ev"]),            col,      False),
        ("DURATION",      f"{data['yrs']:.0f} Years",            C_PURPLE, False),
        ("CAGR",          f"{data['cagr']:.1f}%",                C_GOLD,   True),
        ("TOTAL RETURN",  f"{(data['ev']/data['inv']-1)*100:.0f}%", col,   True),
    ]

    SHOW_ALL_FROM = 4.2
    SQ = 400
    cards_center_y = H//2 + 160

    if t >= SHOW_ALL_FROM:
        # 2x2 grid with CARDS_ALL
        p_all = ease_out3(progress(t, SHOW_ALL_FROM, total))
        gap   = 20
        gx    = (W - SQ*2 - gap) // 2
        gy    = int(cards_center_y - (SQ*2+gap)//2 + 30*(1-p_all))
        for i,(lbl,val2,vc,_) in enumerate(CARDS_ALL):
            row = i//2; c2 = i%2
            bx  = gx + c2*(SQ+gap)
            by  = gy + row*(SQ+gap)
            # Card bg
            d.rounded_rectangle([bx, by, bx+SQ, by+SQ],
                                  radius=26, fill=C_BG3)
            # Colored top border
            d.rounded_rectangle([bx, by, bx+SQ, by+10],
                                  radius=26, fill=vc)
            # Subtle left accent
            d.rounded_rectangle([bx, by, bx+8, by+SQ],
                                  radius=26, fill=(*vc, 80))
            lf2 = font(28, bold=True)
            d.text((bx+cx(d,lbl,lf2,SQ), by+20), lbl, font=lf2, fill=C_WHITE)
            for vs in [68, 56, 46, 38]:
                vf2 = font(vs, bold=True)
                if tw(d,val2,vf2) <= SQ-32: break
            d.text((bx+cx(d,val2,vf2,SQ), by+SQ//2-vs//2+10),
                   val2, font=vf2, fill=vc)
    else:
        # Sequential
        slot_dur = 0.72
        card_idx = int((t-0.65)/slot_dur) if t >= 0.65 else -1
        if 0 <= card_idx < len(CARDS):
            lbl, val2, vc, has_burst = CARDS[card_idx]
            slot_t = t - 0.65 - card_idx*slot_dur
            if slot_t < 0.16:
                p_in  = ease_out3(slot_t/0.16)
                alpha = int(255*p_in); scale = lerp(0.55, 1.0, p_in)
            elif slot_t < 0.52:
                alpha = 255; scale = 1.0
            else:
                p_out = ease_in2((slot_t-0.52)/0.20)
                alpha = int(255*(1-p_out)); scale = lerp(1.0, 0.75, p_out)

            sq_s = int(SQ * scale)
            bx   = (W - sq_s)//2
            by   = cards_center_y - sq_s//2

            # Massive particle burst for CAGR and Total Return
            if has_burst and slot_t < 0.5:
                burst_e = ease_out3(slot_t/0.5)
                rng3    = random.Random(card_idx*333)
                for _ in range(120):
                    angle = rng3.uniform(0, 2*math.pi)
                    dist  = int(rng3.uniform(80, 520) * burst_e)
                    px    = W//2 + int(math.cos(angle)*dist)
                    py    = cards_center_y + int(math.sin(angle)*dist*0.8)
                    ps    = rng3.randint(5, 20)
                    pc    = C_GOLD if rng3.random() > 0.35 else vc
                    a_p   = int(255*(1-burst_e*0.7))
                    ov3   = Image.new("RGBA", img.size, (0,0,0,0))
                    od3   = ImageDraw.Draw(ov3)
                    od3.ellipse([px-ps, py-ps, px+ps, py+ps], fill=(*pc, a_p))
                    img = Image.alpha_composite(img.convert("RGBA"), ov3).convert("RGB")
                    d   = ImageDraw.Draw(img)

            # Card
            d.rounded_rectangle([bx, by, bx+sq_s, by+sq_s],
                                  radius=int(26*scale), fill=C_BG3)
            d.rounded_rectangle([bx, by, bx+sq_s, by+int(10*scale)],
                                  radius=int(26*scale), fill=vc)
            d.rounded_rectangle([bx, by, bx+int(8*scale), by+sq_s],
                                  radius=int(26*scale), fill=(*vc, 80))
            lf2 = font(int(30*scale), bold=True)
            d.text((bx+cx(d,lbl,lf2,sq_s), by+int(22*scale)),
                   lbl, font=lf2, fill=(*C_WHITE, alpha))
            for vs in [80, 68, 56, 46]:
                vf2 = font(int(vs*scale), bold=True)
                if tw(d,val2,vf2) <= sq_s-32: break
            d.text((bx+cx(d,val2,vf2,sq_s), by+sq_s//2-int(vs*scale)//2+10),
                   val2, font=vf2, fill=(*vc, alpha))

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
