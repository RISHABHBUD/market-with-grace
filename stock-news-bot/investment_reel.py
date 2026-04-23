"""
Investment Reel Generator — StockDev.in
"Agar aapne 10 saal pehle 1 lakh lagaye hote..."

Timeline:
  0-2s  : Hook — question flashes in
  2-12s : Animated chart — Y-axis = value of Rs 1 lakh investment
  12-17s: Result card — Rs 1L → Rs X L
  17-19s: Outro CTA
"""

import os, re, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoClip, AudioFileClip, concatenate_videoclips
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime, timedelta
from config import PAGE_NAME, PAGE_HANDLE

W, H, FPS = 1080, 1920, 30
MUSIC_DIR  = os.path.join(os.path.dirname(__file__), "music")

# Palette — dark premium feel for investment content
BG_TOP      = (8,  12, 28)
BG_BOT      = (18, 24, 52)
CARD        = (22, 32, 65)
GOLD        = (255, 200, 50)
GOLD_LIGHT  = (255, 230, 140)
WHITE       = (255, 255, 255)
MUTED       = (140, 155, 190)
GREEN       = (40,  210, 110)
RED         = (230, 60,  80)
ACCENT      = (100, 160, 255)
PURPLE      = (160, 100, 255)


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

def ease_out(t, d): return 1-(1-min(t/max(d,0.001),1))**3

def grad_bg():
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        t = y/H
        arr[y] = [int(BG_TOP[i]+(BG_BOT[i]-BG_TOP[i])*t) for i in range(3)]
    return arr


def fetch_investment_data(ticker, years=10):
    """
    Fetch historical data and compute Rs 1 lakh investment value over time.
    Returns list of (date, value) tuples.
    Falls back to .BO if .NS fails.
    """
    for sym in [ticker, ticker.replace(".NS", ".BO")]:
        try:
            t    = yf.Ticker(sym)
            hist = t.history(period="max")
            if hist.empty or len(hist) < 100:
                continue

            # Use listing date or 10 years back, whichever is later
            cutoff = datetime.now() - timedelta(days=years*365)
            hist   = hist[hist.index >= cutoff.strftime("%Y-%m-%d")]

            if len(hist) < 50:
                # Use all available data if less than 10 years
                t2   = yf.Ticker(sym)
                hist = t2.history(period="max")

            if hist.empty:
                continue

            start_price = hist["Close"].iloc[0]
            investment  = 100000  # Rs 1 lakh

            values = []
            for date, row in hist.iterrows():
                val = (row["Close"] / start_price) * investment
                values.append((date, val))

            start_date = hist.index[0]
            end_date   = hist.index[-1]
            end_value  = values[-1][1]
            cagr       = ((end_value/investment) ** (1/max((end_date-start_date).days/365,1)) - 1) * 100

            return dict(
                ticker=sym,
                values=values,
                start_price=start_price,
                end_price=hist["Close"].iloc[-1],
                start_date=start_date,
                end_date=end_date,
                investment=investment,
                end_value=end_value,
                cagr=cagr,
                years=(end_date-start_date).days/365,
            )
        except Exception as e:
            print(f"  [!] {sym} failed: {e}")
            continue
    return None


def make_investment_chart(data, reveal=1.0, w=960, h=600):
    """Animated investment value chart — Y axis in Rs."""
    values = data["values"]
    n_show = max(2, int(len(values) * reveal))
    shown  = values[:n_show]

    dates  = [v[0] for v in shown]
    vals   = [v[1] for v in shown]
    start  = data["investment"]
    color  = "#28D26E" if data["end_value"] >= start else "#E63C50"

    fig, ax = plt.subplots(figsize=(w/100, h/100), dpi=100)
    fig.patch.set_facecolor("#0C1428")
    ax.set_facecolor("#101C38")

    ax.plot(dates, vals, color=color, linewidth=3, zorder=3)
    ax.fill_between(dates, vals, start*0.95, color=color, alpha=0.2, zorder=2)

    # Reference line at Rs 1 lakh
    ax.axhline(y=start, color="#FFFFFF", linewidth=1, linestyle="--", alpha=0.3)

    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#1E3060"); ax.spines["bottom"].set_color("#1E3060")
    ax.tick_params(colors="#8090B0", labelsize=9)

    def fmt_val(v, _):
        if v >= 1e7:   return f"Rs{v/1e7:.1f}Cr"
        if v >= 1e5:   return f"Rs{v/1e5:.1f}L"
        return f"Rs{v:,.0f}"

    ax.yaxis.set_major_formatter(plt.FuncFormatter(fmt_val))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
    ax.grid(axis="y", color="#1A2A50", linewidth=0.8, zorder=1)

    # Dot at current value
    if len(dates) > 1:
        ax.scatter([dates[-1]], [vals[-1]], color=color, s=80, zorder=5)

    plt.tight_layout(pad=0.3)
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor="#0C1428")
    plt.close(fig); buf.seek(0)
    return Image.open(buf).convert("RGB")


