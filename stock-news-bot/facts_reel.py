"""
Facts Reel Generator — StockDev.in
Cinematic stock market trivia reel. Same visual language as investment_reel.py.

Timeline (~19s):
  0-3s  : Hook — dramatic question with orbital rings
  3-7s  : Point 1 — slides in with number badge
  7-11s : Point 2 — slides in
  11-15s: Point 3 — slides in
  15-17s: CTA card — all 3 points visible
  17-19s: Outro
"""

import json, math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops
from moviepy import VideoClip, AudioFileClip, concatenate_videoclips
from moviepy.audio.AudioClip import AudioArrayClip
from config import PAGE_NAME, PAGE_HANDLE

W, H, FPS = 1080, 1920, 30
MUSIC_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music")
FACTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "facts.json")

# ── Palette (matches investment_reel.py) ──────────────────────
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

# Category → accent color mapping
CAT_COLORS = {
    "investing_myths":      C_RED,
    "compounding":          C_GREEN,
    "nifty_history":        C_CYAN,
    "sip_power":            C_GREEN,
    "trading_psychology":   C_VIOLET,
    "ipo_facts":            C_RED,
    "global_markets":       C_CYAN,
    "wealth_building":      C_GOLD,
    "market_basics":        C_CYAN,
    "stock_picks":          C_GREEN,
    "mutual_funds":         C_VIOLET,
    "gold_vs_stocks":       C_GOLD,
    "real_estate_vs_stocks":C_GOLD,
    "crypto_vs_stocks":     C_RED,
    "dividend_investing":   C_GREEN,
    "smallcap_midcap":      C_VIOLET,
    "sector_insights":      C_CYAN,
    "market_crashes":       C_RED,
    "famous_investors":     C_GOLD,
    "india_economy":        C_GREEN,
}

# ── Helpers ────────────────────────────────────────────────────
def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))
def prog(t, s, e): return clamp((t-s)/(e-s)) if e>s else float(t>=s)
def eo3(t): t=clamp(t); return 1-(1-t)**3
def eo5(t): t=clamp(t); return 1-(1-t)**5
def eio(t): t=clamp(t); return t*t*(3-2*t)
def lerp(a,b,t): return a+(b-a)*clamp(t)
def lerp_col(c1,c2,t): return tuple(int(lerp(c1[i],c2[i],t)) for i in range(3))
def spring(t,s=10,d=0.45):
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

def base_canvas(t=0.0, tint=None):
    arr = np.zeros((H,W,3), dtype=np.uint8)
    for y in range(H):
        arr[y] = lerp_col(C_BG_TOP, C_BG_BOT, y/H)
    img = Image.fromarray(arr)
    d   = ImageDraw.Draw(img)
    for i in range(6):
        x = int((W*0.18*i+(t*110)%(W*1.2))-W*0.2)
        d.polygon([(x,0),(x+110,0),(x-240,H),(x-350,H)], fill=(40,30,82,28))
    rng   = np.random.default_rng(int(t*800)+55)
    noise = rng.integers(0,14,size=(H,W),dtype=np.uint8)
    layer = Image.fromarray(noise,"L").convert("RGB")
    img   = ImageChops.screen(img, layer)
    if tint:
        ov = Image.new("RGBA", img.size, (0,0,0,0))
        od = ImageDraw.Draw(ov)
        for r in range(7,0,-1):
            rad=160+r*55; a=int(16*(r/7))
            od.ellipse([W-rad-40,60-rad,W+rad-40,60+rad], fill=(*tint,a))
        img = Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")
    return img

def soft_glow(img, x, y, radius, color):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    od = ImageDraw.Draw(ov)
    for r in range(6,0,-1):
        rr=radius+(6-r)*22; a=int(65*r/6)
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

def wrap_text(d, text, f, max_w):
    """Wrap text to fit within max_w pixels."""
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

