"""
Investment Reel Generator — StockDev.in (Enhanced Cinematic Version)

Timeline:
  0-3s  : Cinematic hook — particles, glow, dramatic question
  3-13s : Neon chart draws with milestones + color-shifting bg
  13-18s: 3D perspective result card reveal
  18-20s: Outro CTA
"""

import os, re, random, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
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

# ── Cinematic dark palette ─────────────────────────────────────
BG_DARK     = (6,   8,  20)
BG_MID      = (12, 16,  38)
BG_CARD     = (18, 26,  58)
GOLD        = (255, 200,  50)
GOLD2       = (255, 165,   0)
WHITE       = (255, 255, 255)
MUTED       = (120, 135, 170)
GREEN       = ( 30, 220, 100)
GREEN_GLOW  = ( 20, 180,  80)
RED         = (230,  55,  75)
RED_GLOW    = (200,  40,  60)
ACCENT      = ( 80, 150, 255)
NEON_BLUE   = ( 60, 180, 255)

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

def ease_out(t, d):   return 1-(1-min(t/max(d,0.001),1))**3
def ease_in_out(t,d):
    p = min(t/max(d,0.001),1); return p*p*(3-2*p)
def ease_elastic(t, d):
    p = min(t/max(d,0.001),1)
    return 1 + (2.71828**(-6*p)) * math.cos(12*p) if p < 1 else 1.0

def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i]-c1[i])*t) for i in range(3))

def grad_bg(top=BG_DARK, bottom=BG_MID):
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        t = y/H
        arr[y] = [int(top[i]+(bottom[i]-top[i])*t) for i in range(3)]
    return arr

def add_particles(img, t, seed=42, count=40):
    """Subtle floating particles for depth."""
    draw = ImageDraw.Draw(img)
    rng  = random.Random(seed)
    for _ in range(count):
        x    = rng.randint(0, W)
        y    = rng.randint(0, H)
        spd  = rng.uniform(0.3, 1.2)
        size = rng.randint(1, 4)
        # Drift upward slowly
        y    = int((y - t * spd * 30) % H)
        alpha = rng.randint(30, 100)
        col  = (*GOLD, alpha) if rng.random() > 0.6 else (*NEON_BLUE, alpha)
        # Draw as tiny glowing dot
        img_rgba = img.convert("RGBA")
        ov = Image.new("RGBA", img.size, (0,0,0,0))
        od = ImageDraw.Draw(ov)
        od.ellipse([x-size, y-size, x+size, y+size], fill=col)
        img = Image.alpha_composite(img_rgba, ov).convert("RGB")
    return img

def draw_neon_text(draw, text, font, x, y, color, glow_color=None, glow_radius=3):
    """Draw text with neon glow effect."""
    gc = glow_color or color
    # Draw glow layers
    for r in range(glow_radius, 0, -1):
        alpha = int(60 / r)
        for dx in [-r, 0, r]:
            for dy in [-r, 0, r]:
                draw.text((x+dx, y+dy), text, font=font,
                          fill=(*gc[:3], alpha) if len(gc) == 4 else gc)
    draw.text((x, y), text, font=font, fill=color)

# ── Data fetching ──────────────────────────────────────────────
def fetch_investment_data(ticker, years=10):
    for sym in [ticker, ticker.replace(".NS", ".BO")]:
        try:
            t    = yf.Ticker(sym)
            hist = t.history(period="max")
            if hist.empty or len(hist) < 100: continue
            cutoff = datetime.now() - timedelta(days=years*365)
            hist   = hist[hist.index >= cutoff.strftime("%Y-%m-%d")]
            if len(hist) < 50:
                hist = yf.Ticker(sym).history(period="max")
            if hist.empty: continue
            start_price = hist["Close"].iloc[0]
            investment  = 100000
            values = [(date, (row["Close"]/start_price)*investment)
                      for date, row in hist.iterrows()]
            start_date = hist.index[0]
            end_date   = hist.index[-1]
            end_value  = values[-1][1]
            cagr = ((end_value/investment)**(1/max((end_date-start_date).days/365,1))-1)*100
            return dict(ticker=sym, values=values, start_price=start_price,
                        end_price=hist["Close"].iloc[-1], start_date=start_date,
                        end_date=end_date, investment=investment,
                        end_value=end_value, cagr=cagr,
                        years=(end_date-start_date).days/365)
        except Exception as e:
            print(f"  [!] {sym}: {e}"); continue
    return None

