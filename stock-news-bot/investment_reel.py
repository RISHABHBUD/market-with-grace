"""
Investment Reel v2 - Neon cinematic redesign.
Concept unchanged: Rs 1 lakh invested over ~10 years, but with
an entirely fresh visual language and motion style.
"""

import math
import os
import random
from datetime import datetime, timedelta
from io import BytesIO

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import yfinance as yf
from matplotlib.collections import LineCollection
from moviepy import AudioFileClip, CompositeAudioClip, VideoClip, concatenate_videoclips
from moviepy.audio.AudioClip import AudioArrayClip
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from config import PAGE_HANDLE, PAGE_NAME

matplotlib.use("Agg")

W, H, FPS = 1080, 1920, 30
MUSIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music")

# New palette: deep midnight + neon accents.
C_BG_TOP = (9, 8, 30)
C_BG_BOT = (22, 12, 52)
C_PANEL = (22, 28, 58)
C_TEXT = (236, 239, 255)
C_MUTED = (142, 153, 196)
C_CYAN = (32, 224, 255)
C_VIOLET = (154, 106, 255)
C_GOLD = (255, 210, 92)
C_GREEN = (0, 243, 146)
C_RED = (255, 80, 122)
EFFECT_INTENSITY = 1.0


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def progress(t, start, end):
    return clamp((t - start) / (end - start)) if end > start else float(t >= start)


