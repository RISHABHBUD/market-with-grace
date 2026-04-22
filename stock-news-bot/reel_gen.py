"""
Stock Spotlight Reel Generator
Creates a 25-second vertical video (1080x1920) for Instagram Reels.

Sections:
  0-3s   : Intro — StockDev.in branding animates in
  3-8s   : Stock name + badge slides in
  8-16s  : Price chart draws itself
  16-22s : Key headline text types in word by word
  22-25s : Outro — CTA + handle
"""

import os
import re
import random
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, VideoFileClip
)
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from config import PAGE_NAME, PAGE_HANDLE

# ── Canvas ─────────────────────────────────────────────────────
W, H   = 1080, 1920
FPS    = 30
DURATION = 25  # seconds

# ── Palette ────────────────────────────────────────────────────
BG_TOP        = (225, 210, 255)
BG_BOTTOM     = (255, 235, 248)
CARD_BG       = (255, 255, 255)
ACCENT        = (150, 100, 215)
ACCENT_LIGHT  = (220, 200, 255)
TEXT_DARK     = (35, 20, 70)
TEXT_MID      = (100, 80, 150)
TEXT_LIGHT    = (170, 145, 200)
GREEN         = (40, 180, 100)
RED           = (220, 60, 80)
WHITE         = (255, 255, 255)
GOLD          = (255, 200, 60)

MUSIC_DIR = os.path.join(os.path.dirname(__file__), "music")


# ── Fonts ──────────────────────────────────────────────────────
def get_font(size, bold=False):
    candidates = (
        ["arialbd.ttf", "Arial_Bold.ttf", "DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold else
        ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ── Gradient background ────────────────────────────────────────
def make_gradient(w, h, top, bottom):
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        t = y / h
        arr[y] = [int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)]
    return arr


# ── PIL helpers ────────────────────────────────────────────────
def pil_to_np(img):
    return np.array(img.convert("RGB"))


def np_frame(arr):
    """Convert numpy array to moviepy-compatible frame."""
    return arr.astype(np.uint8)


def tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def th(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def draw_centered(draw, text, font, y, color, width=W):
    x = (width - tw(draw, text, font)) // 2
    draw.text((x, y), text, font=font, fill=color)


# ── Stock data ─────────────────────────────────────────────────
STOCK_KEYWORDS = {
    "tata steel": "TATASTEEL.NS",
    "reliance": "RELIANCE.NS",
    "infosys": "INFY.NS",
    "hdfc bank": "HDFCBANK.NS",
    "icici bank": "ICICIBANK.NS",
    "wipro": "WIPRO.NS",
    "tcs": "TCS.NS",
    "bajaj": "BAJFINANCE.NS",
    "adani": "ADANIENT.NS",
    "nestle": "NESTLEIND.NS",
    "hcl": "HCLTECH.NS",
    "axis bank": "AXISBANK.NS",
    "kotak": "KOTAKBANK.NS",
    "sbi": "SBIN.NS",
    "maruti": "MARUTI.NS",
    "ola": "OLAELEC.NS",
    "zomato": "ZOMATO.NS",
    "paytm": "PAYTM.NS",
    "vedanta": "VEDL.NS",
    "trent": "TRENT.NS",
    "groww": "GROWW.NS",
    "suzlon": "SUZLON.NS",
}

NIFTY_TICKER = "^NSEI"


def detect_ticker(title):
    title_lower = title.lower()
    for keyword, ticker in STOCK_KEYWORDS.items():
        if keyword in title_lower:
            return ticker
    return None


def fetch_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="30d")
        info  = stock.info
        if hist.empty:
            return None
        current = hist["Close"].iloc[-1]
        prev    = hist["Close"].iloc[-2]
        change  = ((current - prev) / prev) * 100
        name    = info.get("shortName", ticker.replace(".NS", ""))
        return {
            "name":    name,
            "ticker":  ticker.replace(".NS", ""),
            "current": current,
            "change":  change,
            "history": hist["Close"].tolist()[-20:],
        }
    except Exception as e:
        print(f"  [!] Stock data fetch failed: {e}")
        return None


def fetch_nifty_data():
    try:
        nifty = yf.Ticker(NIFTY_TICKER)
        hist  = nifty.history(period="7d")
        if hist.empty:
            return None
        current = hist["Close"].iloc[-1]
        prev    = hist["Close"].iloc[-2]
        change  = ((current - prev) / prev) * 100
        return {
            "name":    "NIFTY 50",
            "ticker":  "NIFTY",
            "current": current,
            "change":  change,
            "history": hist["Close"].tolist(),
        }
    except Exception:
        return None


# ── Chart generator ────────────────────────────────────────────
def make_chart_image(prices, change, width=900, height=420):
    """Generate a clean price chart, return as PIL Image."""
    color = "#28B464" if change >= 0 else "#DC3C50"
    bg    = (255, 255, 255)

    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8F5FF")

    x = list(range(len(prices)))
    ax.plot(x, prices, color=color, linewidth=3, zorder=3)
    ax.fill_between(x, prices, min(prices) * 0.998,
                    color=color, alpha=0.15, zorder=2)

    # Style
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#E0D8F0")
    ax.spines["bottom"].set_color("#E0D8F0")
    ax.tick_params(colors="#A090C0", labelsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"₹{v:,.0f}"))
    ax.grid(axis="y", color="#EDE8F8", linewidth=0.8, zorder=1)

    plt.tight_layout(pad=0.5)

    # Save to PIL
    from io import BytesIO
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


