import os

from django.conf import settings
from django.core.checks import Error, register


@register(deploy=True)
def verifica_redis_in_productie(app_configs, **kwargs):
    """Fără REDIS_URL setat, rate limiting-ul (honeypot/comentarii/contact,
    bazat pe LocMemCache — per-proces) devine inconsistent între workeri cu
    mai mult de un proces, lăsând un spammer să ocolească limita
    distribuindu-se pe workeri diferiți. Eroare (nu doar warning) — un simplu
    avertisment poate fi omis din greșeală la deploy; o eroare care blochează
    `manage.py check --deploy` cere o decizie conștientă: fie REDIS_URL, fie
    confirmarea explicită (SINGLE_WORKER=True) că rulează un singur proces,
    caz în care LocMemCache e oricum consistent."""
    if settings.DEBUG or os.environ.get("REDIS_URL"):
        return []
    single_worker = os.environ.get("SINGLE_WORKER", "").strip().lower() in ("1", "true", "yes", "on")
    if single_worker:
        return []
    return [
        Error(
            "REDIS_URL nu e setat, deși DEBUG=False.",
            hint=(
                "Rate limiting-ul (bazat pe cache LocMemCache, per-proces) "
                "devine inconsistent între workeri dacă rulezi mai mult de "
                "un proces (gunicorn/uwsgi). Setează REDIS_URL pentru cache "
                "partajat real, sau SINGLE_WORKER=True dacă ești sigură că "
                "rulezi explicit un singur proces."
            ),
            id="reviews.E002",
        )
    ]


@register()
def verifica_fonturile_story(app_configs, **kwargs):
    """Fără fonturile bundle-uite, imaginile de Story (vezi story_image.py)
    se randează silențios cu fontul implicit PIL — urât, neconform brandului
    — și singurul semnal ar fi un logger.warning pe care nimeni nu-l
    citește garantat. Mai bine un `manage.py check` care eșuează vizibil
    la un deploy cu fonturi lipsă."""
    erori = []
    for nume_fisier in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "Fraunces-Black.ttf", "Fraunces-Italic.ttf"):
        cale = settings.BASE_DIR / "static" / "fonts" / nume_fisier
        if not cale.is_file():
            erori.append(
                Error(
                    f"Fontul lipsește: {cale}",
                    hint=(
                        "Imaginile de Story (Descarcă pentru Story) vor folosi "
                        "un font implicit, neconform brandului, în loc de acesta."
                    ),
                    id="reviews.E001",
                )
            )
    return erori