def fmt_money(v):
    if v >= 1e7:  return f"Rs {v/1e7:.2f} Cr"
    if v >= 1e5:  return f"Rs {v/1e5:.2f} L"
    return f"Rs {v:,.0f}"

def get_milestones(investment, end_value):
    """Return list of (multiplier, value) that were crossed."""
    milestones = []
    for mult in [2, 3, 5, 10, 20, 50]:
        target = investment * mult
        if end_value >= target:
            milestones.append((mult, target))
    return milestones


def make_neon_chart(data, reveal=1.0, w=960, h=520):
    """Neon glow chart with milestone markers."""
    values    = data["values"]
    n_show    = max(2, int(len(values) * reveal))
    shown     = values[:n_show]
    dates     = [v[0] for v in shown]
    vals      = [v[1] for v in shown]
    all_dates = [v[0] for v in values]
    all_vals  = [v[1] for v in values]
    start     = data["investment"]
    is_up     = data["end_value"] >= start
    color     = "#1EDC64" if is_up else "#E63748"
    glow      = "#0AFF50" if is_up else "#FF2040"

    fig, ax = plt.subplots(figsize=(w/100, h/100), dpi=100)
    fig.patch.set_facecolor("#060814")
    ax.set_facecolor("#0A0F24")

    ax.set_xlim(all_dates[0], all_dates[-1])
    ax.set_ylim(min(all_vals)*0.90, max(all_vals)*1.08)

    # Glow effect — draw line multiple times with decreasing alpha
    for lw, alpha in [(12, 0.08), (7, 0.15), (4, 0.3), (2, 1.0)]:
        ax.plot(dates, vals, color=color, linewidth=lw,
                alpha=alpha, zorder=3, solid_capstyle="round")

    # Fill under line
    ax.fill_between(dates, vals, start*0.88, color=color, alpha=0.12, zorder=2)

    # Reference line
    ax.axhline(y=start, color="#FFFFFF", linewidth=1, linestyle="--",
               alpha=0.25, zorder=1)

    # Milestone markers
    milestones = get_milestones(start, data["end_value"])
    for mult, target in milestones:
        # Find first date where value crossed this milestone
        for i, (d, v) in enumerate(values):
            if v >= target and i < n_show:
                ax.axhline(y=target, color=glow, linewidth=0.5,
                           linestyle=":", alpha=0.4)
                ax.annotate(f"{mult}x", xy=(d, target),
                            fontsize=8, color=glow, fontweight="bold",
                            xytext=(5, 5), textcoords="offset points",
                            alpha=0.8)
                break

    # Glowing dot at tip
    if len(dates) > 1:
        for s, a in [(120, 0.1), (60, 0.2), (20, 0.5), (8, 1.0)]:
            ax.scatter([dates[-1]], [vals[-1]], color=glow, s=s,
                       alpha=a, zorder=6)

    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#1A2550"); ax.spines["bottom"].set_color("#1A2550")
    ax.tick_params(colors="#5060A0", labelsize=8)

    def fmt_v(v, _):
        if v >= 1e7: return f"Rs{v/1e7:.0f}Cr"
        if v >= 1e5: return f"Rs{v/1e5:.0f}L"
        return f"Rs{v:,.0f}"

    ax.yaxis.set_major_formatter(plt.FuncFormatter(fmt_v))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
    ax.grid(axis="y", color="#0E1830", linewidth=0.6, zorder=0)

    plt.tight_layout(pad=0.2)
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor="#060814")
    plt.close(fig); buf.seek(0)
    return Image.open(buf).convert("RGB")

# ── Frame builders ─────────────────────────────────────────────

