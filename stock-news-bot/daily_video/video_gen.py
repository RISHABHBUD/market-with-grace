"""
Daily Market Briefing — Video Generator
1920x1080, landscape, 8-10 minutes, dark professional theme.
"""

import os, re, textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO

W, H, FPS = 1920, 1080, 24

# ── Dark professional palette ──────────────────────────────────
BG          = (8,  14,  32)      # deep navy
BG2         = (14, 22,  48)      # slightly lighter navy
CARD        = (20, 30,  60)      # card background
CARD2       = (25, 38,  72)
GOLD        = (255, 195, 50)
GOLD_LIGHT  = (255, 220, 120)
WHITE       = (255, 255, 255)
MUTED       = (140, 155, 185)
GREEN       = (40,  210, 110)
RED         = (230, 60,  80)
ACCENT      = (80,  140, 255)    # blue accent
ACCENT2     = (120, 80,  220)    # purple accent
DIVIDER     = (40,  55,  90)

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
def ease_in(t, d):  return min(t/max(d,0.001),1)**2

def solid_bg(color=BG):
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    arr[:] = color
    return arr

def gradient_bg(top=BG, bottom=BG2):
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        t = y/H
        arr[y] = [int(top[i]+(bottom[i]-top[i])*t) for i in range(3)]
    return arr

def make_chart(prices, change, w=800, h=300, dark=True):
    color = "#28D26E" if change >= 0 else "#E63C50"
    bg    = "#0E1630" if dark else "#FFFFFF"
    fig, ax = plt.subplots(figsize=(w/100, h/100), dpi=100)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor("#141E3C" if dark else "#F5F8FF")
    x = list(range(len(prices)))
    ax.plot(x, prices, color=color, linewidth=2.5, zorder=3)
    ax.fill_between(x, prices, min(prices)*0.998, color=color, alpha=0.2, zorder=2)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#283860"); ax.spines["bottom"].set_color("#283860")
    ax.tick_params(colors="#8090B0", labelsize=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,_: f"{v:,.0f}"))
    ax.grid(axis="y", color="#1E2E50", linewidth=0.6, zorder=1)
    plt.tight_layout(pad=0.3)
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor=bg)
    plt.close(fig); buf.seek(0)
    return Image.open(buf).convert("RGB")

def draw_ticker_bar(draw, data):
    """Bottom ticker bar with Nifty/Sensex."""
    bar_h = 52
    draw.rectangle([0, H-bar_h, W, H], fill=(12, 20, 44))
    draw.rectangle([0, H-bar_h, W, H-bar_h+2], fill=GOLD)
    items = [
        f"NIFTY 50: {data['nifty']['current']:,.0f}  "
        f"({'▲' if data['nifty']['change_pct']>=0 else '▼'}"
        f"{abs(data['nifty']['change_pct']):.2f}%)",
        f"SENSEX: {data['sensex']['current']:,.0f}  "
        f"({'▲' if data['sensex']['change_pct']>=0 else '▼'}"
        f"{abs(data['sensex']['change_pct']):.2f}%)",
        f"StockDev.in  |  Aaj ka Market Update",
    ]
    tf = get_font(24, bold=True)
    x  = 20
    for item in items:
        col = (GREEN if "▲" in item else RED) if ("▲" in item or "▼" in item) else GOLD
        draw.text((x, H-bar_h+14), item, font=tf, fill=col)
        x += tw(draw, item, tf) + 60

