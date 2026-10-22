import os

from django.conf import settings
from django.core.checks import Error, Warning, register


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


@register(deploy=True)
def verifica_topologia_proxy(app_configs, **kwargs):
    """Rate limiting-ul (reviews/throttling.py) și lockout-ul de login
    (django-axes) sunt cheiate pe REMOTE_ADDR — corect doar dacă aplicația
    NU stă în spatele unui reverse proxy, sau dacă TRUST_X_FORWARDED_FOR e
    setat explicit după ce proxy-ul a fost verificat manual. Fără asta,
    pe o găzduire cu proxy în față (comun, inclusiv pe multe PaaS-uri),
    REMOTE_ADDR poate fi IP-ul proxy-ului — comun tuturor vizitatorilor —
    iar rate limiting-ul/lockout-ul ar deveni efectiv globale (un singur
    vizitator zgomotos poate bloca comentariile sau login-ul pentru toți
    cei din spatele aceluiași proxy). Warning, nu Error — nu există un
    default corect universal, decizia cere verificare manuală o singură
    dată, la fiecare deploy nou."""
    if settings.DEBUG or getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        return []
    return [
        Warning(
            "TRUST_X_FORWARDED_FOR e False (implicit) — verifică dacă acest "
            "deploy rulează în spatele unui reverse proxy.",
            hint=(
                "Dacă da, REMOTE_ADDR poate fi IP-ul proxy-ului pentru toți "
                "vizitatorii, nu adresa lor reală — rate limiting-ul "
                "(comentarii/contact) și lockout-ul de login (django-axes) "
                "ar deveni efectiv globale, nu per-vizitator. Setează "
                "TRUST_X_FORWARDED_FOR=True DOAR după ce confirmi manual că "
                "proxy-ul suprascrie (nu doar adaugă la) X-Forwarded-For. "
                "Dacă nu există niciun proxy în față, acest avertisment e "
                "de ignorat."
            ),
            id="reviews.W001",
        )
    ]


@register(deploy=True)
def verifica_admin_url(app_configs, **kwargs):
    """ADMIN_URL rămas pe valoarea implicită 'admin/' în producție — ușor
    de găsit prin scanare automată. Warning, nu Error — e hardening prin
    obscuritate, nu o cerință tehnică reală (contul e oricum protejat de
    parolă + lockout django-axes)."""
    if settings.DEBUG or settings.ADMIN_URL != "admin/":
        return []
    return [
        Warning(
            "ADMIN_URL e încă pe valoarea implicită 'admin/'.",
            hint=(
                "Schimbă ADMIN_URL în .env la ceva mai puțin previzibil, ca "
                "hardening minim împotriva scanărilor automate. Nu e o "
                "cerință critică (contul rămâne protejat de parolă + "
                "lockout), doar un strat suplimentar ieftin."
            ),
            id="reviews.W002",
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
