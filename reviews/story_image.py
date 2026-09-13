"""Generează o imagine „poveste" (1080x1920, format Instagram Story) pentru
un produs — poză stil polaroid, verdict scurt, notă și sigiliul TESTED BY
DEEA — gata de descărcat și postat direct de vizitatoare."""

import io
import logging
import textwrap
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

W, H = 1080, 1920

CREAM = (255, 247, 240)
PINK = (255, 111, 165)
PINK_SOFT = (255, 214, 232)
MAROON = (122, 30, 61)
GOLD = (232, 184, 75)
PEACH = (255, 233, 214)
WHITE = (255, 255, 255)

PHOTO_ROTATION_DEG = -4

# Fonturile sunt bundle-uite în repo (static/fonts/) în loc să depindă de o
# cale absolută de sistem — nu e garantat că același font e instalat la
# aceeași cale pe orice host de producție. Fraunces e fontul editorial al
# brandului (folosit pe tot site-ul pentru titluri) — DejaVu rămâne doar
# pentru text mic/UI, unde o serifă grea s-ar citi greu.
_FONTS_DIR = Path(settings.BASE_DIR) / "static" / "fonts"
FONT_BOLD = _FONTS_DIR / "DejaVuSans-Bold.ttf"
FONT_REGULAR = _FONTS_DIR / "DejaVuSans.ttf"
FONT_DISPLAY = _FONTS_DIR / "Fraunces-Black.ttf"
FONT_QUOTE = _FONTS_DIR / "Fraunces-Italic.ttf"


def _font(path, size):
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        # Nu blocăm generarea imaginii dacă fontul lipsește dintr-un motiv
        # sau altul pe host — mai bine text cu fontul implicit decât 500.
        # Logăm totuși, altfel un font lipsă/corupt după un deploy prost ar
        # rămâne nedetectat la nesfârșit (toate imaginile de Story ar arăta
        # tăcut cu fontul implicit, urât, fără ca nimeni să afle).
        logger.warning("Fontul %s nu a putut fi încărcat — folosesc fontul implicit.", path)
        return ImageFont.load_default(size=size)


def _center_text(draw, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text(((W - w) / 2 - bbox[0], y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def _center_pill(draw, y, text, font, text_fill, pill_fill, pad_x=24, pad_y=12, outline=None):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x0 = (W - tw) / 2 - pad_x
    x1 = (W + tw) / 2 + pad_x
    draw.rounded_rectangle(
        [x0, y, x1, y + th + pad_y * 2], radius=(th + pad_y * 2) / 2,
        fill=pill_fill, outline=outline, width=3 if outline else 0,
    )
    draw.text(((W - tw) / 2 - bbox[0], y + pad_y - bbox[1] / 8), text, font=font, fill=text_fill)
    return th + pad_y * 2


def _sparkle(draw, cx, cy, size, color):
    # Formă desenată (nu glyph de emoji — fonturile bundle-uite nu au emoji
    # color), un mic „sparkle" în patru colțuri, ca accent decorativ.
    long_, short_ = size, size * 0.28
    draw.polygon([
        (cx, cy - long_), (cx + short_, cy - short_),
        (cx + long_, cy), (cx + short_, cy + short_),
        (cx, cy + long_), (cx - short_, cy + short_),
        (cx - long_, cy), (cx - short_, cy - short_),
    ], fill=color)


def _blob(base, cx, cy, radius, color, alpha, blur):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius], fill=(*color, alpha)
    )
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    base.paste(layer, (0, 0), layer)


def _gradient_square(size, top, bottom):
    block = Image.new("RGB", (size, size), top)
    bd = ImageDraw.Draw(block)
    for i in range(size):
        t = i / size
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        bd.line([(0, i), (size, i)], fill=(r, g, b))
    return block


def _rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *img.size], radius=radius, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out


def _product_photo(source_path, size):
    img = Image.open(source_path).convert("RGB")
    side = min(img.size)
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
    return _rounded(img, radius=20)


