"""Rate limiting minimal, pe bază de cache — folosit de toate formularele
publice (comentarii, contact) și de randarea Story-image."""

from django.conf import settings
from django.core.cache import cache

RATE_LIMIT_SECONDS = 60
GLOBAL_RATE_LIMIT_MAX = 5
GLOBAL_RATE_LIMIT_WINDOW = 600  # 10 minute


def client_ip(request):
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def global_rate_limited(ip, scope):
    """Limitează nr. de postări (orice produs/pagină) per IP într-o fereastră mai lungă.

    `add` + `incr` (nu `get` + `set`) ca să fie atomic — două cereri simultane
    de la același IP nu pot amândouă „vedea" contorul vechi și trece de limită.
    """
    key = f"rl-global:{scope}:{ip}"
    if cache.add(key, 1, GLOBAL_RATE_LIMIT_WINDOW):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, GLOBAL_RATE_LIMIT_WINDOW)
        return False
    return count > GLOBAL_RATE_LIMIT_MAX
