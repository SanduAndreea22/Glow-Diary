"""Rate limiting minimal, pe bază de cache — folosit de toate formularele
publice (comentarii, contact) și de randarea Story-image."""

from django.conf import settings
from django.core.cache import cache

RATE_LIMIT_SECONDS = 60
GLOBAL_RATE_LIMIT_MAX = 5
GLOBAL_RATE_LIMIT_WINDOW = 600  # 10 minute

# Prag separat, mult mai generos, pentru endpoint-urile de API publice
# (căutare live, favorite, recomandări) — spre deosebire de formularele de
# comentariu/contact, acestea sunt GET-uri ieftine, declanșate la fiecare
# apăsare de tastă în căutarea live; pragul strict de mai sus (5/10min) ar
# rupe căutarea normală după câteva litere tastate.
API_RATE_LIMIT_MAX = 60
API_RATE_LIMIT_WINDOW = 60  # 1 minut


def client_ip(request):
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def global_rate_limited(ip, scope, max_requests=GLOBAL_RATE_LIMIT_MAX, window=GLOBAL_RATE_LIMIT_WINDOW):
    """Limitează nr. de cereri (orice produs/pagină) per IP într-o fereastră dată.

    `add` + `incr` (nu `get` + `set`) ca să fie atomic — două cereri simultane
    de la același IP nu pot amândouă „vedea" contorul vechi și trece de limită.
    """
    key = f"rl-global:{scope}:{ip}"
    if cache.add(key, 1, window):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)
        return False
    return count > max_requests


def api_rate_limited(request):
    """Rate limiting comun pentru endpoint-urile de API publice (căutare
    live, favorite, recomandări) — un singur scope împărțit între toate
    trei, cu pragul generos de mai sus (API_RATE_LIMIT_MAX/WINDOW)."""
    return global_rate_limited(
        client_ip(request), "api", max_requests=API_RATE_LIMIT_MAX, window=API_RATE_LIMIT_WINDOW
    )
