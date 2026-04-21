from PIL import Image, ImageDraw, ImageFont
import textwrap, re
from datetime import datetime
from config import PAGE_NAME, PAGE_HANDLE

WIDTH, HEIGHT = 1080, 1080

# Palette
BG_TOP      = (225, 210, 255)
BG_BOTTOM   = (255, 235, 248)
CARD_BG     = (255, 255, 255)
CARD_BORDER = (190, 160, 235)
CARD_SHADOW = (185, 160, 225)
ACCENT      = (160, 110, 220)
BADGE_BG    = (240, 230, 255)
BADGE_TEXT  = (120, 75, 195)
TITLE_COLOR = (35, 20, 70)
DATE_COLOR  = (170, 145, 200)
FOOTER_BG   = (150, 100, 215)
FOOTER_TEXT = (255, 255, 255)
FOOTER_SUB  = (230, 215, 255)
DIVIDER     = (230, 218, 250)


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


def gradient_bg(size, top, bottom):
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    w, h = size
    for y in range(h):
        t = y / h
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=c)
    return img


def tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def th(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def centered_x(draw, text, font):
    return (WIDTH - tw(draw, text, font)) // 2


def draw_centered(draw, text, font, y, color):
    draw.text((centered_x(draw, text, font), y), text, font=font, fill=color)


def fit_text_centered(draw, text, font, max_w):
    """Wrap text so each line fits within max_w, return list of lines."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if tw(draw, test, font) <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def create_post_image(article, output_path):
    img  = gradient_bg((WIDTH, HEIGHT), BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(img)

    # ── Card geometry ──────────────────────────────────────────
    FOOT_H   = 118          # footer height
    FOOT_PAD = 20           # gap between card and footer
    MARGIN   = 52

    foot_t  = HEIGHT - MARGIN - FOOT_H
    card_t  = MARGIN
    card_b  = foot_t - FOOT_PAD
    card_l  = MARGIN
    card_r  = WIDTH - MARGIN

    # Shadow
    draw.rounded_rectangle(
        [card_l + 7, card_t + 7, card_r + 7, card_b + 7],
        radius=32, fill=CARD_SHADOW
    )
    # Card
    draw.rounded_rectangle(
        [card_l, card_t, card_r, card_b],
        radius=32, fill=CARD_BG, outline=CARD_BORDER, width=2
    )
    # Left accent strip
    draw.rounded_rectangle(
        [card_l, card_t, card_l + 10, card_b],
        radius=32, fill=ACCENT
    )

    inner_l = card_l + 10   # after strip
    inner_r = card_r
    inner_w = inner_r - inner_l - 60   # usable text width with padding

    # ── STOCK NEWS badge ───────────────────────────────────────
    bf    = get_font(26, bold=True)
    blbl  = "STOCK  NEWS"
    bw    = tw(draw, blbl, bf) + 52
    bh    = 46
    bx    = (WIDTH - bw) // 2
    by    = card_t + 44
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=23, fill=BADGE_BG)
    draw.text((bx + 26, by + 9), blbl, font=bf, fill=BADGE_TEXT)

    # ── Date ──────────────────────────────────────────────────
    df   = get_font(25)
    date = datetime.now().strftime("%d %B %Y")
    dy   = by + bh + 14
    draw_centered(draw, date, df, dy, DATE_COLOR)

    # ── Divider ───────────────────────────────────────────────
    div_y = dy + th(draw, date, df) + 18
    draw.rectangle([inner_l + 30, div_y, inner_r - 30, div_y + 2], fill=DIVIDER)

    # ── Headline block — auto-size font to fill space ──────────
    title = re.sub(r"[^\x00-\x7F]+", "", article["title"]).strip()
    # Strip trailing source attribution e.g. "- Moneycontrol" or "| ET"
    title = re.sub(r"\s*[-|]\s*[A-Z][^\-|]{2,30}$", "", title).strip()

    # Space available for headline
    hl_top    = div_y + 28
    hl_bottom = card_b - 40

    available_h = hl_bottom - hl_top

    best_font, best_lines = get_font(40, bold=True), [title]
    for fsize in [76, 68, 60, 52, 46, 40]:
        f     = get_font(fsize, bold=True)
        lines = fit_text_centered(draw, title, f, inner_w)
        lh    = fsize + 14
        total = len(lines) * lh
        if total <= available_h:
            best_font, best_lines = f, lines
            break

    lh      = best_font.size + 14
    block_h = len(best_lines) * lh
    hl_y    = hl_top + (available_h - block_h) // 2   # vertically centered

    for line in best_lines:
        draw_centered(draw, line, best_font, hl_y, TITLE_COLOR)
        hl_y += lh



    # ── Footer ────────────────────────────────────────────────
    draw.rounded_rectangle(
        [MARGIN, foot_t, WIDTH - MARGIN, foot_t + FOOT_H],
        radius=26, fill=FOOTER_BG
    )

    brand_f  = get_font(40, bold=True)
    handle_f = get_font(24)
    brand    = PAGE_NAME
    handle   = PAGE_HANDLE + "   |   Daily Market Updates"

    # Clamp handle text if too wide
    while tw(draw, handle, handle_f) > (WIDTH - MARGIN * 2 - 60) and len(handle) > 10:
        handle = handle[:-4] + "..."

    brand_y  = foot_t + 14
    handle_y = foot_t + 64

    draw_centered(draw, brand,  brand_f,  brand_y,  FOOTER_TEXT)
    draw_centered(draw, handle, handle_f, handle_y, FOOTER_SUB)

    img.save(output_path, quality=95)
    print(f"       saved -> {output_path}")