def draw_logo_bar(draw):
    """Top logo bar."""
    draw.rectangle([0, 0, W, 70], fill=(10, 18, 40))
    draw.rectangle([0, 68, W, 70], fill=GOLD)
    lf = get_font(36, bold=True)
    draw.text((30, 16), "StockDev.in", font=lf, fill=GOLD)
    tf = get_font(24)
    today = datetime.now().strftime("%d %B %Y")
    draw.text((W - tw(draw, today, tf) - 30, 22), today, font=tf, fill=MUTED)
    draw.text((W//2 - tw(draw,"DAILY MARKET BRIEFING",get_font(26,True))//2, 20),
              "DAILY MARKET BRIEFING", font=get_font(26,True), fill=WHITE)

# ── Section frame builders ─────────────────────────────────────

def make_section_clip(frame_fn, audio_path, **kwargs):
    """Create a clip matching the duration of the audio file."""
    from moviepy import AudioFileClip
    if audio_path and os.path.exists(audio_path):
        audio    = AudioFileClip(audio_path)
        duration = audio.duration + 0.5
    else:
        duration = 8.0
        audio    = None

    clip = VideoClip(lambda t: frame_fn(t, duration=duration, **kwargs).astype(np.uint8),
                     duration=duration).with_fps(FPS)
    if audio:
        clip = clip.with_audio(audio)
    return clip


def f_intro(t, duration=8.0, data=None):
    """Animated intro with logo reveal and particle effect."""
    arr  = gradient_bg(BG, BG2)
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    e = ease_out(t, 1.2)

    # Animated background lines
    for i in range(0, W, 80):
        alpha_line = int(30 + 20 * np.sin(t * 2 + i * 0.05))
        draw.line([(i, 0), (i, H)], fill=(*DIVIDER, alpha_line), width=1)
    for j in range(0, H, 80):
        draw.line([(0, j), (W, j)], fill=(*DIVIDER, 20), width=1)

    # Central glow circle
    r = int(300 * e)
    for layer in range(5, 0, -1):
        lr = r + layer * 30
        alpha = int(15 * layer / 5)
        draw.ellipse([W//2-lr, H//2-lr-50, W//2+lr, H//2+lr-50],
                     fill=(*ACCENT2, alpha))

    # Logo text slides in
    logo    = "StockDev.in"
    tagline = "Aapka Daily Market Saathi"
    lf      = get_font(int(120 * e), bold=True)
    tf2     = get_font(int(48 * e))

    lw = tw(draw, logo, lf)
    ly = int(H//2 - 120 + 60*(1-e))
    # Gold shadow
    draw.text((W//2 - lw//2 + 4, ly + 4), logo, font=lf, fill=(*GOLD, 80))
    draw.text((W//2 - lw//2, ly), logo, font=lf, fill=GOLD)

    tw2 = tw(draw, tagline, tf2)
    ty  = int(H//2 + 40 + 40*(1-e))
    draw.text((W//2 - tw2//2, ty), tagline, font=tf2, fill=WHITE)

    # Date
    if t > 1.5:
        date_e = ease_out(t - 1.5, 0.8)
        today  = datetime.now().strftime("%d %B %Y")
        df     = get_font(32)
        dw     = tw(draw, today, df)
        draw.text((W//2 - dw//2, H//2 + 120), today, font=df, fill=MUTED)

    # Bottom bar
    draw.rectangle([0, H-8, W, H], fill=GOLD)

    return np.array(img)


def f_market(t, duration=15.0, data=None):
    """Market overview section with animated charts."""
    arr  = gradient_bg(BG, BG2)
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    draw_logo_bar(draw)
    draw_ticker_bar(draw, data)

    # Section title
    title = "AAJ KA MARKET"
    tf    = get_font(52, bold=True)
    draw.text((60, 90), title, font=tf, fill=GOLD)
    draw.rectangle([60, 152, 60+tw(draw,title,tf), 156], fill=GOLD)

    e = ease_out(t, 0.8)

    # Nifty card
    n       = data["nifty"]
    chg_col = GREEN if n["change_pct"] >= 0 else RED
    arrow   = "▲" if n["change_pct"] >= 0 else "▼"

    card_x = int(60 + 40*(1-e))
    draw.rounded_rectangle([card_x, 175, card_x+560, 420],
                            radius=16, fill=CARD)
    draw.rounded_rectangle([card_x, 175, card_x+6, 420],
                            radius=16, fill=GOLD)
    draw.text((card_x+24, 188), "NIFTY 50", font=get_font(28,True), fill=MUTED)
    draw.text((card_x+24, 228), f"{n['current']:,.2f}",
              font=get_font(72,True), fill=WHITE)
    chg_str = f"{arrow} {abs(n['change_pct']):.2f}%  ({n['change']:+,.2f})"
    draw.text((card_x+24, 318), chg_str, font=get_font(36,True), fill=chg_col)
    draw.text((card_x+24, 372), f"H: {n['high']:,.0f}   L: {n['low']:,.0f}",
              font=get_font(26), fill=MUTED)

    # Sensex card
    s       = data["sensex"]
    schg    = GREEN if s["change_pct"] >= 0 else RED
    sarrow  = "▲" if s["change_pct"] >= 0 else "▼"
    sx      = int(660 + 40*(1-e))
    draw.rounded_rectangle([sx, 175, sx+560, 420], radius=16, fill=CARD)
    draw.rounded_rectangle([sx, 175, sx+6, 420], radius=16, fill=ACCENT)
    draw.text((sx+24, 188), "SENSEX", font=get_font(28,True), fill=MUTED)
    draw.text((sx+24, 228), f"{s['current']:,.2f}",
              font=get_font(72,True), fill=WHITE)
    draw.text((sx+24, 318),
              f"{sarrow} {abs(s['change_pct']):.2f}%  ({s['change']:+,.2f})",
              font=get_font(36,True), fill=schg)

    # Nifty chart
    if n.get("history") and len(n["history"]) > 3:
        chart = make_chart(n["history"], n["change_pct"], w=760, h=280)
        chart = chart.resize((760, 280), Image.LANCZOS)
        reveal_w = max(4, int(760 * min(t/4.0, 1.0)))
        img.paste(chart.crop((0,0,reveal_w,280)), (1100, 175))

    return np.array(img)


def f_movers(t, duration=20.0, data=None):
    """Top gainers and losers with animated bars."""
    arr  = gradient_bg(BG, BG2)
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    draw_logo_bar(draw)
    draw_ticker_bar(draw, data)

    draw.text((60, 90), "TOP MOVERS", font=get_font(52,True), fill=GOLD)
    draw.rectangle([60, 152, 340, 156], fill=GOLD)

    # Gainers column
    draw.text((60, 175), "TOP GAINERS", font=get_font(32,True), fill=GREEN)
    gainers = data["top_gainers"][:5]
    for i, g in enumerate(gainers):
        e   = ease_out(max(t - i*0.3, 0), 0.6)
        ry  = 225 + i * 140
        bx  = int(60 + 30*(1-e))
        draw.rounded_rectangle([bx, ry, bx+840, ry+120], radius=12, fill=CARD)
        draw.rounded_rectangle([bx, ry, bx+6, ry+120], radius=12, fill=GREEN)
        draw.text((bx+20, ry+12), g["name"][:18], font=get_font(34,True), fill=WHITE)
        draw.text((bx+20, ry+60), f"Rs {g['price']:,.2f}", font=get_font(28), fill=MUTED)
        chg = f"▲ {g['change_pct']:.2f}%"
        draw.text((bx+820-tw(draw,chg,get_font(36,True)), ry+40),
                  chg, font=get_font(36,True), fill=GREEN)
        # Bar
        bar_w = int(800 * min(abs(g["change_pct"])/10, 1.0) * e)
        draw.rounded_rectangle([bx+20, ry+96, bx+20+bar_w, ry+110],
                                radius=4, fill=(*GREEN, 120))

    # Losers column
    draw.text((980, 175), "TOP LOSERS", font=get_font(32,True), fill=RED)
    losers = data["top_losers"][:5]
    for i, l in enumerate(losers):
        e   = ease_out(max(t - i*0.3 - 0.5, 0), 0.6)
        ry  = 225 + i * 140
        bx  = int(980 + 30*(1-e))
        draw.rounded_rectangle([bx, ry, bx+840, ry+120], radius=12, fill=CARD)
        draw.rounded_rectangle([bx, ry, bx+6, ry+120], radius=12, fill=RED)
        draw.text((bx+20, ry+12), l["name"][:18], font=get_font(34,True), fill=WHITE)
        draw.text((bx+20, ry+60), f"Rs {l['price']:,.2f}", font=get_font(28), fill=MUTED)
        chg = f"▼ {abs(l['change_pct']):.2f}%"
        draw.text((bx+820-tw(draw,chg,get_font(36,True)), ry+40),
                  chg, font=get_font(36,True), fill=RED)
        bar_w = int(800 * min(abs(l["change_pct"])/10, 1.0) * e)
        draw.rounded_rectangle([bx+20, ry+96, bx+20+bar_w, ry+110],
                                radius=4, fill=(*RED, 120))

    return np.array(img)

def f_sectors(t, duration=12.0, data=None):
    """Sector performance with animated horizontal bars."""
    arr  = gradient_bg(BG, BG2)
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    draw_logo_bar(draw)
    draw_ticker_bar(draw, data)

    draw.text((60, 90), "SECTOR PERFORMANCE", font=get_font(52,True), fill=GOLD)
    draw.rectangle([60, 152, 520, 156], fill=GOLD)

    sectors = data["sectors"]
    max_abs = max(abs(s["change_pct"]) for s in sectors) if sectors else 1
    bar_max = 700

    for i, sec in enumerate(sectors[:8]):
        e   = ease_out(max(t - i*0.25, 0), 0.7)
        ry  = 185 + i * 108
        col = GREEN if sec["change_pct"] >= 0 else RED

        # Label
        draw.text((60, ry+30), sec["name"], font=get_font(32,True), fill=WHITE)

        # Bar background
        draw.rounded_rectangle([280, ry+28, 280+bar_max, ry+72],
                                radius=8, fill=CARD2)
        # Bar fill
        fill_w = int(bar_max * abs(sec["change_pct"]) / max_abs * e)
        if fill_w > 0:
            draw.rounded_rectangle([280, ry+28, 280+fill_w, ry+72],
                                    radius=8, fill=col)

        # Value
        val = f"{'▲' if sec['change_pct']>=0 else '▼'} {abs(sec['change_pct']):.2f}%"
        draw.text((280+bar_max+20, ry+30), val, font=get_font(30,True), fill=col)

    return np.array(img)


def f_news(t, duration=15.0, data=None):
    """News headlines with card reveal animation."""
    arr  = gradient_bg(BG, BG2)
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    draw_logo_bar(draw)
    draw_ticker_bar(draw, data)

    draw.text((60, 90), "AAJ KI KHABREIN", font=get_font(52,True), fill=GOLD)
    draw.rectangle([60, 152, 440, 156], fill=GOLD)

    news = data["news"][:4]
    for i, item in enumerate(news):
        e   = ease_out(max(t - i*0.5, 0), 0.7)
        ry  = int(185 + i * 200 + 30*(1-e))
        alpha = min(int(255 * e), 255)

        draw.rounded_rectangle([60, ry, W-60, ry+180], radius=14, fill=CARD)
        draw.rounded_rectangle([60, ry, 68, ry+180], radius=14, fill=ACCENT)

        # Number badge
        draw.rounded_rectangle([80, ry+20, 130, ry+70], radius=10, fill=ACCENT)
        draw.text((88, ry+24), str(i+1), font=get_font(36,True), fill=WHITE)

        # Title
        title = re.sub(r"[^\x00-\x7F]+", "", item["title"])[:90]
        draw.text((148, ry+20), title, font=get_font(30,True), fill=WHITE)

        # Summary
        summary = re.sub(r"[^\x00-\x7F]+", "", item.get("summary",""))[:120]
        if summary:
            for j, line in enumerate(textwrap.wrap(summary, width=90)[:2]):
                draw.text((148, ry+68+j*36), line, font=get_font(26), fill=MUTED)

    return np.array(img)


def f_outro(t, duration=8.0, data=None):
    """Outro with subscribe CTA and animation."""
    arr  = gradient_bg(BG, BG2)
    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    e = ease_out(t, 1.0)

    # Background glow
    for layer in range(6, 0, -1):
        r = int(250 * layer / 6 * e)
        draw.ellipse([W//2-r, H//2-r-30, W//2+r, H//2+r-30],
                     fill=(*GOLD, int(8 * layer / 6)))

    # Logo
    lf = get_font(int(100*e), bold=True)
    lw = tw(draw, "StockDev.in", lf)
    draw.text((W//2-lw//2+3, H//2-160+3), "StockDev.in", font=lf, fill=(*GOLD,60))
    draw.text((W//2-lw//2, H//2-160), "StockDev.in", font=lf, fill=GOLD)

    # CTA
    if t > 1.5:
        cta_e = ease_out(t-1.5, 0.8)
        ctas  = ["Like karein  |  Subscribe karein  |  Share karein",
                 "Kal milenge ek naye market update ke saath!"]
        for i, cta in enumerate(ctas):
            cf = get_font(int(36*cta_e), bold=(i==0))
            cw = tw(draw, cta, cf)
            draw.text((W//2-cw//2, H//2+i*60), cta,
                      font=cf, fill=GOLD if i==0 else WHITE)

    # Subscribe button
    if t > 2.5:
        btn_e = ease_out(t-2.5, 0.6)
        bw, bh = 320, 70
        bx, by = W//2-bw//2, H//2+160
        draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=35, fill=RED)
        sub = "SUBSCRIBE"
        sf  = get_font(int(36*btn_e), bold=True)
        draw.text((bx+(bw-tw(draw,sub,sf))//2, by+(bh-36)//2),
                  sub, font=sf, fill=WHITE)

    draw.rectangle([0, H-8, W, H], fill=GOLD)
    return np.array(img)


def fade_transition(clip_a, clip_b, duration=0.5):
    """Simple crossfade between two clips."""
    from moviepy import VideoClip
    total = clip_a.duration + clip_b.duration - duration

    def make_frame(t):
        if t < clip_a.duration - duration:
            return clip_a.get_frame(t)
        elif t > clip_a.duration:
            return clip_b.get_frame(t - clip_a.duration + duration)
        else:
            alpha = (t - (clip_a.duration - duration)) / duration
            fa    = clip_a.get_frame(t)
            fb    = clip_b.get_frame(t - clip_a.duration + duration)
            return (fa * (1-alpha) + fb * alpha).astype(np.uint8)

    return VideoClip(make_frame, duration=total).with_fps(FPS)


def build_video(data, audio_files, output_path):
    """Assemble all sections into final video."""
    print("  Building video sections...")

    sections = [
        ("intro",   f_intro,   audio_files.get("intro")),
        ("market",  f_market,  audio_files.get("market")),
        ("movers",  f_movers,  audio_files.get("movers")),
        ("sectors", f_sectors, audio_files.get("sectors")),
        ("news",    f_news,    audio_files.get("news")),
        ("outro",   f_outro,   audio_files.get("outro")),
    ]

    clips = []
    for name, fn, audio_path in sections:
        print(f"  Rendering {name}...")
        clip = make_section_clip(fn, audio_path, data=data)
        clips.append(clip)

    # Concatenate with crossfades
    print("  Assembling with transitions...")
    final = clips[0]
    for clip in clips[1:]:
        final = concatenate_videoclips([final, clip], method="compose")

    # Add background music at low volume under narration
    music_dir = os.path.join(os.path.dirname(__file__), "..", "music")
    music_files = [f for f in os.listdir(music_dir)
                   if f.endswith((".mp3",".wav"))] if os.path.exists(music_dir) else []
    if music_files:
        import random
        try:
            from moviepy import AudioFileClip, CompositeAudioClip
            bg_music = AudioFileClip(
                os.path.join(music_dir, random.choice(music_files))
            ).with_subclip(0, min(final.duration, 600)).audio_fadeout(3)
            bg_music = bg_music.with_volume_scaled(0.08)  # very low — under narration
            if final.audio:
                from moviepy import CompositeAudioClip
                final = final.with_audio(
                    CompositeAudioClip([final.audio, bg_music])
                )
            else:
                final = final.with_audio(bg_music)
            print("  Background music added")
        except Exception as e:
            print(f"  [!] Music error: {e}")

    print(f"  Writing video ({final.duration:.1f}s)...")
    final.write_videofile(
        output_path, fps=FPS, codec="libx264",
        audio_codec="aac", temp_audiofile="temp_daily_audio.m4a",
        remove_temp=True, logger=None, preset="ultrafast",
        threads=4,
    )
    print(f"  [✓] Video saved -> {output_path}")
    return output_path