def ease_out3(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_out5(t):
    t = clamp(t)
    return 1 - (1 - t) ** 5


def ease_in2(t):
    t = clamp(t)
    return t * t


def ease_io(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def spring(t, s=9.0, d=0.5):
    t = clamp(t)
    if t in (0, 1):
        return t
    return 1 + math.exp(-d * s * t) * math.cos(s * t * 1.55)


def lerp(a, b, t):
    return a + (b - a) * clamp(t)


def lerp_col(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


def font(size, bold=False):
    candidates = (
        ["arialbd.ttf", "Arial_Bold.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf"]
    )
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def tw(d, txt, f):
    b = d.textbbox((0, 0), txt, font=f)
    return b[2] - b[0]


def th(d, txt, f):
    b = d.textbbox((0, 0), txt, font=f)
    return b[3] - b[1]


def cx(d, txt, f, w=W):
    return (w - tw(d, txt, f)) // 2


def fmt_money_ascii(v):
    if v >= 1e7:
        return f"Rs {v / 1e7:.2f} Cr"
    if v >= 1e5:
        return f"Rs {v / 1e5:.2f} L"
    return f"Rs {v:,.0f}"


def make_base_canvas(t=0.0, tint=None):
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        arr[y] = lerp_col(C_BG_TOP, C_BG_BOT, y / H)
    img = Image.fromarray(arr)
    d = ImageDraw.Draw(img)

    # Diagonal light sweeps.
    for i in range(6):
        x = int((W * 0.18 * i + (t * 130) % (W * 1.2)) - W * 0.2)
        d.polygon(
            [(x, 0), (x + 120, 0), (x - 260, H), (x - 380, H)],
            fill=(40, 30, 82, 36),
        )

    # Grain for cinematic texture.
    rng = np.random.default_rng(int(t * 1000) + 99)
    noise = rng.integers(0, 22, size=(H, W), dtype=np.uint8)
    layer = Image.fromarray(noise, mode="L").convert("RGB")
    img = ImageChops.screen(img, layer)

    # Optional directional tint.
    if tint:
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        for r in range(8, 0, -1):
            rad = 210 + r * 70
            alpha = int(20 * (r / 8))
            od.ellipse([W - rad - 60, 80 - rad, W + rad - 60, 80 + rad], fill=(*tint, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

    return img


def draw_hud_grid(img, t, alpha=36):
    d = ImageDraw.Draw(img)
    step = 120
    x_shift = int((t * 40) % step)
    y_shift = int((t * 26) % step)
    for x in range(-step, W + step, step):
        d.line([(x + x_shift, 0), (x + x_shift, H)], fill=(70, 86, 145, alpha), width=1)
    for y in range(-step, H + step, step):
        d.line([(0, y + y_shift), (W, y + y_shift)], fill=(70, 86, 145, alpha), width=1)
    return img


def draw_soft_glow(img, x, y, radius, color):
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for r in range(7, 0, -1):
        rr = radius + (7 - r) * 24
        aa = int(80 * r / 7)
        od.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(*color, aa))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def draw_glow_text(img, txt, f, x, y, color, glow):
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for r in [8, 5, 3]:
        od.text((x, y), txt, font=f, fill=(*glow, 85 // max(1, r // 2)))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(img)
    d.text((x, y), txt, font=f, fill=color)
    return img


def draw_cracker_burst(img, cx0, cy0, t, duration, color, seed=1, intensity=80):
    """Firecracker-style radial particles."""
    p = progress(t, 0.0, duration)
    if p <= 0:
        return img
    rng = random.Random(seed)
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    scaled = max(6, int(intensity * (0.75 + 0.55 * EFFECT_INTENSITY)))
    for _ in range(scaled):
        ang = rng.uniform(0, math.tau)
        max_dist = rng.uniform(90, 420)
        dist = max_dist * ease_out3(p)
        px = int(cx0 + math.cos(ang) * dist)
        py = int(cy0 + math.sin(ang) * dist * 0.75)
        r = rng.randint(2, 7)
        alpha = int(255 * (1 - p) * rng.uniform(0.45, 1.0))
        col = color if rng.random() > 0.35 else C_GOLD
        od.ellipse([px - r, py - r, px + r, py + r], fill=(*col, alpha))
        if rng.random() > 0.82:
            # Spark streaks.
            sx = int(px + math.cos(ang) * rng.uniform(10, 26))
            sy = int(py + math.sin(ang) * rng.uniform(10, 26))
            od.line([(px, py), (sx, sy)], fill=(*col, alpha), width=2)
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def draw_bubble_field(img, box, t, color, seed=11, count=16):
    """Floating bubble particles for celebratory card moments."""
    x1, y1, x2, y2 = box
    rng = random.Random(seed)
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    scaled_count = max(4, int(count * (0.8 + 0.5 * EFFECT_INTENSITY)))
    for i in range(scaled_count):
        bx = rng.uniform(x1 - 20, x2 + 20)
        phase = (t * rng.uniform(0.6, 1.4) + rng.uniform(0, 1)) % 1.0
        by = y2 + 20 - (y2 - y1 + 80) * phase
        rr = rng.uniform(5, 16)
        a = int(130 * (1 - phase) * rng.uniform(0.5, 1.0))
        od.ellipse([bx - rr, by - rr, bx + rr, by + rr], outline=(*color, a), width=2)
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def add_subtle_vignette(img, strength=0.10):
    """Darken edges slightly to focus viewer attention near center."""
    arr = np.asarray(img).astype(np.float32)
    yy, xx = np.indices((arr.shape[0], arr.shape[1]))
    cx0 = arr.shape[1] / 2.0
    cy0 = arr.shape[0] / 2.0
    dx = (xx - cx0) / (arr.shape[1] / 2.0)
    dy = (yy - cy0) / (arr.shape[0] / 2.0)
    r = np.sqrt(dx * dx + dy * dy)
    # 0 near center, 1 near edges/corners.
    edge = np.clip((r - 0.22) / 0.95, 0.0, 1.0)
    mask = 1.0 - (strength * edge * edge)
    arr = arr * mask[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")


def detect_music_bpm(audio_clip, duration_limit=45, sample_rate=11025):
    """Estimate BPM via envelope autocorrelation."""
    try:
        sample_dur = min(float(audio_clip.duration), float(duration_limit))
        if sample_dur < 5:
            return 120
        arr = audio_clip.subclipped(0, sample_dur).to_soundarray(fps=sample_rate)
        mono = arr.mean(axis=1) if arr.ndim > 1 else arr
        env = np.abs(mono)
        # Smooth envelope to emphasize beats.
        win = max(16, int(sample_rate * 0.045))
        kernel = np.ones(win, dtype=np.float32) / win
        env = np.convolve(env, kernel, mode="same")
        env = env - np.mean(env)
        if np.allclose(env.std(), 0):
            return 120

        ac = np.correlate(env, env, mode="full")
        ac = ac[len(ac) // 2 :]
        min_bpm, max_bpm = 72, 170
        min_lag = int(sample_rate * 60 / max_bpm)
        max_lag = int(sample_rate * 60 / min_bpm)
        if max_lag >= len(ac):
            max_lag = len(ac) - 1
        if min_lag >= max_lag:
            return 120
        segment = ac[min_lag:max_lag]
        best = int(np.argmax(segment)) + min_lag
        bpm = 60 * sample_rate / max(1, best)
        bpm = int(round(clamp(bpm / 200, 0.35, 0.95) * 200))
        return max(min_bpm, min(max_bpm, bpm))
    except Exception:
        return 120


def make_micro_sfx(duration, bpm, milestone_times=None, sample_rate=44100):
    """Create subtle cinematic SFX layer (no beat ticks)."""
    n = int(duration * sample_rate)
    sig = np.zeros(n, dtype=np.float32)

    def add_click(t0, amp=0.028, freq=1150, length=0.08):
        i0 = int(t0 * sample_rate)
        i1 = min(n, i0 + int(length * sample_rate))
        if i0 >= n or i1 <= i0:
            return
        tt = np.arange(i1 - i0) / sample_rate
        env = np.exp(-tt * 38)
        tone = np.sin(2 * math.pi * freq * tt) + 0.45 * np.sin(2 * math.pi * freq * 1.6 * tt)
        sig[i0:i1] += amp * tone * env

    def add_noise_burst(t0, amp=0.038, length=0.16):
        i0 = int(t0 * sample_rate)
        i1 = min(n, i0 + int(length * sample_rate))
        if i0 >= n or i1 <= i0:
            return
        tt = np.arange(i1 - i0) / sample_rate
        env = np.exp(-tt * 24)
        noise = np.random.default_rng(i0 + 91).normal(0, 1, size=i1 - i0).astype(np.float32)
        sig[i0:i1] += amp * noise * env

    # Only milestone sparkle bursts + very light section whooshes.
    for t0 in [2.9, 13.9, 20.9]:
        add_noise_burst(t0, amp=0.02, length=0.20)
        add_click(t0 + 0.03, amp=0.015, freq=1200, length=0.07)

    for mt in milestone_times or []:
        add_noise_burst(mt, amp=0.026)
        add_click(mt + 0.03, amp=0.016, freq=1500, length=0.05)

    sig = np.clip(sig, -0.16, 0.16)
    stereo = np.stack([sig, sig], axis=1)
    return AudioArrayClip(stereo, fps=sample_rate)


def fetch_data(ticker, years=10):
    for sym in [ticker, ticker.replace(".NS", ".BO")]:
        try:
            hist = yf.Ticker(sym).history(period="max")
            if hist.empty or len(hist) < 100:
                continue
            cutoff = datetime.now() - timedelta(days=years * 365)
            h2 = hist[hist.index >= cutoff.strftime("%Y-%m-%d")]
            if len(h2) < 50:
                h2 = hist
            if h2.empty:
                continue
            sp = h2["Close"].iloc[0]
            inv = 100000
            vals = [(d, (r["Close"] / sp) * inv) for d, r in h2.iterrows()]
            # Filter out NaN values
            vals = [(d, v) for d, v in vals if not (v != v)]  # NaN check
            if len(vals) < 10:
                continue
            sd, ed = h2.index[0], h2.index[-1]
            ev = vals[-1][1]
            cagr = ((ev / inv) ** (1 / max((ed - sd).days / 365, 1)) - 1) * 100
            return {
                "sym": sym,
                "vals": vals,
                "sp": sp,
                "ep": h2["Close"].iloc[-1],
                "sd": sd,
                "ed": ed,
                "inv": inv,
                "ev": ev,
                "cagr": cagr,
                "yrs": (ed - sd).days / 365,
            }
        except Exception as e:
            print(f"  [!] {sym}: {e}")
    return None


def milestones(inv, ev):
    return [m for m in [2, 3, 5, 10, 15, 20, 30, 50] if ev >= inv * m]


def make_chart(data, reveal=1.0, w=980, h=900):
    vals = data["vals"]
    n = max(2, int(len(vals) * reveal))
    shown = vals[:n]
    all_d = [v[0] for v in vals]
    all_p = [v[1] for v in vals]
    dates = [v[0] for v in shown]
    prices = [v[1] for v in shown]

    inv = data["inv"]
    up = prices[-1] >= inv
    accent = np.array([0 / 255, 243 / 255, 146 / 255]) if up else np.array([1.0, 80 / 255, 122 / 255])

    fig, ax = plt.subplots(figsize=(w / 100, h / 100), dpi=100)
    fig.patch.set_facecolor("#0A0B1D")
    ax.set_facecolor("#111530")
    ax.set_xlim(all_d[0], all_d[-1])
    ax.set_ylim(min(all_p) * 0.84, max(all_p) * 1.1)

    x = mdates.date2num(dates)
    y = np.array(prices)
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segs = np.concatenate([points[:-1], points[1:]], axis=1) if len(points) > 1 else None

    if segs is not None:
        colors = []
        for i in range(len(segs)):
            t = i / max(1, len(segs) - 1)
            c = accent * (0.5 + 0.5 * t) + np.array([0.25, 0.25, 0.45]) * (1 - t)
            colors.append((*c, 1.0))
        lc = LineCollection(segs, colors=colors, linewidths=4.8, capstyle="round", zorder=6)
        ax.add_collection(lc)
        for lw, alpha in [(20, 0.05), (12, 0.08), (7, 0.13)]:
            ax.plot(dates, prices, lw=lw, color=tuple(accent), alpha=alpha, solid_capstyle="round", zorder=5)

        ax.fill_between(dates, prices, min(all_p) * 0.84, color=tuple(accent), alpha=0.12, zorder=2)

    ax.axhline(y=inv, color="#FFFFFF", lw=1.2, ls="--", alpha=0.22, zorder=1)
    for m in milestones(inv, data["ev"]):
        target = inv * m
        if target <= max(prices):
            ax.axhline(y=target, color="#FFFFFF", lw=0.8, ls=":", alpha=0.12, zorder=1)

    tip_x, tip_y = dates[-1], prices[-1]
    # Premium tip tracker: glow ring + white core + small Rs badge.
    ax.scatter([tip_x], [tip_y], s=760, color=tuple(accent), alpha=0.12, zorder=6)
    ax.scatter([tip_x], [tip_y], s=300, color=tuple(accent), alpha=0.26, zorder=7)
    ax.scatter([tip_x], [tip_y], s=98, color="#F4F8FF", edgecolors=tuple(accent), linewidths=2.2, zorder=8)
    ax.annotate(
        "Rs",
        xy=(tip_x, tip_y),
        xytext=(12, -16),
        textcoords="offset points",
        fontsize=9,
        fontweight="bold",
        ha="center",
        va="center",
        color="#0E1230",
        bbox=dict(boxstyle="round,pad=0.22", fc="#DFFBFF", ec="none", alpha=0.95),
        zorder=9,
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#3B4372")
    ax.spines["bottom"].set_color("#3B4372")
    ax.tick_params(colors="#C7D1FF", labelsize=11, length=0)
    ax.grid(axis="y", color="#2A3158", lw=0.7, alpha=0.55)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    def _fmt(v, _):
        if v >= 1e7:
            return f"Rs{v/1e7:.0f}Cr"
        if v >= 1e5:
            return f"Rs{v/1e5:.0f}L"
        return f"Rs{v:,.0f}"

    ax.yaxis.set_major_formatter(plt.FuncFormatter(_fmt))
    plt.subplots_adjust(left=0.13, right=0.98, top=0.96, bottom=0.09)
    buf = BytesIO()
    plt.savefig(buf, format="png", facecolor="#0A0B1D", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def frame_intro(t, name, years, total=3.0):
    p = ease_out5(progress(t, 0, total))
    img = make_base_canvas(t, tint=C_VIOLET)
    img = draw_hud_grid(img, t, alpha=24)
    d = ImageDraw.Draw(img)

    # Orbital ring.
    for i in range(3):
        rot = int((t * 90 + i * 120) % 360)
        rad = 220 + i * 48
        box = [W // 2 - rad, H // 2 - 260 - rad, W // 2 + rad, H // 2 - 260 + rad]
        d.arc(box, start=rot, end=rot + 250, fill=(*C_CYAN, 150), width=3)
        d.arc(box, start=rot + 120, end=rot + 300, fill=(*C_VIOLET, 130), width=2)

    # Strong first 1.5s hook.
    hook_p = progress(t, 0.0, 1.5)
    if hook_p < 1:
        band_y = int(186 - 36 * (1 - ease_out3(hook_p)))
        d.rounded_rectangle([86, band_y, W - 86, band_y + 92], radius=28, fill=(16, 18, 44))
        d.rectangle([86, band_y, W - 86, band_y + 8], fill=C_CYAN)
        hook = "CAN Rs 1 LAKH BECOME A FORTUNE?"
        d.text((cx(d, hook, font(34, True)), band_y + 26), hook, font=font(34, True), fill=C_TEXT)
        # Beat punch around the hook strip.
        d.rounded_rectangle([74, band_y - 10, W - 74, band_y + 102], radius=30, outline=(64, 180, 210, 130), width=2)

    f1 = font(38, bold=True)
    f2 = font(96, bold=True)
    f3 = font(52, bold=True)
    f4 = font(34)

    line1 = "IF YOU INVESTED"
    line2 = "Rs 1 LAKH"
    line3 = name.upper()
    line4 = f"{int(years)} YEAR MARKET JOURNEY"

    y0 = int(430 - 22 * (1 - p))
    img = draw_glow_text(img, line1, f1, cx(d, line1, f1), y0, C_TEXT, C_CYAN)
    img = draw_glow_text(img, line2, f2, cx(d, line2, f2), y0 + 84, C_GOLD, C_GOLD)
    img = draw_glow_text(img, line3, f3, cx(d, line3, f3), y0 + 238, C_TEXT, C_VIOLET)
    d = ImageDraw.Draw(img)
    d.text((cx(d, line4, f4), y0 + 322), line4, font=f4, fill=(*C_MUTED, 220))

    # Branded footer.
    d.rounded_rectangle([56, H - 156, W - 56, H - 62], radius=26, fill=(18, 20, 42))
    d.rectangle([56, H - 156, W - 56, H - 150], fill=C_CYAN)
    d.text((88, H - 134), PAGE_NAME, font=font(38, bold=True), fill=C_TEXT)
    d.text((W - 88 - tw(d, PAGE_HANDLE, font(30)), H - 126), PAGE_HANDLE, font=font(30), fill=C_MUTED)
    return np.array(img)


def frame_chart(t, data, cache, total=11.0):
    reveal = ease_io(progress(t, 0, total * 0.94))
    n_shown = max(1, int(len(data["vals"]) * reveal))
    cur_val = data["vals"][n_shown - 1][1]
    up = cur_val >= data["inv"]
    accent = C_GREEN if up else C_RED
    tint = C_CYAN if up else C_VIOLET

    img = make_base_canvas(t, tint=tint)
    img = draw_hud_grid(img, t, alpha=30)
    img = draw_soft_glow(img, W - 120, 180, 180, tint)
    d = ImageDraw.Draw(img)
    img = add_subtle_vignette(img, strength=0.10)
    d = ImageDraw.Draw(img)

    # Header bar.
    hdr = [46, 42, W - 46, 214]
    d.rounded_rectangle(hdr, radius=28, fill=(20, 24, 52))
    d.rounded_rectangle([hdr[0], hdr[1], hdr[2], hdr[1] + 8], radius=28, fill=C_CYAN)
    title = data.get("dn", data["sym"].replace(".NS", ""))
    subtitle = f"{data['sd'].year} - {data['ed'].year} | Rs 1 Lakh Simulation"
    d.text((74, 70), title, font=font(52, bold=True), fill=C_TEXT)
    d.text((74, 140), subtitle, font=font(30), fill=C_MUTED)

    chart_y = 238
    cw, ch = W - 80, 1040
    key = int(reveal * 220)
    if key not in cache:
        cache[key] = make_chart(data, reveal=reveal, w=cw, h=ch)
    chart = cache[key].resize((cw, ch), Image.LANCZOS)
    d.rounded_rectangle([40, chart_y - 12, W - 40, chart_y + ch + 12], radius=30, fill=(11, 12, 30))
    # Dynamic camera path with tip lock-on (no perspective distortion).
    cam_zoom = 1.04 - 0.02 * reveal
    zw, zh = int(cw * cam_zoom), int(ch * cam_zoom)
    zchart = chart.resize((zw, zh), Image.LANCZOS)
    pan_x = int((reveal - 0.5) * (44 + 14 * EFFECT_INTENSITY) + math.sin(t * 0.85) * (8 + 5 * EFFECT_INTENSITY))
    pan_y = int((0.5 - reveal) * (34 + 12 * EFFECT_INTENSITY) + math.sin(t * 0.52) * (6 + 3 * EFFECT_INTENSITY))

    # Tip lock-on: gently keeps current chart tip in visual focus as line advances.
    all_prices = [v[1] for v in data["vals"]]
    ymin = min(all_prices) * 0.84
    ymax = max(all_prices) * 1.10
    tip_x_ratio = (n_shown - 1) / max(1, len(data["vals"]) - 1)
    tip_y_ratio = clamp((cur_val - ymin) / max(1e-9, (ymax - ymin)))
    tip_px = int(tip_x_ratio * zw)
    tip_py = int((1.0 - tip_y_ratio) * zh)
    target_x = int(cw * 0.76)
    target_y = int(ch * 0.34)
    lock_x = tip_px - target_x
    lock_y = tip_py - target_y
    lock_strength = progress(reveal, 0.16, 0.42) * (1.0 - progress(reveal, 0.9, 1.0))

    ox_base = (zw - cw) // 2 + pan_x
    oy_base = (zh - ch) // 2 + pan_y
    ox = int(lerp(ox_base, lock_x, lock_strength))
    oy = int(lerp(oy_base, lock_y, lock_strength))
    ox = max(0, min(zw - cw, ox))
    oy = max(0, min(zh - ch, oy))
    img.paste(zchart.crop((ox, oy, ox + cw, oy + ch)), (40, chart_y))
    d = ImageDraw.Draw(img)

    # Live counter and multiplier.
    value_txt = fmt_money_ascii(cur_val)
    val_f = font(82, bold=True)
    d.text((cx(d, value_txt, val_f), 1348), value_txt, font=val_f, fill=accent)
    d.text((cx(d, "CURRENT VALUE", font(28, True)), 1312), "CURRENT VALUE", font=font(28, True), fill=C_MUTED)

    mult = cur_val / data["inv"]
    mult_txt = f"{mult:.2f}x"
    bubble_w = tw(d, mult_txt, font(62, True)) + 78
    bx = (W - bubble_w) // 2
    by = 1460
    d.rounded_rectangle([bx, by, bx + bubble_w, by + 108], radius=54, fill=(28, 34, 70))
    d.rounded_rectangle([bx, by, bx + bubble_w, by + 6], radius=54, fill=accent)
    mult_f = font(62, True)
    d.text((bx + 40, by + 20), mult_txt, font=mult_f, fill=accent)

    # Milestone flash + crackers.
    for m in milestones(data["inv"], data["ev"]):
        target = data["inv"] * m
        for i, (_, v) in enumerate(data["vals"]):
            if v >= target:
                frac = i / max(1, len(data["vals"]) - 1)
                fp = progress(reveal, frac, frac + 0.12)
                if 0 < fp < 1:
                    alpha = int(120 * (1 - fp))
                    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
                    od = ImageDraw.Draw(ov)
                    od.rectangle([0, 0, W, H], fill=(*accent, alpha))
                    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
                    d = ImageDraw.Draw(img)
                    tag = f"{m}x UNLOCKED"
                    d.text((cx(d, tag, font(108, True)), H // 2 - 94), tag, font=font(108, True), fill=C_TEXT)
                    burst_t = fp * 0.75
                    img = draw_cracker_burst(img, W // 2 - 240, H // 2 - 10, burst_t, 0.6, accent, seed=91 + m, intensity=90)
                    img = draw_cracker_burst(img, W // 2 + 240, H // 2 - 10, burst_t, 0.6, C_GOLD, seed=131 + m, intensity=90)
                    d = ImageDraw.Draw(img)
                break

    # Tighter suspense: short, punchy end zoom handoff.
    end_p = progress(t, total * 0.95, total)
    if end_p > 0:
        ze = ease_out5(end_p)
        val_now = fmt_money_ascii(cur_val if reveal < 1 else data["ev"])
        size = int(82 + 110 * ze)
        vf = font(size, True)
        fade = Image.new("RGBA", img.size, (0, 0, 0, int(210 * ze)))
        img = Image.alpha_composite(img.convert("RGBA"), fade).convert("RGB")
        d = ImageDraw.Draw(img)
        d.text((cx(d, val_now, vf), H // 2 - size // 2), val_now, font=vf, fill=accent)
        sub = "FINAL NUMBER REVEAL"
        d.text((cx(d, sub, font(34, True)), H // 2 + size // 2 + 24), sub, font=font(34, True), fill=C_GOLD)

    d.text((cx(d, PAGE_NAME, font(32, True)), H - 64), PAGE_NAME, font=font(32, True), fill=C_TEXT)
    return np.array(img)


def frame_result(t, data, total=7.0):
    img = make_base_canvas(t, tint=C_GOLD)
    img = draw_hud_grid(img, t, alpha=26)
    d = ImageDraw.Draw(img)
    up = data["ev"] >= data["inv"]
    accent = C_GREEN if up else C_RED

    # Smooth carry-over from chart zoom.
    if t < 0.9:
        p_in = ease_out5(progress(t, 0.0, 0.9))
        hold_val = fmt_money_ascii(data["ev"])
        size = int(176 - 102 * p_in)
        vf = font(size, True)
        fade = Image.new("RGBA", img.size, (0, 0, 0, int(190 * (1 - p_in))))
        img = Image.alpha_composite(img.convert("RGBA"), fade).convert("RGB")
        d = ImageDraw.Draw(img)
        d.text((cx(d, hold_val, vf), H // 2 - size // 2 - 60), hold_val, font=vf, fill=accent)
        d.text((cx(d, "LOCKED RESULT", font(34, True)), H // 2 + 78),
               "LOCKED RESULT", font=font(34, True), fill=C_GOLD)

    # Hero text.
    hdr_f = font(40, True)
    name_f = font(64, True)
    d.text((cx(d, "RESULT DASHBOARD", hdr_f), 84), "RESULT DASHBOARD", font=hdr_f, fill=C_TEXT)
    d.text((cx(d, data.get("dn", data["sym"]), name_f), 142), data.get("dn", data["sym"]), font=name_f, fill=C_GOLD)

    cards = [
        ("INVESTED", "Rs 1 Lakh", C_CYAN),
        ("FINAL VALUE", fmt_money_ascii(data["ev"]), accent),
        ("DURATION", f"{data['yrs']:.1f} Years", C_VIOLET),
        ("CAGR", f"{data['cagr']:.1f}%", C_GOLD),
        ("TOTAL RETURN", f"{((data['ev'] / data['inv']) - 1) * 100:.0f}%", accent),
    ]

    # Sequential reveal then all grid.
    show_grid_at = 4.0
    if t < show_grid_at:
        idx = min(len(cards) - 1, max(0, int((t / show_grid_at) * len(cards))))
        lbl, val, color = cards[idx]
        pop = clamp(spring(progress(t % 0.8, 0.0, 0.65), 11, 0.48))
        s = int(700 * max(0.62, min(1.02, pop)))
        x = (W - s) // 2
        y = H // 2 - s // 2 + 110
        d.rounded_rectangle([x, y, x + s, y + s], radius=34, fill=(20, 24, 56))
        d.rounded_rectangle([x, y, x + s, y + 10], radius=34, fill=color)
        d.text((x + 42, y + 44), lbl, font=font(int(46 * (s / 700)), True), fill=C_TEXT)
        vf = font(int(82 * (s / 700)), True)
        d.text((x + (s - tw(d, val, vf)) // 2, y + s // 2 - 28), val, font=vf, fill=color)
        if lbl in ("CAGR", "TOTAL RETURN"):
            burst_local_t = (t % 0.8)
            img = draw_cracker_burst(img, W // 2 - 190, y + s // 2, burst_local_t, 0.7, color, seed=777 + idx, intensity=95)
            img = draw_cracker_burst(img, W // 2 + 190, y + s // 2, burst_local_t, 0.7, C_GOLD, seed=888 + idx, intensity=95)
            d = ImageDraw.Draw(img)
    else:
        p = ease_out3(progress(t, show_grid_at, total))
        gw, gh = 470, 360
        gap = 24
        start_x = (W - (gw * 2 + gap)) // 2
        start_y = int(500 + (1 - p) * 36)
        grid_cards = cards[1:]
        for i, (lbl, val, color) in enumerate(grid_cards):
            r = i // 2
            c = i % 2
            x = start_x + c * (gw + gap)
            y = start_y + r * (gh + gap)
            d.rounded_rectangle([x, y, x + gw, y + gh], radius=28, fill=(20, 24, 56))
            d.rounded_rectangle([x, y, x + gw, y + 9], radius=28, fill=color)
            d.text((x + 24, y + 28), lbl, font=font(29, True), fill=C_TEXT)
            vf = font(56, True)
            while tw(d, val, vf) > gw - 44 and vf.size > 30:
                vf = font(vf.size - 2, True)
            d.text((x + (gw - tw(d, val, vf)) // 2, y + 154), val, font=vf, fill=color)
            if lbl in ("CAGR", "TOTAL RETURN"):
                img = draw_bubble_field(img, [x, y, x + gw, y + gh], t + i * 0.23, color, seed=200 + i, count=18)
                d = ImageDraw.Draw(img)
                pulse_t = ((t * 0.9 + i * 0.17) % 1.0)
                img = draw_cracker_burst(img, x + gw // 2, y + gh // 2, pulse_t, 0.55, color, seed=430 + i, intensity=52)
                d = ImageDraw.Draw(img)

    d.text((cx(d, PAGE_NAME, font(34, True)), H - 72), PAGE_NAME, font=font(34, True), fill=C_TEXT)
    return np.array(img)


def frame_outro(t, total=2.0):
    p = ease_out5(progress(t, 0.0, total))
    img = make_base_canvas(t, tint=C_CYAN)
    img = draw_hud_grid(img, t, alpha=18)
    img = draw_soft_glow(img, W // 2, H // 2 - 220, 220, C_CYAN)
    d = ImageDraw.Draw(img)

    title = PAGE_NAME
    f_title = font(96, True)
    while tw(d, title, f_title) > W - 100 and f_title.size > 52:
        f_title = font(f_title.size - 2, True)
    img = draw_glow_text(img, title, f_title, cx(d, title, f_title), 460, C_TEXT, C_CYAN)
    d = ImageDraw.Draw(img)
    d.text((cx(d, PAGE_HANDLE, font(42)), 594), PAGE_HANDLE, font=font(42), fill=C_MUTED)

    lines = ["Follow for daily market stories", "Data-driven investing insights"]
    for i, line in enumerate(lines):
        y = int(860 + i * 82 + (1 - p) * 18)
        d.text((cx(d, line, font(46)), y), line, font=font(46), fill=C_TEXT)

    btn_w, btn_h = 440, 94
    bx, by = W // 2 - btn_w // 2, 1110
    d.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=46, fill=C_VIOLET)
    d.text((bx + (btn_w - tw(d, "WATCH NEXT", font(42, True))) // 2, by + 24), "WATCH NEXT", font=font(42, True), fill=C_TEXT)
    return np.array(img)


def create_thumbnail(data, path):
    img = make_base_canvas(0.25, tint=C_CYAN)
    img = draw_hud_grid(img, 0.2, alpha=22)
    img = draw_soft_glow(img, W // 2, 430, 240, C_VIOLET)
    d = ImageDraw.Draw(img)

    name = data.get("dn", data["sym"].replace(".NS", ""))
    value = fmt_money_ascii(data["ev"])
    up = data["ev"] >= data["inv"]
    accent = C_GREEN if up else C_RED

    d.text((cx(d, "Rs 1 LAKH IN", font(52, True)), 132), "Rs 1 LAKH IN", font=font(52, True), fill=C_MUTED)
    d.text((cx(d, name, font(96, True)), 214), name, font=font(96, True), fill=C_TEXT)
    d.text((cx(d, "BECAME", font(52, True)), 364), "BECAME", font=font(52, True), fill=C_MUTED)
    d.text((cx(d, value, font(122, True)), 470), value, font=font(122, True), fill=accent)

    meta = f"{data['yrs']:.0f} Years | CAGR {data['cagr']:.1f}%"
    d.text((cx(d, meta, font(44)), 652), meta, font=font(44), fill=C_GOLD)
    d.rounded_rectangle([42, H - 174, W - 42, H - 52], radius=30, fill=(18, 22, 48))
    d.rectangle([42, H - 174, W - 42, H - 166], fill=C_CYAN)
    d.text((cx(d, PAGE_NAME, font(60, True)), H - 156), PAGE_NAME, font=font(60, True), fill=C_TEXT)
    img.save(path, quality=95)
    print(f"  [✓] Thumbnail -> {path}")


def create_investment_reel(display_name, ticker, output_path):
    global EFFECT_INTENSITY
    print(f"  Stock: {display_name} ({ticker})")
    print("  Fetching data...")
    data = fetch_data(ticker)
    if not data:
        print(f"  [!] No data for {ticker}")
        return False

    data["dn"] = display_name
    total_return_pct = ((data["ev"] / data["inv"]) - 1) * 100
    # Smart intensity mode: ties visual intensity to performance profile.
    intensity_raw = 0.85 + clamp(total_return_pct / 450.0, 0.0, 1.4) + clamp(data["cagr"] / 35.0, 0.0, 0.9) * 0.35
    EFFECT_INTENSITY = clamp(intensity_raw / 1.35, 0.75, 1.45)
    print(
        f"  {data['sd'].date()} -> {data['ed'].date()} | "
        f"{fmt_money_ascii(data['ev'])} | CAGR {data['cagr']:.1f}%"
    )
    print(f"  [i] Smart intensity: {EFFECT_INTENSITY:.2f}")

    thumb = output_path.replace(".mp4", "_thumbnail.jpg")
    create_thumbnail(data, thumb)

    cache = {}

    def clip(fn, dur, **kw):
        return VideoClip(lambda t: fn(t, **kw).astype(np.uint8), duration=dur).with_fps(FPS)

    print("  Rendering redesigned reel...")
    clips = [
        clip(frame_intro, 3.0, name=display_name, years=data["yrs"]),
        clip(frame_chart, 11.0, data=data, cache=cache),
        clip(frame_result, 7.0, data=data),
        clip(frame_outro, 2.0),
    ]
    video = concatenate_videoclips(clips)
    total_duration = sum(c.duration for c in clips)

    # Map milestone events to global timeline for audio sparkle cues.
    milestone_times = []
    for m in milestones(data["inv"], data["ev"]):
        target = data["inv"] * m
        for i, (_, v) in enumerate(data["vals"]):
            if v >= target:
                frac = i / max(1, len(data["vals"]) - 1)
                milestone_times.append(3.0 + frac * 11.0)  # chart starts at 3s, lasts 11s
                break

    mfiles = (
        sorted(
            [f for f in os.listdir(MUSIC_DIR) if f.endswith((".mp3", ".wav"))],
            key=lambda x: "cinematic" in x.lower(),
            reverse=True,
        )
        if os.path.exists(MUSIC_DIR)
        else []
    )
    print(f"  Music: {mfiles}")
    if mfiles:
        try:
            audio = AudioFileClip(os.path.join(MUSIC_DIR, mfiles[0]))
            audio = audio.subclipped(0, min(total_duration, audio.duration))
            detected_bpm = detect_music_bpm(audio)
            print(f"  [i] Music tempo detected: {detected_bpm} BPM")
            sfx = make_micro_sfx(total_duration, detected_bpm, milestone_times=milestone_times)
            # Keep SFX subtle under music.
            mixed = CompositeAudioClip([audio.with_volume_scaled(0.95), sfx.with_volume_scaled(0.60)])
            video = video.with_audio(mixed)
            print("  [✓] Music + micro SFX embedded")
        except Exception as e:
            print(f"  [!] Music error: {e}")
            # Fallback: synthetic SFX only if music processing fails.
            try:
                sfx = make_micro_sfx(total_duration, 120, milestone_times=milestone_times)
                video = video.with_audio(sfx.with_volume_scaled(0.45))
                print("  [i] Fallback SFX-only audio applied")
            except Exception as e2:
                print(f"  [!] SFX fallback error: {e2}")
    else:
        # If no music found, still provide a very light synthetic bed.
        try:
            sfx = make_micro_sfx(total_duration, 120, milestone_times=milestone_times)
            video = video.with_audio(sfx.with_volume_scaled(0.38))
            print("  [i] No music found, using subtle synthetic SFX")
        except Exception as e:
            print(f"  [!] Could not create fallback SFX: {e}")

    print("  Writing video...")
    video.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp_inv.m4a",
        remove_temp=True,
        logger=None,
        preset="medium",       # better compression than ultrafast
        ffmpeg_params=["-crf", "28"],  # quality factor — keeps file under 50MB
    )
    print(f"  [✓] Done -> {output_path}")
    return True
