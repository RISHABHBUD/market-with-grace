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


def frame_counter(t, fact, fact_number, total_facts, accent, total=2.0):
    """0-2s: '1/100' counter reveal with category heading."""
    img = base_canvas(t, tint=accent)
    img = soft_glow(img, W//2, H//2-100, 280, accent)
    d   = ImageDraw.Draw(img)
    if t < 0.1:
        flash = int(180*(1-t/0.1))
        ov = Image.new("RGBA", img.size, (255,255,255,flash))
        img = Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")
        d   = ImageDraw.Draw(img)
    p = eo5(prog(t, 0.0, 0.8))
    hdr = "STOCK MARKET FACTS"
    hf  = font(38, True)
    d.text((cx(d,hdr,hf), int(H//2-380+20*(1-p))), hdr, font=hf,
           fill=(*C_MUTED, int(220*p)))
    counter = f"{fact_number}/{total_facts}"
    for fsize in [200, 170, 150]:
        cf = font(fsize, True)
        if tw(d, counter, cf) <= W-80: break
    cy = H//2 - 200
    img = glow_text(img, counter, cf, cx(d,counter,cf),
                    int(cy+40*(1-p)), C_TEXT, accent)
    d   = ImageDraw.Draw(img)
    lw_ = int((W-120)*p)
    d.rectangle([W//2-lw_//2, H//2+cf.size-180,
                 W//2+lw_//2, H//2+cf.size-176], fill=(*accent,180))
    cat = fact["category"].replace("_"," ").upper()
    cbf = font(28, True)
    cw_ = tw(d,cat,cbf)+48
    bx  = (W-cw_)//2
    by  = int(H//2+cf.size-160+20*(1-p))
    d.rounded_rectangle([bx,by,bx+cw_,by+54], radius=27, fill=C_PANEL)
    d.rectangle([bx,by,bx+cw_,by+6], fill=accent)
    d.text((bx+24,by+14), cat, font=cbf, fill=accent)
    sub = "Today's Market Fact"
    sf  = font(34)
    d.text((cx(d,sub,sf), by+74), sub, font=sf, fill=(*C_MUTED, int(200*p)))
    hud_footer(img, d)
    return np.array(img)


def frame_hook(t, fact, accent, total=3.0):
    """Hook with orbital rings centered on screen."""
    img = base_canvas(t, tint=accent)
    img = soft_glow(img, W//2, H//2, 260, accent)  # glow at true center
    d   = ImageDraw.Draw(img)
    # Orbital rings centered at H//2 (true screen center)
    for i in range(3):
        rot = int((t*80+i*120)%360)
        rad = 200+i*48
        box = [W//2-rad, H//2-rad, W//2+rad, H//2+rad]  # centered
        d.arc(box, start=rot, end=rot+240, fill=(*accent,130), width=3)
        d.arc(box, start=rot+130, end=rot+310, fill=(*C_VIOLET,100), width=2)
    p_h = eo5(prog(t, 0.1, 1.0))
    sub = fact["hook_sub"]
    sf  = font(32)
    d.text((cx(d,sub,sf), int(H//2-320+20*(1-p_h))), sub, font=sf,
           fill=(*C_MUTED, int(200*p_h)))
    hook  = fact["hook"]
    max_w = W-80
    for fsize in [76,66,58,50,44]:
        hf    = font(fsize, True)
        lines = wrap_text(d, hook, hf, max_w)
        if len(lines)*(fsize+20) <= 500: break
    lh = hf.size+20; total_h = len(lines)*lh
    y  = H//2 - total_h//2
    for line in lines:
        img = glow_text(img, line, hf, cx(d,line,hf),
                        int(y+30*(1-p_h)), C_TEXT, accent)
        d   = ImageDraw.Draw(img)
        y  += lh
    hud_footer(img, d)
    return np.array(img)


def frame_point(t, point_text, number, total_points, accent, total=6.0):
    """Each point: compact design, smooth character-by-character reveal."""
    img = base_canvas(t, tint=accent)
    img = soft_glow(img, W//2, H//2, 300, accent)
    d   = ImageDraw.Draw(img)
    top_y = 80
    # Progress dots
    dot_r = 14; dot_gap = 44
    dots_w = total_points*(dot_r*2) + (total_points-1)*(dot_gap-dot_r*2)
    dx = (W-dots_w)//2
    for i in range(total_points):
        filled = i < number
        if filled:
            d.ellipse([dx+i*dot_gap, top_y, dx+i*dot_gap+dot_r*2, top_y+dot_r*2],
                      fill=accent)
        else:
            d.ellipse([dx+i*dot_gap, top_y, dx+i*dot_gap+dot_r*2, top_y+dot_r*2],
                      outline=C_MUTED, width=2)
    pt_lbl = f"POINT  {number}"
    plf    = font(32, True)
    d.text((cx(d,pt_lbl,plf), top_y+40), pt_lbl, font=plf, fill=accent)
    d.rectangle([80, top_y+86, W-80, top_y+89], fill=(*accent,120))

    # Character-by-character reveal — slower, smoother pace
    chars_total = len(point_text)
    # Start at 0.4s, finish at 70% of clip — leaves 30% for reading
    chars_shown = int(chars_total * min(prog(t, 0.4, total*0.70), 1.0))
    visible     = point_text[:chars_shown]

    text_area_h = H - top_y - 200 - 160
    for fsize in [58, 50, 44, 38, 34]:
        pf    = font(fsize, True)
        lines = wrap_text(d, point_text, pf, W-100)
        if len(lines)*(fsize+22) <= text_area_h: break
    vis_lines = wrap_text(d, visible, pf, W-100) if visible else []
    lh        = pf.size+22
    block_h   = len(wrap_text(d, point_text, pf, W-100))*lh
    text_y    = top_y + 110 + (text_area_h - block_h)//2
    for line in vis_lines:
        img = glow_text(img, line, pf, cx(d,line,pf), text_y, C_TEXT, accent)
        d   = ImageDraw.Draw(img)
        text_y += lh
    # Blinking cursor — slower blink (2x per second)
    if chars_shown < chars_total and int(t*2)%2==0:
        d.rectangle([W//2-3, text_y, W//2+3, text_y+pf.size], fill=accent)
    bar_y = H - 170
    bar_w = int((W-120) * min(prog(t, 0.1, 0.5), 1.0))
    d.rounded_rectangle([60, bar_y, 60+bar_w, bar_y+6], radius=3, fill=accent)
    hud_footer(img, d)
    return np.array(img)


def frame_summary(t, fact, accent, total=5.0):
    """
    Summary: 3 compact cards centered on screen.
    Cards fit their content tightly. Bubbles float up.
    CTA pulses at bottom.
    """
    img = base_canvas(t, tint=accent)
    img = soft_glow(img, W//2, H//2, 340, accent)
    d   = ImageDraw.Draw(img)

    points = fact["points"][:3]
    pf     = font(34)
    pad    = 24   # internal card padding

    # ── Pre-calculate card heights based on actual text ────────
    card_heights = []
    for pt in points:
        lines = wrap_text(d, pt, pf, W-200)
        # height = top_pad + number_circle(56) + gap(12) + lines + bottom_pad
        text_h = len(lines)*(pf.size+10)
        card_h = max(120, pad + 56 + 12 + text_h + pad)
        card_heights.append(card_h)

    gap     = 20
    total_h = sum(card_heights) + gap*(len(points)-1)

    # ── "KEY TAKEAWAYS" header ─────────────────────────────────
    hdr_h   = 80
    cta_h   = 90
    spacing = 24
    # Total block: header + spacing + cards + spacing + cta
    block_h = hdr_h + spacing + total_h + spacing + cta_h
    # Center the whole block
    block_y = (H - block_h) // 2

    p_hdr = eo3(prog(t, 0.0, 0.5))
    img   = glow_text(img, "KEY TAKEAWAYS", font(42,True),
                      cx(d,"KEY TAKEAWAYS",font(42,True)),
                      block_y, C_TEXT, accent)
    d = ImageDraw.Draw(img)
    uw = tw(d,"KEY TAKEAWAYS",font(42,True))
    d.rectangle([W//2-uw//2, block_y+52, W//2+uw//2, block_y+56],
                fill=(*accent,160))

    # ── Cards ──────────────────────────────────────────────────
    card_y = block_y + hdr_h + spacing
    for i, (pt, ch) in enumerate(zip(points, card_heights)):
        entry_p = eo5(prog(t, i*0.2, i*0.2+0.6))
        slide_x = int(80*(1-entry_p))
        by      = card_y

        # Shadow
        d.rounded_rectangle([46+slide_x+3, by+3, W-46+3, by+ch+3],
                             radius=18, fill=(4,4,16))
        # Card
        d.rounded_rectangle([46+slide_x, by, W-46, by+ch],
                             radius=18, fill=C_PANEL)
        d.rounded_rectangle([46+slide_x, by, W-46, by+7], radius=18, fill=accent)

        # Number circle — top left
        cx_c = 46+slide_x+46; cy_c = by+pad+28
        d.ellipse([cx_c-24, cy_c-24, cx_c+24, cy_c+24], fill=(*accent,220))
        nf = font(30,True)
        d.text((cx_c-tw(d,str(i+1),nf)//2, cy_c-16), str(i+1),
               font=nf, fill=C_BG_TOP)

        # Point text — right of circle, wraps naturally
        lines = wrap_text(d, pt, pf, W-200)
        ty    = by + pad
        for line in lines:
            d.text((46+slide_x+86, ty), line, font=pf, fill=C_TEXT)
            ty += pf.size + 10

        # Bubble particles
        if entry_p > 0.4:
            rng = random.Random(i*77 + int(t*6))
            ov  = Image.new("RGBA", img.size, (0,0,0,0))
            od  = ImageDraw.Draw(ov)
            for _ in range(6):
                bx_   = rng.randint(46+slide_x+60, W-60)
                phase = (t*0.5 + rng.uniform(0,1)) % 1.0
                by_   = by - int(phase*80)
                br    = rng.randint(3,9)
                ba    = int(100*(1-phase)*entry_p)
                od.ellipse([bx_-br, by_-br, bx_+br, by_+br],
                           outline=(*accent, ba), width=2)
            img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
            d   = ImageDraw.Draw(img)

        card_y += ch + gap

    # ── CTA button ─────────────────────────────────────────────
    cta_y = block_y + hdr_h + spacing + total_h + spacing
    p_cta = eo3(prog(t, 1.0, 2.0))
    if p_cta > 0:
        pulse = 1 + 0.05*math.sin(t*5)
        cta   = fact["cta"]
        cf    = font(36, True)
        cw_   = int((tw(d,cta,cf)+60)*pulse)
        bx    = (W-cw_)//2
        img   = soft_glow(img, W//2, cta_y+36, 70, accent)
        d     = ImageDraw.Draw(img)
        d.rounded_rectangle([bx, cta_y, bx+cw_, cta_y+68], radius=34, fill=accent)
        d.text((bx+(cw_-tw(d,cta,cf))//2, cta_y+14), cta, font=cf,
               fill=(*C_BG_TOP, int(255*p_cta)))

    hud_footer(img, d)
    return np.array(img)


def frame_outro(t, accent, total=2.0):
    """Outro CTA."""
    img = base_canvas(t, tint=C_CYAN)
    img = soft_glow(img, W//2, H//2-200, 220, C_CYAN)
    d   = ImageDraw.Draw(img)
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
    accent   = CAT_COLORS.get(fact.get("category","market_basics"), C_CYAN)
    points   = fact["points"][:3]
    fact_id  = fact.get("id","fact_001")
    fact_num = int(fact_id.split("_")[-1]) if "_" in fact_id else 1
    print(f"  Fact #{fact_num}: {fact['hook'][:55]}")
    print(f"  Category: {fact['category']} | Accent: {accent}")

    def clip(fn, dur, **kw):
        return VideoClip(lambda t: fn(t,**kw).astype(np.uint8),
                         duration=dur).with_fps(FPS)

    print("  Rendering sections...")
    clips = [
        clip(frame_counter, 2.0, fact=fact, fact_number=fact_num,
             total_facts=100, accent=accent),
        clip(frame_hook,    3.0, fact=fact, accent=accent),
        clip(frame_point,   6.0, point_text=points[0], number=1,
             total_points=3, accent=accent),
        clip(frame_point,   6.0, point_text=points[1], number=2,
             total_points=3, accent=accent),
        clip(frame_point,   6.0, point_text=points[2], number=3,
             total_points=3, accent=accent),
        clip(frame_summary, 5.0, fact=fact, accent=accent),
        clip(frame_outro,   2.0, accent=accent),
    ]
    # Crossfade transitions between clips
    from moviepy import VideoClip as VC
    FADE = 0.4  # seconds of crossfade

    def crossfade(clip_a, clip_b, fade=FADE):
        total = clip_a.duration + clip_b.duration - fade
        def make_frame(t):
            if t < clip_a.duration - fade:
                return clip_a.get_frame(t)
            elif t > clip_a.duration:
                return clip_b.get_frame(t - clip_a.duration + fade)
            else:
                alpha = (t - (clip_a.duration - fade)) / fade
                fa = clip_a.get_frame(t)
                fb = clip_b.get_frame(t - clip_a.duration + fade)
                return (fa*(1-alpha) + fb*alpha).astype(np.uint8)
        return VC(make_frame, duration=total).with_fps(FPS)

    video = clips[0]
    for c in clips[1:]:
        video = crossfade(video, c)
    total_dur = sum(c.duration for c in clips) - FADE*(len(clips)-1)

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

