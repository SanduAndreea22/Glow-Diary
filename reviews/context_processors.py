from django.conf import settings


def social_links(request):
    """Linkuri social în footer, dezactivate până sunt completate în .env
    (INSTAGRAM_URL / TIKTOK_URL) — nu inventăm profiluri inexistente."""
    return {
        "instagram_url": getattr(settings, "INSTAGRAM_URL", ""),
        "tiktok_url": getattr(settings, "TIKTOK_URL", ""),
    }