def hud_footer(img, d):
    d.rounded_rectangle([46,H-148,W-46,H-54], radius=26, fill=C_PANEL)
    d.rectangle([46,H-148,W-46,H-142], fill=C_CYAN)
    d.text((74,H-128), PAGE_NAME, font=font(38,True), fill=C_TEXT)
    hf = font(28)
    d.text((W-74-tw(d,PAGE_HANDLE,hf),H-120), PAGE_HANDLE, font=hf, fill=C_MUTED)

def get_todays_fact():
    """Pick fact based on day-of-year rotation."""
    from datetime import datetime
    with open(FACTS_FILE, encoding="utf-8") as f:
        facts = json.load(f)
    idx = datetime.now().timetuple().tm_yday % len(facts)
    return facts[idx]

# ── Frame builders ─────────────────────────────────────────────

def frame_hook(t, fact, accent, total=3.0):
    """0-3s: Dramatic hook with orbital rings and flash."""
    img = base_canvas(t, tint=accent)
    img = soft_glow(img, W//2, H//2-200, 260, accent)
    d   = ImageDraw.Draw(img)

    # Orbital rings
    for i in range(3):
        rot = int((t*80+i*120)%360)
        rad = 210+i*50
        box = [W//2-rad, H//2-280-rad, W//2+rad, H//2-280+rad]
        d.arc(box, start=rot, end=rot+240, fill=(*accent,140), width=3)
        d.arc(box, start=rot+130, end=rot+310, fill=(*C_VIOLET,110), width=2)

    # Flash on entry
    if t < 0.12:
        flash = int(200*(1-t/0.12))
        ov = Image.new("RGBA", img.size, (255,255,255,flash))
        img = Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")
        d   = ImageDraw.Draw(img)

    # Category badge
    p_b = eo3(prog(t,0.0,0.7))
    cat = fact["category"].replace("_"," ").upper()
    cf  = font(26,True)
    cw_ = tw(d,cat,cf)+48
    bx  = (W-cw_)//2
    by  = int(180-28*(1-p_b))
    d.rounded_rectangle([bx,by,bx+cw_,by+52], radius=26, fill=C_PANEL)
    d.rectangle([bx,by,bx+cw_,by+6], fill=accent)
    d.text((bx+24,by+14), cat, font=cf, fill=accent)

    # Hook sub
    p_s = eo3(prog(t,0.15,0.85))
    sf  = font(34)
    sub = fact["hook_sub"]
    sy  = int(260-20*(1-p_s))
    d.text((cx(d,sub,sf),sy), sub, font=sf, fill=(*C_MUTED,int(220*p_s)))

    # Main hook — big, glowing
    p_h = eo5(prog(t,0.3,1.2))
    hook = fact["hook"]
    max_w = W-80
    for fsize in [80,70,62,54,46,40]:
        hf = font(fsize,True)
        lines = wrap_text(d, hook, hf, max_w)
        if len(lines)*( fsize+18) <= 420: break

    lh = hf.size+18
    total_h = len(lines)*lh
    y = H//2 - total_h//2 - 80
    for line in lines:
        img = glow_text(img, line, hf, cx(d,line,hf), int(y+30*(1-p_h)),
                        C_TEXT, accent)
        d   = ImageDraw.Draw(img)
        y  += lh

    hud_footer(img, d)
    return np.array(img)


def frame_point(t, point_text, number, accent, total=4.0):
    """Each point slides in dramatically with number badge."""
    img = base_canvas(t, tint=accent)
    d   = ImageDraw.Draw(img)

    p_in = eo5(prog(t, 0.0, 0.5))

    # Large number badge — slides from right
    badge_size = 180
    badge_x = int(lerp(W+50, W//2-badge_size//2, p_in))
    badge_y = 220
    # Glow behind badge
    img = soft_glow(img, W//2, badge_y+badge_size//2, badge_size//2+40, accent)
    d   = ImageDraw.Draw(img)
    d.rounded_rectangle([badge_x, badge_y, badge_x+badge_size, badge_y+badge_size],
                         radius=36, fill=C_PANEL)
    d.rounded_rectangle([badge_x, badge_y, badge_x+badge_size, badge_y+10],
                         radius=36, fill=accent)
    nf = font(96,True)
    d.text((badge_x+cx(d,str(number),nf,badge_size), badge_y+42),
           str(number), font=nf, fill=accent)

    # Point text card — slides up from bottom
    card_y = int(lerp(H, 460, eo3(prog(t,0.1,0.6))))
    card_h = H - card_y - 170
    d.rounded_rectangle([46,card_y+6,W-46+6,card_y+card_h+6], radius=28, fill=(6,6,20))
    d.rounded_rectangle([46,card_y,W-46,card_y+card_h], radius=28, fill=C_PANEL)
    d.rounded_rectangle([46,card_y,W-46,card_y+8], radius=28, fill=accent)
    d.rounded_rectangle([46,card_y,58,card_y+card_h], radius=28, fill=(*accent,100))

    # Point text — word by word reveal
    words   = point_text.split()
    n_words = max(1, int(len(words)*min(prog(t,0.3,total*0.9),1.0)))
    visible = " ".join(words[:n_words])
    pf      = font(46,True)
    lines   = wrap_text(d, visible, pf, W-130)
    ty      = card_y + 32
    for line in lines[:6]:
        img = glow_text(img, line, pf, cx(d,line,pf), ty, C_TEXT, accent)
        d   = ImageDraw.Draw(img)
        ty += 62

    # Blinking cursor
    if n_words < len(words) and int(t*3)%2==0:
        d.rectangle([W//2-3,ty,W//2+3,ty+46], fill=accent)

    hud_footer(img, d)
    return np.array(img)


def frame_cta(t, fact, accent, total=2.0):
    """15-17s: All 3 points visible + CTA."""
    img = base_canvas(t, tint=accent)
    img = soft_glow(img, W//2, H//2, 300, accent)
    d   = ImageDraw.Draw(img)

    p = eo3(prog(t,0,total))

    # Header
    d.rounded_rectangle([46,42,W-46,160], radius=26, fill=C_PANEL)
    d.rectangle([46,42,W-46,50], fill=accent)
    img = glow_text(img,"KEY TAKEAWAYS",font(40,True),
                    cx(d,"KEY TAKEAWAYS",font(40,True)),68,C_TEXT,accent)
    d = ImageDraw.Draw(img)

    # 3 mini point cards
    points = fact["points"]
    card_h = 200
    gap    = 16
    total_cards_h = len(points)*card_h + (len(points)-1)*gap
    start_y = int(H//2 - total_cards_h//2 + 20*(1-p))

    for i, pt in enumerate(points[:3]):
        by = start_y + i*(card_h+gap)
        # Staggered entry
        entry_p = eo3(prog(t, i*0.15, i*0.15+0.5))
        bx_off  = int(60*(1-entry_p))
        d.rounded_rectangle([46+bx_off,by,W-46,by+card_h],
                             radius=20, fill=C_PANEL)
        d.rounded_rectangle([46+bx_off,by,W-46,by+8], radius=20, fill=accent)
        # Number circle
        d.ellipse([60+bx_off,by+card_h//2-28,116+bx_off,by+card_h//2+28],
                  fill=(*accent,180))
        d.text((60+bx_off+cx(d,str(i+1),font(36,True),56),
                by+card_h//2-20), str(i+1), font=font(36,True), fill=C_BG_TOP)
        # Point text (truncated)
        short = pt[:80]+"..." if len(pt)>80 else pt
        pf    = font(30)
        for line in wrap_text(d, short, pf, W-200)[:3]:
            d.text((130+bx_off, by+20), line, font=pf, fill=C_TEXT)
            by += 38

    # CTA text
    cta_y = start_y + total_cards_h + 30
    img = glow_text(img, fact["cta"], font(38,True),
                    cx(d,fact["cta"],font(38,True)), cta_y, C_GOLD, C_GOLD)
    d = ImageDraw.Draw(img)

    hud_footer(img, d)
    return np.array(img)


def frame_outro(t, accent, total=2.0):
    """17-19s: Brand outro."""
    img = base_canvas(t, tint=C_CYAN)
    img = soft_glow(img, W//2, H//2-200, 220, C_CYAN)
    d   = ImageDraw.Draw(img)

    p = eo5(prog(t,0,total))

    img = glow_text(img, PAGE_NAME, font(88,True),
                    cx(d,PAGE_NAME,font(88,True)), H//2-220, C_TEXT, C_CYAN)
    d = ImageDraw.Draw(img)
    d.text((cx(d,PAGE_HANDLE,font(38)),H//2-110),
           PAGE_HANDLE, font=font(38), fill=C_MUTED)

    for i,line in enumerate(["Follow for daily","market facts & insights!"]):
        cf = font(46,True if i==1 else False)
        d.text((cx(d,line,cf),H//2+20+i*68), line, font=cf, fill=C_TEXT)

    bw,bh = 420,84; bx=W//2-bw//2; by=H//2+200
    d.rounded_rectangle([bx,by,bx+bw,by+bh], radius=42, fill=accent)
    d.text((bx+(bw-tw(d,"FOLLOW NOW",font(40,True)))//2,by+22),
           "FOLLOW NOW", font=font(40,True), fill=C_BG_TOP)

    hud_footer(img, d)
    return np.array(img)

# ── Main ───────────────────────────────────────────────────────
def create_facts_reel(fact, output_path):
    """Generate a cinematic facts reel from a fact dict."""
    accent = CAT_COLORS.get(fact.get("category","market_basics"), C_CYAN)
    points = fact["points"][:3]

    print(f"  Fact: {fact['hook'][:60]}")
    print(f"  Category: {fact['category']} | Accent: {accent}")

    def clip(fn, dur, **kw):
        return VideoClip(lambda t: fn(t,**kw).astype(np.uint8),
                         duration=dur).with_fps(FPS)

    print("  Rendering sections...")
    clips = [
        clip(frame_hook,  3.0, fact=fact, accent=accent),
        clip(frame_point, 4.0, point_text=points[0], number=1, accent=accent),
        clip(frame_point, 4.0, point_text=points[1], number=2, accent=accent),
        clip(frame_point, 4.0, point_text=points[2], number=3, accent=accent),
        clip(frame_cta,   2.0, fact=fact, accent=accent),
        clip(frame_outro, 2.0, accent=accent),
    ]
    video = concatenate_videoclips(clips)
    total_dur = sum(c.duration for c in clips)

    # Music — prefer cinematic tracks
    mfiles = sorted(
        [f for f in os.listdir(MUSIC_DIR) if f.endswith((".mp3",".wav"))],
        key=lambda x: "cinematic" in x.lower(), reverse=True
    ) if os.path.exists(MUSIC_DIR) else []
    print(f"  Music: {mfiles}")
    if mfiles:
        try:
            audio = AudioFileClip(os.path.join(MUSIC_DIR, mfiles[0]))
            audio = audio.subclipped(0, min(total_dur, audio.duration))
            video = video.with_audio(audio)
            print("  [✓] Music embedded")
        except Exception as e:
            print(f"  [!] Music error: {e}")

    print("  Writing video...")
    video.write_videofile(
        output_path, fps=FPS, codec="libx264",
        audio_codec="aac", temp_audiofile="temp_facts.m4a",
        remove_temp=True, logger=None,
        preset="medium", ffmpeg_params=["-crf","28"]
    )
    print(f"  [✓] Saved -> {output_path}")
    return True