def f_hook(t, name, years, total=3.0):
    """0-3s: Cinematic hook with particles and glow."""
    e   = ease_out(t, 0.8)
    img = Image.fromarray(grad_bg())
    img = add_particles(img, t, count=50)
    draw = ImageDraw.Draw(img)

    # Pulsing glow rings
    for ring in range(4, 0, -1):
        r     = int((200 + ring*60) * e)
        alpha = int(20 * ring / 4)
        ov    = Image.new("RGBA", img.size, (0,0,0,0))
        od    = ImageDraw.Draw(ov)
        od.ellipse([W//2-r, H//2-r-80, W//2+r, H//2+r-80],
                   fill=(*GOLD, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        draw = ImageDraw.Draw(img)

    # Flash on entry
    if t < 0.1:
        flash = int(200*(1-t/0.1))
        ov2   = Image.new("RGBA", img.size, (255,255,255,flash))
        img   = Image.alpha_composite(img.convert("RGBA"), ov2).convert("RGB")
        draw  = ImageDraw.Draw(img)

    yr_str = f"{int(years)} years" if years >= 1 else f"{int(years*12)} months"
    lines  = ["What if you had", f"invested Rs 1 Lakh", f"{yr_str} ago in", name + "?"]

    max_w = W - 80
    y     = H//2 - 220
    for i, line in enumerate(lines):
        for fsize in [76, 64, 54, 44]:
            f = get_font(fsize, bold=(i < 3))
            if tw(draw, line, f) <= max_w: break
        col = GOLD if i in [1, 2] else WHITE
        # Shadow
        draw.text((cx(draw,line,f)+3, y+3), line, font=f, fill=(0,0,0))
        draw.text((cx(draw,line,f), y), line, font=f, fill=col)
        y += fsize + 18

    # Brand
    bf = get_font(34, bold=True)
    draw.text((cx(draw,PAGE_NAME,bf), H-110), PAGE_NAME, font=bf, fill=GOLD)
    draw.rectangle([0, H-6, W, H], fill=GOLD)
    return np.array(img)


def f_chart(t, data, chart_cache, total=10.0):
    """3-13s: Neon chart with color-shifting bg and milestone pops."""
    reveal  = min(t/(total*0.88), 1.0)
    is_up   = data["end_value"] >= data["investment"]
    col     = GREEN if is_up else RED

    # Background shifts from dark → tinted as chart draws
    tint_strength = reveal * 0.15
    bg_top  = lerp_color(BG_DARK, GREEN_GLOW if is_up else RED_GLOW, tint_strength)
    bg_bot  = lerp_color(BG_MID,  GREEN_GLOW if is_up else RED_GLOW, tint_strength*0.5)

    img  = Image.fromarray(grad_bg(bg_top, bg_bot))
    img  = add_particles(img, t, count=30)
    draw = ImageDraw.Draw(img)

    # Header
    name = data.get("display_name", data["ticker"].replace(".NS",""))
    nf   = get_font(52, bold=True)
    draw.text((cx(draw,name,nf)+2, 57), name, font=nf, fill=(0,0,0))
    draw.text((cx(draw,name,nf), 55), name, font=nf, fill=WHITE)

    sub = f"{data['start_date'].year}  →  {data['end_date'].year}  |  Rs 1 Lakh"
    draw.text((cx(draw,sub,get_font(28)), 120), sub, font=get_font(28), fill=MUTED)

    # Chart
    key = int(reveal * 80)
    if key not in chart_cache:
        chart_cache[key] = make_neon_chart(data, reveal=reveal)

    chart = chart_cache[key].resize((960, 520), Image.LANCZOS)
    img.paste(chart, ((W-960)//2, 162))

    chart_bottom = 162 + 520  # = 682

    # Milestone pop badges
    milestones = get_milestones(data["investment"], data["end_value"])
    values     = data["values"]
    badge_y    = chart_bottom + 20
    shown_badges = []
    for mult, target in milestones:
        for i, (d, v) in enumerate(values):
            if v >= target:
                frac = i / len(values)
                if frac <= reveal:
                    shown_badges.append(mult)
                break

    if shown_badges:
        bw_each = (W - 80) // max(len(shown_badges), 1)
        for i, mult in enumerate(shown_badges[-4:]):
            bx = 40 + i * bw_each
            e2 = ease_elastic(reveal - 0.1*i, 0.3)
            bh = int(70 * min(e2, 1.2))
            draw.rounded_rectangle([bx+4, badge_y, bx+bw_each-4, badge_y+bh],
                                    radius=14, fill=BG_CARD)
            draw.rounded_rectangle([bx+4, badge_y, bx+bw_each-4, badge_y+5],
                                    radius=14, fill=col)
            label = f"{mult}x"
            lf2   = get_font(36, bold=True)
            draw.text((bx+4+cx(draw,label,lf2,bw_each-8), badge_y+16),
                      label, font=lf2, fill=col)

    # Current value counter — accelerates dramatically
    accel = reveal ** 0.4  # slow start, fast finish
    cur_val = data["investment"] + (data["end_value"]-data["investment"]) * accel
    val_str = fmt_money(cur_val)
    vf      = get_font(88, bold=True)
    # Neon glow on value
    for r in [6, 4, 2]:
        alpha = 40 // r
        draw.text((cx(draw,val_str,vf), badge_y+90), val_str, font=vf,
                  fill=(*col[:3], alpha))
    draw.text((cx(draw,val_str,vf), badge_y+90), val_str, font=vf, fill=col)

    # Stats row
    stats = [f"CAGR  {data['cagr']:.1f}%",
             f"Return  {(data['end_value']/data['investment']-1)*100:.0f}%",
             f"Years  {data['years']:.1f}"]
    row_y = badge_y + 200
    bw3   = (W-80)//3
    for i, stat in enumerate(stats):
        bx = 40 + i*bw3
        draw.rounded_rectangle([bx+4, row_y, bx+bw3-4, row_y+80],
                                radius=14, fill=BG_CARD)
        draw.text((bx+4+cx(draw,stat,get_font(28,True),bw3-8), row_y+24),
                  stat, font=get_font(28,True), fill=GOLD)

    # Brand
    draw.text((cx(draw,PAGE_NAME,get_font(30,True)), H-80),
              PAGE_NAME, font=get_font(30,True), fill=GOLD)
    draw.rectangle([0, H-6, W, H], fill=GOLD)
    return np.array(img)


def f_result(t, data, total=5.0):
    """13-18s: 3D perspective card reveal."""
    e   = ease_out(t, 0.6)
    col = GREEN if data["end_value"] >= data["investment"] else RED

    img  = Image.fromarray(grad_bg())
    img  = add_particles(img, t+10, count=60)
    draw = ImageDraw.Draw(img)

    # Expanding glow behind card
    for r in range(5, 0, -1):
        radius = int(400 * e * r / 5)
        ov     = Image.new("RGBA", img.size, (0,0,0,0))
        od     = ImageDraw.Draw(ov)
        od.ellipse([W//2-radius, H//2-radius, W//2+radius, H//2+radius],
                   fill=(*col[:3], int(12*r/5)))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        draw = ImageDraw.Draw(img)

    # Card with perspective — starts narrow, expands to full width
    card_w  = int((W-80) * min(e*1.5, 1.0))
    card_x  = (W - card_w) // 2
    card_y  = H//2 - 400
    card_h  = 780
    draw.rounded_rectangle([card_x, card_y, card_x+card_w, card_y+card_h],
                            radius=28, fill=BG_CARD)
    draw.rounded_rectangle([card_x, card_y, card_x+card_w, card_y+10],
                            radius=28, fill=col)

    name = data.get("display_name", data["ticker"].replace(".NS",""))
    nf   = get_font(58, bold=True)
    draw.text((cx(draw,name,nf), card_y+28), name, font=nf, fill=WHITE)

    # Invested label
    draw.text((cx(draw,"Rs 1,00,000 Invested",get_font(44,True)), card_y+110),
              "Rs 1,00,000 Invested", font=get_font(44,True), fill=MUTED)

    # Arrow
    if t > 0.5:
        ae = ease_out(t-0.5, 0.4)
        af = get_font(int(90*ae), bold=True)
        draw.text((cx(draw,"↓",af), card_y+185), "↓", font=af, fill=col)

    # Final value with neon glow
    if t > 0.9:
        ve      = ease_elastic(t-0.9, 0.6)
        val_str = fmt_money(data["end_value"])
        vf      = get_font(int(96*min(ve,1.1)), bold=True)
        for r in [8, 5, 2]:
            draw.text((cx(draw,val_str,vf), card_y+290), val_str, font=vf,
                      fill=(*col[:3], 30//r))
        draw.text((cx(draw,val_str,vf), card_y+290), val_str, font=vf, fill=col)

    # Stats
    if t > 1.5:
        se    = ease_out(t-1.5, 0.5)
        stats = [("Invested","Rs 1 Lakh"),
                 ("Years", f"{data['years']:.1f}"),
                 ("CAGR",  f"{data['cagr']:.1f}%"),
                 ("Return",f"{(data['end_value']/data['investment']-1)*100:.0f}%")]
        bw4 = (card_w-40)//4
        for i,(label,val) in enumerate(stats):
            bx = card_x+20 + i*bw4
            by = int(card_y+440 + 30*(1-se))
            draw.rounded_rectangle([bx+2, by, bx+bw4-2, by+120],
                                    radius=14, fill=(24,36,72))
            draw.text((bx+2+cx(draw,label,get_font(22,True),bw4-4), by+10),
                      label, font=get_font(22,True), fill=MUTED)
            draw.text((bx+2+cx(draw,val,get_font(36,True),bw4-4), by+46),
                      val, font=get_font(36,True), fill=WHITE)

    # Period + disclaimer
    period = f"{data['start_date'].strftime('%b %Y')} — {data['end_date'].strftime('%b %Y')}"
    draw.text((cx(draw,period,get_font(26)), card_y+590),
              period, font=get_font(26), fill=MUTED)
    disc = "Past performance ≠ future returns"
    draw.text((cx(draw,disc,get_font(22)), card_y+640),
              disc, font=get_font(22), fill=(*MUTED[:3],150))

    draw.rectangle([0, H-6, W, H], fill=GOLD)
    return np.array(img)


def f_outro(t, total=2.0):
    """18-20s: Cinematic outro."""
    e   = ease_out(t, 0.5)
    img = Image.fromarray(grad_bg())
    img = add_particles(img, t+20, count=80)
    draw = ImageDraw.Draw(img)

    # Gold horizontal lines sweep in
    for i in range(5):
        lx = int(W * (1-e) * (i%2==0 and 1 or -1) + (W//2 if i%2 else 0))
        ly = H//2 - 300 + i*120
        draw.rectangle([0, ly, W, ly+2], fill=(*GOLD, int(60*e)))

    lf = get_font(int(96*e), bold=True)
    lw = tw(draw, PAGE_NAME, lf)
    # Neon glow on brand
    for r in [8, 5, 2]:
        draw.text((W//2-lw//2, H//2-180), PAGE_NAME, font=lf,
                  fill=(*GOLD[:3], 30//r))
    draw.text((W//2-lw//2, H//2-180), PAGE_NAME, font=lf, fill=GOLD)

    if t > 0.7:
        ce = ease_out(t-0.7, 0.5)
        for i, line in enumerate(["Follow for daily stock", "investment insights!"]):
            f = get_font(int(46*ce))
            draw.text((cx(draw,line,f), H//2-30+i*62), line, font=f, fill=WHITE)

    if t > 1.3:
        be  = ease_elastic(t-1.3, 0.5)
        bw, bh = 360, 76
        bx, by = W//2-bw//2, H//2+160
        draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=38, fill=RED)
        sub = "SUBSCRIBE"
        sf  = get_font(int(40*min(be,1.1)), bold=True)
        draw.text((bx+(bw-tw(draw,sub,sf))//2, by+(bh-40)//2),
                  sub, font=sf, fill=WHITE)

    draw.rectangle([0, H-6, W, H], fill=GOLD)
    return np.array(img)

# ── Thumbnail generator ────────────────────────────────────────
def create_thumbnail(data, output_path):
    """Generate a cinematic thumbnail for YouTube."""
    img  = Image.fromarray(grad_bg())
    img  = add_particles(img, 5.0, count=60)
    draw = ImageDraw.Draw(img)

    is_up = data["end_value"] >= data["investment"]
    col   = GREEN if is_up else RED
    name  = data.get("display_name", data["ticker"].replace(".NS",""))

    # Large glow circle
    for r in range(5, 0, -1):
        radius = 280 + r*40
        ov     = Image.new("RGBA", img.size, (0,0,0,0))
        od     = ImageDraw.Draw(ov)
        od.ellipse([W//2-radius, H//2-radius-100,
                    W//2+radius, H//2+radius-100],
                   fill=(*col[:3], int(15*r/5)))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        draw = ImageDraw.Draw(img)

    # "Rs 1 LAKH" top
    t1 = "Rs 1 LAKH"
    f1 = get_font(80, bold=True)
    draw.text((cx(draw,t1,f1)+3, 183), t1, font=f1, fill=(0,0,0))
    draw.text((cx(draw,t1,f1), 180), t1, font=f1, fill=MUTED)

    # Arrow
    draw.text((cx(draw,"↓",get_font(100,True)), 280), "↓",
              font=get_font(100,True), fill=col)

    # Final value — huge
    val_str = fmt_money(data["end_value"])
    vf      = get_font(120, bold=True)
    for r in [10, 6, 3]:
        draw.text((cx(draw,val_str,vf), 390), val_str, font=vf,
                  fill=(*col[:3], 25//r))
    draw.text((cx(draw,val_str,vf), 390), val_str, font=vf, fill=col)

    # Stock name
    nf = get_font(64, bold=True)
    draw.text((cx(draw,name,nf), 540), name, font=nf, fill=WHITE)

    # Years badge
    yr_str = f"In {data['years']:.0f} Years"
    yf2    = get_font(48)
    yw     = tw(draw, yr_str, yf2) + 40
    draw.rounded_rectangle([(W-yw)//2, 620, (W+yw)//2, 680],
                            radius=30, fill=BG_CARD)
    draw.text(((W-tw(draw,yr_str,yf2))//2, 628), yr_str, font=yf2, fill=GOLD)

    # CAGR
    cagr_str = f"CAGR: {data['cagr']:.1f}% per year"
    draw.text((cx(draw,cagr_str,get_font(38)), 710),
              cagr_str, font=get_font(38), fill=MUTED)

    # Brand bar at bottom
    draw.rounded_rectangle([40, H-160, W-40, H-50], radius=24, fill=BG_CARD)
    draw.rounded_rectangle([40, H-160, W-40, H-154], radius=24, fill=GOLD)
    bf = get_font(52, bold=True)
    draw.text((cx(draw,PAGE_NAME,bf), H-142), PAGE_NAME, font=bf, fill=GOLD)
    draw.text((cx(draw,PAGE_HANDLE,get_font(32)), H-82),
              PAGE_HANDLE, font=get_font(32), fill=MUTED)

    img.save(output_path, quality=95)
    print(f"  [✓] Thumbnail saved -> {output_path}")


# ── Main ───────────────────────────────────────────────────────
def create_investment_reel(display_name, ticker, output_path):
    print(f"  Stock: {display_name} ({ticker})")
    print("  Fetching historical data...")
    data = fetch_investment_data(ticker)
    if not data:
        print(f"  [!] Could not fetch data for {ticker}")
        return False

    data["display_name"] = display_name
    years = data["years"]
    print(f"  Data: {data['start_date'].date()} → {data['end_date'].date()}")
    print(f"  Rs 1L → {fmt_money(data['end_value'])} | CAGR: {data['cagr']:.1f}%")

    # Generate thumbnail alongside reel
    thumb_path = output_path.replace(".mp4", "_thumbnail.jpg")
    create_thumbnail(data, thumb_path)

    chart_cache = {}

    def make_clip(fn, dur, **kw):
        return VideoClip(lambda t: fn(t, **kw).astype(np.uint8),
                         duration=dur).with_fps(FPS)

    print("  Rendering cinematic sections...")
    clips = [
        make_clip(f_hook,   3.0,  name=display_name, years=years),
        make_clip(f_chart,  10.0, data=data, chart_cache=chart_cache),
        make_clip(f_result, 5.0,  data=data),
        make_clip(f_outro,  2.0),
    ]

    video = concatenate_videoclips(clips)

    # Music — prefer cinematic tracks
    music_files = sorted([f for f in os.listdir(MUSIC_DIR)
                          if f.endswith((".mp3",".wav"))],
                         key=lambda x: ("cinematic" in x.lower(), x),
                         reverse=True) if os.path.exists(MUSIC_DIR) else []
    print(f"  Music files: {music_files}")
    if music_files:
        try:
            chosen = music_files[0]  # prefer cinematic
            print(f"  Adding music: {chosen}")
            audio = AudioFileClip(os.path.join(MUSIC_DIR, chosen))
            dur   = sum(c.duration for c in clips)
            audio = audio.subclipped(0, min(dur, audio.duration))
            video = video.with_audio(audio)
            print("  [✓] Music embedded")
        except Exception as e:
            print(f"  [!] Music error: {e}")

    print("  Writing video...")
    video.write_videofile(output_path, fps=FPS, codec="libx264",
                          audio_codec="aac", temp_audiofile="temp_inv_audio.m4a",
                          remove_temp=True, logger=None, preset="ultrafast")
    print(f"  [✓] Reel saved -> {output_path}")
    return True