# ── Frame builders ─────────────────────────────────────────────
def build_base_frame():
    """Gradient background as numpy array."""
    return make_gradient(W, H, BG_TOP, BG_BOTTOM)


def frame_intro(t, total=3.0):
    """0-3s: Branding slides down from top."""
    progress = min(t / 1.2, 1.0)
    ease     = 1 - (1 - progress) ** 3  # ease-out cubic

    img  = Image.fromarray(build_base_frame())
    draw = ImageDraw.Draw(img)

    # Decorative circles
    draw.ellipse([W - 200, -100, W + 100, 200], fill=(200, 180, 245))
    draw.ellipse([-100, H - 200, 200, H + 100], fill=(220, 200, 255))

    # Brand card slides in from top
    card_h = 180
    card_y = int(-card_h + (card_h + 120) * ease)
    draw.rounded_rectangle([60, card_y, W - 60, card_y + card_h],
                            radius=28, fill=ACCENT)

    brand_f  = get_font(72, bold=True)
    handle_f = get_font(36)
    tagline_f = get_font(32)

    draw.text(((W - tw(draw, PAGE_NAME, brand_f)) // 2,
               card_y + 28), PAGE_NAME, font=brand_f, fill=WHITE)
    draw.text(((W - tw(draw, PAGE_HANDLE, handle_f)) // 2,
               card_y + 112), PAGE_HANDLE, font=handle_f, fill=ACCENT_LIGHT)

    # "Stock Spotlight" fades in
    alpha = int(255 * min(max((t - 1.5) / 1.0, 0), 1))
    spotlight = "✦ Stock Spotlight ✦"
    sf = get_font(44, bold=True)
    # Draw with manual alpha simulation (blend with bg)
    if alpha > 0:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        color_a = (*TEXT_MID, alpha)
        od.text(((W - tw(od, spotlight, sf)) // 2, 340),
                spotlight, font=sf, fill=color_a)
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    return pil_to_np(img)


def frame_stock_info(t, stock_data, total=5.0):
    """3-8s: Stock name, ticker, price, change badge."""
    progress = min(t / 0.8, 1.0)
    ease     = 1 - (1 - progress) ** 3

    img  = Image.fromarray(build_base_frame())
    draw = ImageDraw.Draw(img)

    # Decorative circles
    draw.ellipse([W - 200, -100, W + 100, 200], fill=(200, 180, 245))
    draw.ellipse([-100, H - 200, 200, H + 100], fill=(220, 200, 255))

    # Brand bar (static at top)
    draw.rounded_rectangle([60, 60, W - 60, 200], radius=24, fill=ACCENT)
    bf = get_font(52, bold=True)
    hf = get_font(30)
    draw.text(((W - tw(draw, PAGE_NAME, bf)) // 2, 80),
              PAGE_NAME, font=bf, fill=WHITE)
    draw.text(((W - tw(draw, PAGE_HANDLE, hf)) // 2, 148),
              PAGE_HANDLE, font=hf, fill=ACCENT_LIGHT)

    # Stock card slides up
    card_y = int(H + (280 - H) * ease)
    card_h = 380
    draw.rounded_rectangle([60, card_y, W - 60, card_y + card_h],
                            radius=32, fill=CARD_BG,
                            outline=(200, 180, 240), width=2)
    # Left accent strip
    draw.rounded_rectangle([60, card_y, 74, card_y + card_h],
                            radius=32, fill=ACCENT)

    name_f    = get_font(68, bold=True)
    ticker_f  = get_font(36)
    price_f   = get_font(80, bold=True)
    change_f  = get_font(44, bold=True)

    name = stock_data["name"][:22]
    draw.text(((W - tw(draw, name, name_f)) // 2,
               card_y + 30), name, font=name_f, fill=TEXT_DARK)

    ticker_label = f"NSE: {stock_data['ticker']}"
    draw.text(((W - tw(draw, ticker_label, ticker_f)) // 2,
               card_y + 112), ticker_label, font=ticker_f, fill=TEXT_LIGHT)

    price_str = f"₹{stock_data['current']:,.2f}"
    draw.text(((W - tw(draw, price_str, price_f)) // 2,
               card_y + 168), price_str, font=price_f, fill=TEXT_DARK)

    # Change badge
    change    = stock_data["change"]
    chg_color = GREEN if change >= 0 else RED
    chg_str   = f"{'▲' if change >= 0 else '▼'} {abs(change):.2f}%  Today"
    chg_w     = tw(draw, chg_str, change_f) + 48
    chg_x     = (W - chg_w) // 2
    draw.rounded_rectangle([chg_x, card_y + 290, chg_x + chg_w, card_y + 350],
                            radius=24, fill=chg_color)
    draw.text((chg_x + 24, card_y + 300), chg_str,
              font=change_f, fill=WHITE)

    return pil_to_np(img)


def frame_chart(t, stock_data, chart_img, total=8.0):
    """8-16s: Chart draws itself (reveal left to right)."""
    img  = Image.fromarray(build_base_frame())
    draw = ImageDraw.Draw(img)

    # Decorative circles
    draw.ellipse([W - 200, -100, W + 100, 200], fill=(200, 180, 245))

    # Brand bar
    draw.rounded_rectangle([60, 60, W - 60, 200], radius=24, fill=ACCENT)
    bf = get_font(52, bold=True)
    hf = get_font(30)
    draw.text(((W - tw(draw, PAGE_NAME, bf)) // 2, 80),
              PAGE_NAME, font=bf, fill=WHITE)
    draw.text(((W - tw(draw, PAGE_HANDLE, hf)) // 2, 148),
              PAGE_HANDLE, font=hf, fill=ACCENT_LIGHT)

    # "30-Day Price Chart" label
    lf = get_font(40, bold=True)
    label = "30-Day Price Chart"
    draw.text(((W - tw(draw, label, lf)) // 2, 240),
              label, font=lf, fill=TEXT_MID)

    # Chart card
    chart_card_y = 310
    chart_card_h = 520
    draw.rounded_rectangle([60, chart_card_y, W - 60, chart_card_y + chart_card_h],
                            radius=24, fill=CARD_BG,
                            outline=(200, 180, 240), width=2)

    # Reveal chart progressively
    reveal = min(t / (total * 0.85), 1.0)
    cw = chart_img.width
    ch = chart_img.height
    target_w = W - 120
    target_h = int(ch * target_w / cw)
    chart_resized = chart_img.resize((target_w, target_h), Image.LANCZOS)

    reveal_w = int(target_w * reveal)
    if reveal_w > 10:
        chart_crop = chart_resized.crop((0, 0, reveal_w, target_h))
        img.paste(chart_crop, (90, chart_card_y + 20))

    # Stock name + price below chart
    nf = get_font(48, bold=True)
    pf = get_font(44)
    change    = stock_data["change"]
    chg_color = GREEN if change >= 0 else RED
    name_str  = stock_data["name"][:20]
    price_str = f"₹{stock_data['current']:,.2f}  {'▲' if change >= 0 else '▼'}{abs(change):.2f}%"

    draw.text(((W - tw(draw, name_str, nf)) // 2, chart_card_y + chart_card_h + 30),
              name_str, font=nf, fill=TEXT_DARK)
    draw.text(((W - tw(draw, price_str, pf)) // 2, chart_card_y + chart_card_h + 92),
              price_str, font=pf, fill=chg_color)

    return pil_to_np(img)


def frame_headline(t, headline, total=6.0):
    """16-22s: Headline types in word by word."""
    img  = Image.fromarray(build_base_frame())
    draw = ImageDraw.Draw(img)

    draw.ellipse([-100, H - 200, 200, H + 100], fill=(220, 200, 255))

    # Brand bar
    draw.rounded_rectangle([60, 60, W - 60, 200], radius=24, fill=ACCENT)
    bf = get_font(52, bold=True)
    hf = get_font(30)
    draw.text(((W - tw(draw, PAGE_NAME, bf)) // 2, 80),
              PAGE_NAME, font=bf, fill=WHITE)
    draw.text(((W - tw(draw, PAGE_HANDLE, hf)) // 2, 148),
              PAGE_HANDLE, font=hf, fill=ACCENT_LIGHT)

    # "What's the news?" label
    lf = get_font(40, bold=True)
    label = "What's the news?"
    draw.text(((W - tw(draw, label, lf)) // 2, 250),
              label, font=lf, fill=TEXT_MID)

    # Headline card
    draw.rounded_rectangle([60, 320, W - 60, H - 200],
                            radius=28, fill=CARD_BG,
                            outline=(200, 180, 240), width=2)
    draw.rounded_rectangle([60, 320, 74, H - 200],
                            radius=28, fill=ACCENT)

    # Type-in effect
    words    = headline.split()
    n_words  = max(1, int(len(words) * min(t / (total * 0.9), 1.0)))
    visible  = " ".join(words[:n_words])
    lines    = textwrap.wrap(visible, width=24)

    hf2 = get_font(56, bold=True)
    y   = 380
    for line in lines[:8]:
        draw.text(((W - tw(draw, line, hf2)) // 2, y),
                  line, font=hf2, fill=TEXT_DARK)
        y += 76

    # Blinking cursor
    if int(t * 2) % 2 == 0 and n_words < len(words):
        draw.rectangle([W // 2 - 4, y, W // 2 + 4, y + 56],
                       fill=ACCENT)

    return pil_to_np(img)


def frame_outro(t, total=3.0):
    """22-25s: CTA + follow prompt."""
    progress = min(t / 0.8, 1.0)
    ease     = 1 - (1 - progress) ** 3

    img  = Image.fromarray(build_base_frame())
    draw = ImageDraw.Draw(img)

    draw.ellipse([W - 200, -100, W + 100, 200], fill=(200, 180, 245))
    draw.ellipse([-100, H - 200, 200, H + 100], fill=(220, 200, 255))

    # Big brand card
    card_y = int(H * 0.25)
    draw.rounded_rectangle([60, card_y, W - 60, card_y + 280],
                            radius=32, fill=ACCENT)
    bf2 = get_font(80, bold=True)
    hf2 = get_font(40)
    draw.text(((W - tw(draw, PAGE_NAME, bf2)) // 2, card_y + 30),
              PAGE_NAME, font=bf2, fill=WHITE)
    draw.text(((W - tw(draw, PAGE_HANDLE, hf2)) // 2, card_y + 130),
              PAGE_HANDLE, font=hf2, fill=ACCENT_LIGHT)

    tagline = "Where markets meet technology ⚡"
    tf = get_font(34)
    draw.text(((W - tw(draw, tagline, tf)) // 2, card_y + 192),
              tagline, font=tf, fill=ACCENT_LIGHT)

    # CTA
    cta_y = card_y + 340
    cta1  = "Follow for daily"
    cta2  = "Stock Market Updates"
    cf1   = get_font(52, bold=True)
    cf2   = get_font(56, bold=True)
    draw.text(((W - tw(draw, cta1, cf1)) // 2, cta_y),
              cta1, font=cf1, fill=TEXT_DARK)
    draw.text(((W - tw(draw, cta2, cf2)) // 2, cta_y + 72),
              cta2, font=cf2, fill=ACCENT)

    # Like + share prompt
    lf = get_font(40)
    like = "Like  •  Share  •  Save"
    draw.text(((W - tw(draw, like, lf)) // 2, cta_y + 180),
              like, font=lf, fill=TEXT_LIGHT)

    # Bottom bar
    draw.rounded_rectangle([60, H - 160, W - 60, H - 60],
                            radius=24, fill=ACCENT)
    bf3 = get_font(38, bold=True)
    tag = "stockdev.in  |  Daily Market Intelligence"
    draw.text(((W - tw(draw, tag, bf3)) // 2, H - 130),
              tag, font=bf3, fill=WHITE)

    return pil_to_np(img)


# ── Main reel builder ──────────────────────────────────────────
def create_reel(article, output_path):
    title = re.sub(r"[^\x00-\x7F]+", "", article["title"]).strip()
    print(f"  Creating reel for: {title[:60]}")

    # Detect stock ticker
    ticker     = detect_ticker(title)
    stock_data = fetch_stock_data(ticker) if ticker else fetch_nifty_data()

    if not stock_data:
        print("  [!] Could not fetch stock data, using Nifty fallback")
        stock_data = {
            "name": "NIFTY 50", "ticker": "NIFTY",
            "current": 24500.0, "change": 0.5,
            "history": [24000 + i * 25 for i in range(20)]
        }

    print(f"  Stock: {stock_data['name']} | ₹{stock_data['current']:,.2f} | {stock_data['change']:+.2f}%")

    # Generate chart
    chart_img = make_chart_image(stock_data["history"], stock_data["change"])

    # Build video clips
    clips = []

    # Intro (0-3s)
    intro = ImageClip(
        np.array([frame_intro(t / FPS) for t in range(int(3 * FPS))]),
        fps=FPS
    ) if False else None  # use make_frame instead

    def make_clip(frame_fn, duration, **kwargs):
        return ImageClip(
            np.array([frame_fn(t / FPS, **kwargs)
                      for t in range(int(duration * FPS))]),
            fps=FPS
        ).set_duration(duration)

    print("  Rendering intro...")
    c1 = make_clip(frame_intro, 3.0)

    print("  Rendering stock info...")
    c2 = make_clip(frame_stock_info, 5.0, stock_data=stock_data)

    print("  Rendering chart...")
    c3 = make_clip(frame_chart, 8.0, stock_data=stock_data, chart_img=chart_img)

    print("  Rendering headline...")
    c4 = make_clip(frame_headline, 6.0, headline=title)

    print("  Rendering outro...")
    c5 = make_clip(frame_outro, 3.0)

    video = concatenate_videoclips([c1, c2, c3, c4, c5])

    # Add music
    music_files = [
        f for f in os.listdir(MUSIC_DIR)
        if f.endswith(".mp3") or f.endswith(".wav")
    ] if os.path.exists(MUSIC_DIR) else []

    if music_files:
        music_path = os.path.join(MUSIC_DIR, random.choice(music_files))
        try:
            audio = AudioFileClip(music_path).subclip(0, DURATION)
            audio = audio.audio_fadeout(2)
            video = video.set_audio(audio)
            print(f"  Music: {os.path.basename(music_path)}")
        except Exception as e:
            print(f"  [!] Music failed: {e}")
    else:
        print("  [!] No music files found in music/ folder")

    # Write video
    print("  Writing video...")
    video.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp_audio.m4a",
        remove_temp=True,
        logger=None,
        preset="ultrafast",
    )
    print(f"  [✓] Reel saved -> {output_path}")