def _polaroid(product, inner_size, border):
    try:
        photo = _product_photo(product.poza.path, inner_size)
    except (ValueError, FileNotFoundError, AttributeError):
        photo = _rounded(_gradient_square(inner_size, PINK_SOFT, PEACH), radius=20)

    frame_size = inner_size + border * 2
    frame = Image.new("RGBA", (frame_size, frame_size), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle(
        [0, 0, frame_size, frame_size], radius=32, fill=(*WHITE, 255)
    )
    frame.paste(photo, (border, border), photo)
    return frame.rotate(PHOTO_ROTATION_DEG, resample=Image.BICUBIC, expand=True)


def _shadow_for(rotated_frame, alpha=90, blur=22):
    alpha_mask = rotated_frame.split()[-1]
    tinted = Image.new("RGBA", rotated_frame.size, (*MAROON, alpha))
    shadow = Image.new("RGBA", rotated_frame.size, (0, 0, 0, 0))
    shadow.paste(tinted, (0, 0), alpha_mask)
    return shadow.filter(ImageFilter.GaussianBlur(blur))


def _wrap_truncated(text, width, max_lines):
    """Ca textwrap.wrap, dar dacă textul nu încape în max_lines, ultima
    linie afișată primește un „…" — altfel o simplă tăiere la [:max_lines]
    pierde restul textului fără niciun semn vizibil (arată ca tot textul,
    dar nu e), ceea ce e mai rău decât o trunchiere vizibilă."""
    text = " ".join(text.split())
    lines = textwrap.wrap(text, width=width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" ,.;:!?") + "…"
    return lines


def _truncate_to_width(draw, text, font, max_width):
    """Taie `text` caracter cu caracter până încape pe o singură linie —
    fără asta, un brand cu nume neobișnuit de lung ar ieși din cadru în loc
    să se oprească elegant la marginea imaginii."""
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text
    while text and draw.textbbox((0, 0), text + "…", font=font)[2] > max_width:
        text = text[:-1]
    return text.rstrip(" ,.;:") + "…"


def build_story_image(product, host):
    base = Image.new("RGB", (W, H), CREAM)
    for i in range(H):
        t = i / H
        r = int(PINK_SOFT[0] * (1 - t) + PEACH[0] * t)
        g = int(PINK_SOFT[1] * (1 - t) + PEACH[1] * t)
        b = int(PINK_SOFT[2] * (1 - t) + PEACH[2] * t)
        ImageDraw.Draw(base).line([(0, i), (W, i)], fill=(r, g, b))

    _blob(base, W + 60, 140, 320, GOLD, 60, 90)
    _blob(base, -80, H - 260, 380, PINK, 70, 100)

    draw = ImageDraw.Draw(base)

    y = 88
    _sparkle(draw, 150, y + 30, 16, GOLD)
    y += _center_text(draw, y, "glow diary", _font(FONT_DISPLAY, 52), MAROON) + 6
    y += _center_text(draw, y, "by Deea", _font(FONT_QUOTE, 30), PINK) + 34

    y += _center_pill(
        draw, y, product.get_categorie_display().upper(), _font(FONT_BOLD, 24),
        MAROON, (*WHITE, 235),
    ) + 26

    inner_size, border = 660, 24
    photo = _polaroid(product, inner_size, border)
    shadow = _shadow_for(photo)
    photo_x = (W - photo.width) // 2
    base.paste(shadow, (photo_x, y + 16), shadow)
    base.paste(photo, (photo_x, y), photo)
    y += photo.height + 40

    draw = ImageDraw.Draw(base)
    brand_font = _font(FONT_BOLD, 34)
    brand_text = _truncate_to_width(draw, product.brand.upper(), brand_font, W - 140)
    y += _center_text(draw, y, brand_text, brand_font, PINK) + 18

    name_font = _font(FONT_DISPLAY, 56)
    for line in _wrap_truncated(product.nume, width=20, max_lines=2):
        y += _center_text(draw, y, line, name_font, MAROON) + 8
    y += 26

    stars = "★" * product.nota_mea + "☆" * (5 - product.nota_mea)
    y += _center_text(draw, y, stars, _font(FONT_BOLD, 50), GOLD) + 30

    if product.pret:
        y += _center_pill(
            draw, y, f"{product.pret.normalize():f} lei", _font(FONT_BOLD, 26),
            MAROON, None, outline=MAROON,
        ) + 34

    quote_lines = _wrap_truncated(product.parerea_mea, width=30, max_lines=3)
    if quote_lines:
        if len(quote_lines) == 1:
            quote_lines[0] = f"„{quote_lines[0]}”"
        else:
            quote_lines[0] = f"„{quote_lines[0]}"
            quote_lines[-1] = f"{quote_lines[-1]}”"
        quote_font = _font(FONT_QUOTE, 34)
        for line in quote_lines:
            y += _center_text(draw, y, line, quote_font, MAROON) + 6
        y += 24

    if product.il_recumpar:
        y += _center_pill(
            draw, y, "✓ AȘ RECUMPĂRA-L", _font(FONT_BOLD, 26), MAROON, (*GOLD, 255),
        ) + 20

    seal_font = _font(FONT_BOLD, 32)
    seal_text = "TESTED BY DEEA"
    bbox = draw.textbbox((0, 0), seal_text, font=seal_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 32, 18
    seal_w, seal_h = tw + pad_x * 2, th + pad_y * 2 + 6
    seal = Image.new("RGBA", (seal_w + 40, seal_h + 40), (0, 0, 0, 0))
    sd = ImageDraw.Draw(seal)
    sd.rounded_rectangle([20, 20, 20 + seal_w, 20 + seal_h], radius=seal_h / 2, fill=(*PINK, 255))
    sd.text((20 + pad_x, 20 + pad_y - bbox[1]), seal_text, font=seal_font, fill=WHITE)
    _sparkle(sd, 20 + seal_w - 6, 20, 10, GOLD)
    seal = seal.rotate(3, resample=Image.BICUBIC, expand=True)
    base.paste(seal, ((W - seal.width) // 2, int(y)), seal)
    y += seal.height + 44

    # Poziția footer-ului e ancorată jos în cazul obișnuit (conținut scurt),
    # dar niciodată mai sus decât atât — dacă textul de deasupra (citatul,
    # badge-ul „aș recumpăra") a crescut mai mult decât de obicei, footer-ul
    # coboară odată cu el în loc să se suprapună peste sigiliu.
    tag_y = max(y + 24, H - 150)
    host_y = tag_y + 54

    # Produsele fără preț/decizie de recumpărare încă (câmpuri opționale)
    # lasă un gol vizibil între sigiliu și footer — câteva sparkle-uri
    # risipite îl umplu în loc să arate ca un spațiu uitat gol.
    gap = tag_y - y
    if gap > 160:
        for dx, dy_frac, sz, color in (
            (-260, 0.35, 14, GOLD), (240, 0.55, 18, PINK), (-140, 0.75, 11, GOLD),
        ):
            _sparkle(draw, W / 2 + dx, y + gap * dy_frac, sz, color)

    dot_y = tag_y - 40
    for i in range(-2, 3):
        draw.ellipse(
            [W / 2 + i * 26 - 5, dot_y - 5, W / 2 + i * 26 + 5, dot_y + 5],
            fill=PINK if i != 0 else GOLD,
        )

    tag_font = _font(FONT_REGULAR, 30)
    _center_text(draw, tag_y, "Real products. My honest take.", tag_font, MAROON)
    if host:
        _center_text(draw, host_y, host, _font(FONT_BOLD, 28), PINK)

    return base


def render_story_png(product, host):
    img = build_story_image(product, host)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
