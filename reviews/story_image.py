"""Generează o imagine „poveste" (1080x1920, format Instagram Story) pentru
un produs — poza lui, brand, nume, notă și sigiliul TESTED BY DEEA — gata
de descărcat și postat direct de vizitatoare."""

import io
import textwrap

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920

CREAM = (255, 247, 240)
PINK = (255, 111, 165)
PINK_SOFT = (255, 214, 232)
MAROON = (122, 30, 61)
GOLD = (232, 184, 75)
PEACH = (255, 233, 214)
WHITE = (255, 255, 255)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(path, size):
    return ImageFont.truetype(path, size)


def _center_text(draw, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text(((W - w) / 2 - bbox[0], y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def _rounded_photo(source_path, size, radius):
    img = Image.open(source_path).convert("RGB")
    side = min(img.size)
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], radius=radius, fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(img, (0, 0), mask)
    return out


def build_story_image(product, host):
    img = Image.new("RGB", (W, H), CREAM)
    draw = ImageDraw.Draw(img)

    for i in range(H):
        t = i / H
        r = int(PINK_SOFT[0] * (1 - t) + PEACH[0] * t)
        g = int(PINK_SOFT[1] * (1 - t) + PEACH[1] * t)
        b = int(PINK_SOFT[2] * (1 - t) + PEACH[2] * t)
        draw.line([(0, i), (W, i)], fill=(r, g, b))

    _center_text(draw, 90, "glow diary by Deea", _font(FONT_BOLD, 44), MAROON)

    photo_size = 820
    photo_x = (W - photo_size) // 2
    photo_y = 220
    try:
        photo = _rounded_photo(product.poza.path, photo_size, 48)
        img.paste(photo, (photo_x, photo_y), photo)
    except (ValueError, FileNotFoundError, AttributeError):
        block = Image.new("RGB", (photo_size, photo_size), PINK_SOFT)
        bd = ImageDraw.Draw(block)
        for i in range(photo_size):
            t = i / photo_size
            r = int(PINK_SOFT[0] * (1 - t) + PEACH[0] * t)
            g = int(PINK_SOFT[1] * (1 - t) + PEACH[1] * t)
            b = int(PINK_SOFT[2] * (1 - t) + PEACH[2] * t)
            bd.line([(0, i), (photo_size, i)], fill=(r, g, b))
        mask = Image.new("L", (photo_size, photo_size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo_size, photo_size], radius=48, fill=255)
        img.paste(block, (photo_x, photo_y), mask)

    y = photo_y + photo_size + 70
    y += _center_text(draw, y, product.brand.upper(), _font(FONT_BOLD, 38), PINK) + 20

    name_font = _font(FONT_BOLD, 58)
    wrapped = textwrap.wrap(product.nume, width=22)[:2]
    for line in wrapped:
        y += _center_text(draw, y, line, name_font, MAROON) + 10
    y += 20

    stars = "★" * product.nota_mea + "☆" * (5 - product.nota_mea)
    y += _center_text(draw, y, stars, _font(FONT_BOLD, 54), GOLD) + 50

    seal_font = _font(FONT_BOLD, 30)
    seal_text = "TESTED BY DEEA"
    bbox = draw.textbbox((0, 0), seal_text, font=seal_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 28, 16
    sx = (W - tw) / 2 - pad_x
    draw.rounded_rectangle(
        [sx, y, sx + tw + pad_x * 2, y + th + pad_y * 2 + 10],
        radius=14, fill=WHITE, outline=PINK, width=3,
    )
    draw.text((sx + pad_x, y + pad_y), seal_text, font=seal_font, fill=MAROON)

    tag_font = _font(FONT_REGULAR, 30)
    _center_text(draw, H - 160, "Real products. My honest take.", tag_font, MAROON)
    if host:
        _center_text(draw, H - 100, host, _font(FONT_BOLD, 28), PINK)

    return img


def render_story_png(product, host):
    img = build_story_image(product, host)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
