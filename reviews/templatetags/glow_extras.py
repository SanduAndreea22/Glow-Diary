"""Template tag-uri specifice site-ului. `stars_svg` e singurul loc care
știe cum arată o stea plină/goală/jumătate — folosit de toate paginile
randate server-side, ca stelele să nu poată diverge vizual de-a lungul
site-ului (varianta client-side, pentru cardurile randate din JS la
căutare/Favorite, e GlowStars.render din static/js/cards.js — aceeași
formă de stea, desenată din același path SVG)."""

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

# Un singur path, refolosit plin/gol/jumătate — ca varianta JS (cards.js)
# să deseneze exact aceeași formă de stea, nu una vizual apropiată.
STAR_PATH = "M12 2.5l2.95 6.02 6.65.97-4.8 4.68 1.13 6.62L12 17.7l-5.93 3.12 1.13-6.62-4.8-4.68 6.65-.97z"


def _star_full():
    return f'<svg class="star-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="{STAR_PATH}" fill="currentColor"/></svg>'


def _star_empty():
    return (
        f'<svg class="star-ico star-ico-empty" viewBox="0 0 24 24" aria-hidden="true">'
        f'<path d="{STAR_PATH}" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>'
    )


def _star_half():
    # Steaua goală stă dedesubt ca fundal; peste ea, aceeași stea plină,
    # decupată la 50% din lățime — nu un al treilea desen separat, ca cele
    # două jumătăți să se alinieze mereu perfect, indiferent de mărime.
    return (
        '<span class="star-ico star-ico-half">'
        + _star_empty().replace('class="star-ico star-ico-empty"', 'class="star-ico-empty"')
        + f'<svg class="star-ico-half-fill" viewBox="0 0 24 24" aria-hidden="true"><path d="{STAR_PATH}" fill="currentColor"/></svg>'
        + "</span>"
    )


@register.simple_tag
def stars_svg(value, max_stars=5):
    """Randează `max_stars` stele SVG (implicit 5) pornind de la `value`
    (0-max_stars, poate fi fracționar — ex. media notelor cititoarelor).
    Rotunjire la cea mai apropiată jumătate de stea."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    value = max(0.0, min(float(max_stars), value))

    full = int(value)
    remainder = value - full
    half = 0.25 <= remainder < 0.75
    if remainder >= 0.75:
        full += 1
        half = False
    empty = max(0, max_stars - full - (1 if half else 0))

    parts = [_star_full()] * full
    if half:
        parts.append(_star_half())
    parts += [_star_empty()] * empty

    label = escape(f"{value:g} din {max_stars} stele")
    html = f'<span class="stars-svg" role="img" aria-label="{label}">' + "".join(parts) + "</span>"
    return mark_safe(html)
