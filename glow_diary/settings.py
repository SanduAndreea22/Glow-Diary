"""
Django settings for glow_diary project.

Toate valorile sensibile/specifice mediului vin din variabile de mediu
(vezi .env.example). Local, `.env` e încărcat automat de python-dotenv;
în producție, setează variabilele direct pe server/platformă — nu
folosi niciodată un fișier `.env` commis în git.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


# SECURITY WARNING: keep the secret key used in production secret!
# Fără variabilă de mediu setată, aplicația refuză să pornească —
# nu există niciun fallback hardcodat/commis în git.
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY nu e setat. Copiază .env.example în .env și completează-l "
        "(local), sau setează variabila de mediu SECRET_KEY (producție)."
    )

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool("DEBUG", default=False)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", default="localhost,127.0.0.1")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "reviews",
    "axes",
    # django-cleanup ultimul — se agață de post_delete/pre_save pe orice
    # FileField/ImageField (Product.poza, ProductImage.imagine,
    # Collection.coperta, Comment.imagine) și șterge fișierul fizic de pe
    # disc odată cu rândul/la înlocuirea unei poze existente. Fără el,
    # fișierele rămâneau orfane la nesfârșit (Django nu face asta implicit).
    "django_cleanup.apps.CleanupConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Ultimul — django-axes cere asta explicit, ca să vadă rezultatul final
    # al autentificării înainte de a decide dacă blochează.
    "axes.middleware.AxesMiddleware",
]

AUTHENTICATION_BACKENDS = [
    # Primul — django-axes trebuie să intercepteze login-ul înaintea
    # backend-ului implicit, ca să poată bloca după N încercări eșuate.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Un singur cont admin controlează tot site-ul (produse, comentarii,
# mesaje) — fără lockout, parola era limitată doar de
# MinimumLengthValidator(12), fără nicio blocare după încercări eșuate
# repetate (brute-force nelimitat, deși lent).
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # oră
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT = False

ROOT_URLCONF = "glow_diary.urls"

CSRF_FAILURE_VIEW = "reviews.views.csrf_failure"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "reviews.context_processors.social_links",
            ],
        },
    },
]

WSGI_APPLICATION = "glow_diary.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        # Implicit e 8 — pe un site cu un singur cont admin care controlează
        # tot, o parolă minimă mai lungă e o linie de apărare gratuită.
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "ro"

TIME_ZONE = "Europe/Bucharest"

USE_I18N = True

USE_TZ = True


# Static & media files
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Praguri de upload declarate explicit (nu lăsate pe implicitul „ascuns" al
# Django) — FILE_UPLOAD_MAX_MEMORY_SIZE e doar pragul de spooling pe disc
# pentru un fișier (nu un refuz), iar respingerea reală a pozelor prea mari
# de pe formularul public de comentarii se face în CommentForm.clean_imagine
# (MAX_UPLOAD_IMAGINE_BYTES). Valorile de mai jos rămân cele implicite din
# Django — sunt declarate ca să fie clar că alegerea e conștientă.
FILE_UPLOAD_MAX_MEMORY_SIZE = 2621440
DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440

# Nume de fișier cu hash (style.a1b2c3.css) generate la `collectstatic` —
# fără asta, vizitatoarele care revin pot vedea CSS/JS învechit din cache-ul
# browserului după un deploy, în funcție de headerele serverului. Doar în
# producție (DEBUG=False): ManifestStaticFilesStorage cere `collectstatic`
# rulat înainte ca {% static %} să funcționeze deloc — un pas în plus care
# n-are ce căuta în fluxul simplu de dezvoltare locală (`runserver` direct).
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Cache — folosit și pentru rate limiting (honeypot/comentarii/contact).
# LocMemCache e per-proces: cu mai mult de un worker în producție,
# rate limiting-ul devine inconsistent între procese. Setează REDIS_URL
# în producție ca să foloseşti un cache partajat real.
REDIS_URL = os.environ.get("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }


# Rate limiting / IP detection
# ---------------------------------------------------------------------------
# X-Forwarded-For e setabil de orice client și NU trebuie avut încredere în
# el decât dacă aplicația rulează garantat în spatele unui proxy de încredere
# care suprascrie (nu doar adaugă la) acest header înainte să ajungă la noi
# (ex. Render, Heroku, Fly.io, un load balancer configurat corect).
# Implicit e dezactivat — rate limiting foloseşte doar REMOTE_ADDR.
TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", default=False)


# Email — folosit pentru notificarea erorilor 500 către ADMINS.
# Implicit scrie în consolă (dev); setează EMAIL_* în producție pentru SMTP real.
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@glowdiary.local")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

_admin_email = os.environ.get("ADMIN_EMAIL")
ADMINS = [("Deea", _admin_email)] if _admin_email else []
MANAGERS = ADMINS


# Logging — în producție (DEBUG=False) Django trimite automat un email către
# ADMINS la fiecare eroare 500 (handler-ul django.utils.log.AdminEmailHandler,
# activat implicit de LOGGING de mai jos), plus tot ce e WARNING+ apare în
# consola serverului (captat de orice platformă de hosting în logurile ei).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}


# Admin URL configurabil — schimbă ADMIN_URL în producție (ex. "secret-panel/")
# în loc de "admin/" implicit, ca hardening minim împotriva scanărilor automate.
ADMIN_URL = os.environ.get("ADMIN_URL", "admin/").lstrip("/")
if not ADMIN_URL.endswith("/"):
    ADMIN_URL += "/"


# Linkuri social afișate în footer — opționale. Necompletate, iconițele
# nu apar deloc (nu linkuim către profiluri inexistente). Instagram are
# valoare implicită (contul real al Deei); poate fi schimbat oricând din
# variabila de mediu INSTAGRAM_URL, fără cod nou.
INSTAGRAM_URL = os.environ.get(
    "INSTAGRAM_URL", "https://www.instagram.com/s_andreea_22"
)
TIKTOK_URL = os.environ.get("TIKTOK_URL", "")


# Niciun script din proiect nu are nevoie să citească din JS cookie-ul CSRF
# (formularele trimit tokenul din câmpul ascuns randat de {% csrf_token %},
# nu din JS) — HttpOnly e hardening gratuit, activ și local.
CSRF_COOKIE_HTTPONLY = True

# Setări de securitate active doar când DEBUG=False (producție), ca să nu
# strice dezvoltarea locală peste HTTP simplu.
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

    # Pe orice host care termină SSL la un proxy din față și retrimite
    # cererea ca HTTP simplu către aplicație (comun pe PaaS-uri, inclusiv
    # PythonAnywhere), Django crede că request-ul e nesecurizat și
    # SECURE_SSL_REDIRECT redirecționează la infinit. TRUST_X_FORWARDED_PROTO
    # e opt-in, ca SECURE_PROXY_SSL_HEADER să nu fie activat orbește —
    # verifică întâi (manual, pe domeniul real) că proxy-ul chiar trimite
    # X-Forwarded-Proto, altfel oricine poate falsifica headerul.
    if env_bool("TRUST_X_FORWARDED_PROTO", default=False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