def fmt_money(v):
    if v >= 1e7:  return f"Rs {v/1e7:.2f} Crore"
    if v >= 1e5:  return f"Rs {v/1e5:.2f} Lakh"
    return f"Rs {v:,.0f}"


# ── Frame builders ─────────────────────────────────────────────

def f_hook(t, name, years, total=2.0):
    """0-2s: Hook question flashes in."""
    img  = Image.fromarray(grad_bg())
    draw = ImageDraw.Draw(img)

    e = ease_out(t, 0.6)

    # Glow circle
    r = int(280 * e)
    draw.ellipse([W//2-r, H//2-r-100, W//2+r, H//2+r-100], fill=(20,35,80))

    # Flash
    if t < 0.12:
        alpha = int(255*(1-t/0.12))
        ov = Image.new("RGBA", img.size, (255,255,255,alpha))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        draw = ImageDraw.Draw(img)

    # Hook text
    yr_str = f"{int(years)} saal" if years >= 1 else f"{int(years*12)} mahine"
    lines  = [
        "Agar aapne",
        f"{yr_str} pehle",
        "Rs 1 Lakh lagaye hote",
        name + " mein...",
    ]

    max_w = W - 100
    y = H//2 - 200
    for i, line in enumerate(lines):
        for fsize in [72, 60, 50, 42]:
            f = get_font(fsize, bold=(i < 3))
            if tw(draw, line, f) <= max_w:
                break
        col = GOLD if i == 2 else WHITE
        draw.text((cx(draw, line, f), y), line, font=f, fill=col)
        y += fsize + 20

    # Brand
    bf = get_font(32, bold=True)
    draw.text((cx(draw, PAGE_NAME, bf), H-120), PAGE_NAME, font=bf, fill=GOLD)

    return np.array(img)


def f_chart(t, data, chart_cache, total=10.0):
    """2-12s: Chart draws itself left to right."""
    img  = Image.fromarray(grad_bg())
    draw = ImageDraw.Draw(img)

    # Header
    name = data.get("display_name", data["ticker"].replace(".NS",""))
    draw.text((cx(draw, name, get_font(52,True)), 55),
              name, font=get_font(52,True), fill=WHITE)

    start_yr = data["start_date"].year
    end_yr   = data["end_date"].year
    sub      = f"{start_yr}  →  {end_yr}"
    draw.text((cx(draw, sub, get_font(34)), 122), sub, font=get_font(34), fill=MUTED)

    # Chart reveal
    reveal = min(t / (total * 0.85), 1.0)
    key    = int(reveal * 20)  # cache at 5% intervals

    if key not in chart_cache:
        chart_cache[key] = make_investment_chart(data, reveal=reveal)

    chart = chart_cache[key]
    cw, ch = 960, 600
    chart  = chart.resize((cw, ch), Image.LANCZOS)
    img.paste(chart, ((W-cw)//2, 175))

    # Rs 1L reference label
    draw.text((60, 175+ch+20), "--- Rs 1 Lakh (invested)", font=get_font(26), fill=MUTED)

    # Current value counter (counts up as chart draws)
    cur_val = data["investment"] + (data["end_value"] - data["investment"]) * reveal
    val_str = fmt_money(cur_val)
    col     = GREEN if data["end_value"] >= data["investment"] else RED

    vf = get_font(72, bold=True)
    draw.text((cx(draw, val_str, vf), 175+ch+80), val_str, font=vf, fill=col)

    # CAGR badge
    cagr_str = f"CAGR: {data['cagr']:.1f}% per year"
    cf = get_font(32)
    cw2 = tw(draw, cagr_str, cf) + 40
    draw.rounded_rectangle([(W-cw2)//2, 175+ch+170, (W+cw2)//2, 175+ch+218],
                            radius=20, fill=CARD)
    draw.text(((W-tw(draw,cagr_str,cf))//2, 175+ch+178),
              cagr_str, font=cf, fill=GOLD)

    # Brand
    draw.text((cx(draw, PAGE_NAME, get_font(28,True)), H-80),
              PAGE_NAME, font=get_font(28,True), fill=GOLD)

    return np.array(img)


def f_result(t, data, total=5.0):
    """12-17s: Big result reveal card."""
    img  = Image.fromarray(grad_bg())
    draw = ImageDraw.Draw(img)

    e = ease_out(t, 0.5)

    # Glow
    r = int(350 * e)
    col = GREEN if data["end_value"] >= data["investment"] else RED
    draw.ellipse([W//2-r, H//2-r, W//2+r, H//2+r], fill=(*col, 15))

    # Card
    card_y = int(H//2 - 380)
    draw.rounded_rectangle([60, card_y, W-60, card_y+760],
                            radius=32, fill=CARD)
    draw.rounded_rectangle([60, card_y, W-60, card_y+10], radius=32, fill=col)

    name = data.get("display_name", data["ticker"].replace(".NS",""))

    # Stock name
    nf = get_font(56, bold=True)
    draw.text((cx(draw, name, nf), card_y+30), name, font=nf, fill=WHITE)

    # Arrow animation
    arrow_y = card_y + 120
    draw.text((cx(draw, "Rs 1,00,000", get_font(52,True)), arrow_y),
              "Rs 1,00,000", font=get_font(52,True), fill=MUTED)

    if t > 0.4:
        ae = ease_out(t-0.4, 0.5)
        arrow = "↓"
        af = get_font(int(80*ae), bold=True)
        draw.text((cx(draw, arrow, af), arrow_y+80), arrow, font=af, fill=col)

    if t > 0.8:
        ve = ease_out(t-0.8, 0.6)
        val_str = fmt_money(data["end_value"])
        vf = get_font(int(88*ve), bold=True)
        draw.text((cx(draw, val_str, vf), arrow_y+180), val_str, font=vf, fill=col)

    # Stats row
    if t > 1.2:
        se = ease_out(t-1.2, 0.5)
        stats = [
            ("Invested", "Rs 1 Lakh"),
            ("Years", f"{data['years']:.1f}"),
            ("CAGR", f"{data['cagr']:.1f}%"),
            ("Return", f"{(data['end_value']/data['investment']-1)*100:.0f}%"),
        ]
        bw = (W-120)//4
        for i, (label, val) in enumerate(stats):
            bx = 60 + i*bw
            by = int(card_y + 420 + 30*(1-se))
            draw.rounded_rectangle([bx+4, by, bx+bw-4, by+130],
                                    radius=16, fill=(30,42,80))
            draw.text((bx+4+cx(draw,label,get_font(24,True),bw-8), by+12),
                      label, font=get_font(24,True), fill=MUTED)
            draw.text((bx+4+cx(draw,val,get_font(38,True),bw-8), by+52),
                      val, font=get_font(38,True), fill=WHITE)

    # Period
    period = f"{data['start_date'].strftime('%b %Y')} — {data['end_date'].strftime('%b %Y')}"
    draw.text((cx(draw, period, get_font(28)), card_y+580),
              period, font=get_font(28), fill=MUTED)

    # Disclaimer
    disc = "Past performance does not guarantee future returns."
    draw.text((cx(draw, disc, get_font(22)), card_y+640),
              disc, font=get_font(22), fill=(*MUTED, 180))

    return np.array(img)


def f_outro(t, total=2.0):
    """17-19s: CTA."""
    img  = Image.fromarray(grad_bg())
    draw = ImageDraw.Draw(img)

    e = ease_out(t, 0.5)

    lf = get_font(int(88*e), bold=True)
    lw = tw(draw, PAGE_NAME, lf)
    draw.text((W//2-lw//2, H//2-180), PAGE_NAME, font=lf, fill=GOLD)

    if t > 0.6:
        ce = ease_out(t-0.6, 0.5)
        lines = ["Aisi aur stocks ki kahani",
                 "dekhne ke liye Follow karein!"]
        y = H//2 - 40
        for line in lines:
            f = get_font(int(44*ce))
            draw.text((cx(draw, line, f), y), line, font=f, fill=WHITE)
            y += 60

    if t > 1.2:
        be = ease_out(t-1.2, 0.4)
        bw, bh = 340, 72
        bx, by = W//2-bw//2, H//2+120
        draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=36, fill=RED)
        sub = "SUBSCRIBE"
        sf  = get_font(int(38*be), bold=True)
        draw.text((bx+(bw-tw(draw,sub,sf))//2, by+(bh-38)//2),
                  sub, font=sf, fill=WHITE)

    draw.rectangle([0, H-6, W, H], fill=GOLD)
    return np.array(img)


# ── Main ───────────────────────────────────────────────────────

def create_investment_reel(display_name, ticker, output_path):
    print(f"  Stock: {display_name} ({ticker})")

    # Fetch data
    print("  Fetching historical data...")
    data = fetch_investment_data(ticker)
    if not data:
        print(f"  [!] Could not fetch data for {ticker}")
        return False

    data["display_name"] = display_name
    years = data["years"]
    print(f"  Data: {data['start_date'].date()} → {data['end_date'].date()}")
    print(f"  Rs 1L → {fmt_money(data['end_value'])} | CAGR: {data['cagr']:.1f}%")

    chart_cache = {}

    def make_clip(fn, dur, **kw):
        return VideoClip(lambda t: fn(t, **kw).astype(np.uint8),
                         duration=dur).with_fps(FPS)

    print("  Rendering sections...")
    clips = [
        make_clip(f_hook,   2.0,  name=display_name, years=years),
        make_clip(f_chart,  10.0, data=data, chart_cache=chart_cache),
        make_clip(f_result, 5.0,  data=data),
        make_clip(f_outro,  2.0),
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
        except Exception as e:
            print(f"  [!] Music error: {e}")

    print("  Writing video...")
    video.write_videofile(output_path, fps=FPS, codec="libx264",
                          audio_codec="aac", temp_audiofile="temp_inv_audio.m4a",
                          remove_temp=True, logger=None, preset="ultrafast")
    print(f"  [✓] Saved -> {output_path}")
    return True
