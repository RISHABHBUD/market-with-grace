"""
Instagram image post generator — cinematic midnight/neon theme.
Matches the visual language of investment_reel.py and reel_gen.py.
"""

import re, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops
from datetime import datetime
from config import PAGE_NAME, PAGE_HANDLE

W, H = 1080, 1080

# ── Cinematic palette ──────────────────────────────────────────
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

def cx(d, txt, f, w=W):
    return (w - tw(d,txt,f)) // 2

def lerp_col(c1, c2, t):
    return tuple(int(c1[i]+(c2[i]-c1[i])*t) for i in range(3))


def make_canvas():
    """Gradient background with diagonal light sweeps + film grain."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        arr[y] = lerp_col(C_BG_TOP, C_BG_BOT, y/H)
    img = Image.fromarray(arr)
    d   = ImageDraw.Draw(img)
    # Diagonal sweeps
    for i in range(5):
        x = int(W*0.2*i - W*0.1)
        d.polygon([(x,0),(x+100,0),(x-220,H),(x-320,H)], fill=(40,30,82,30))
    # Film grain
    rng   = np.random.default_rng(77)
    noise = rng.integers(0,16,size=(H,W),dtype=np.uint8)
    layer = Image.fromarray(noise,"L").convert("RGB")
    img   = ImageChops.screen(img, layer)
    return img


def soft_glow(img, x, y, radius, color):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    od = ImageDraw.Draw(ov)
    for r in range(6,0,-1):
        rr=radius+(6-r)*20; a=int(65*r/6)
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


def fit_lines(d, text, f, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur+" "+w).strip()
        if tw(d,test,f) <= max_w: cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


def create_post_image(article, output_path):
    img = make_canvas()
    img = soft_glow(img, W-80, 80, 160, C_VIOLET)
    d   = ImageDraw.Draw(img)

    title = re.sub(r"[^\x00-\x7F]+","",article["title"]).strip()
    title = re.sub(r"\s*[-|]\s*[A-Z][^\-|]{2,30}$","",title).strip()

    # ── Top header bar ─────────────────────────────────────────
    d.rounded_rectangle([40,40,W-40,168], radius=26, fill=C_PANEL)
    d.rectangle([40,40,W-40,48], fill=C_CYAN)

    # "STOCK NEWS" badge
    bf  = font(28,True)
    blb = "STOCK  NEWS"
    bw  = tw(d,blb,bf)+48
    bx  = (W-bw)//2
    d.rounded_rectangle([bx,58,bx+bw,104], radius=22, fill=(30,36,72))
    d.rectangle([bx,58,bx+bw,64], fill=C_CYAN)
    d.text((bx+24,66), blb, font=bf, fill=C_CYAN)

    # Date
    date = datetime.now().strftime("%d %B %Y")
    df   = font(24)
    d.text((cx(d,date,df),114), date, font=df, fill=C_MUTED)

    # ── Main card ──────────────────────────────────────────────
    card_t, card_b = 188, H-148
    # Shadow
    d.rounded_rectangle([48,card_t+6,W-48+6,card_b+6], radius=28, fill=(6,6,20))
    # Card
    d.rounded_rectangle([48,card_t,W-48,card_b], radius=28, fill=C_PANEL)
    # Cyan top strip
    d.rounded_rectangle([48,card_t,W-48,card_t+8], radius=28, fill=C_CYAN)
    # Left accent
    d.rounded_rectangle([48,card_t,58,card_b], radius=28, fill=(*C_VIOLET,180))

    inner_l = 72
    inner_r = W-60
    inner_w = inner_r - inner_l

    # ── Headline — auto-size, vertically centered ──────────────
    hl_top    = card_t + 32
    hl_bottom = card_b - 32
    available = hl_bottom - hl_top

    best_f, best_lines = font(40,True), [title]
    for fsize in [80,70,62,54,46,40]:
        f_  = font(fsize,True)
        lns = fit_lines(d, title, f_, inner_w)
        lh  = fsize+16
        if len(lns)*lh <= available:
            best_f, best_lines = f_, lns
            break

    lh      = best_f.size+16
    block_h = len(best_lines)*lh
    hl_y    = hl_top + (available-block_h)//2

    for line in best_lines:
        img = glow_text(img, line, best_f,
                        cx(d,line,best_f), hl_y, C_TEXT, C_CYAN)
        d   = ImageDraw.Draw(img)
        hl_y += lh

    # ── Footer bar ─────────────────────────────────────────────
    foot_t = H-138
    d.rounded_rectangle([40,foot_t,W-40,H-40], radius=24, fill=C_PANEL)
    d.rectangle([40,foot_t,W-40,foot_t+6], fill=C_CYAN)

    bf2 = font(40,True)
    hf2 = font(24)
    brand  = PAGE_NAME
    handle = PAGE_HANDLE+"   |   Daily Market Updates"

    # Auto-shrink handle if too wide
    while tw(d,handle,hf2) > W-120 and len(handle)>10:
        handle = handle[:-4]+"..."

    d.text((cx(d,brand,bf2),  foot_t+16), brand,  font=bf2, fill=C_GOLD)
    d.text((cx(d,handle,hf2), foot_t+68), handle, font=hf2, fill=C_MUTED)

    img.save(output_path, quality=95)
    print(f"       saved -> {output_path}")
