"""
URL configuration for glow_diary project.
"""

from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import Http404, HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve

from reviews.sitemaps import sitemaps

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("", include("reviews.urls")),
]


def _robots_txt(request):
    # robots.txt indică sitemap-ul explicit — Google descoperă și
    # (re)indexează paginile mult mai repede decât dacă ar trebui să dea
    # peste ele doar urmărind linkuri.
    host = request.build_absolute_uri("/sitemap.xml")
    content = f"User-agent: *\nAllow: /\nSitemap: {host}\n"
    return HttpResponse(content, content_type="text/plain")


urlpatterns += [path("robots.txt", _robots_txt, name="robots_txt")]


def _google_site_verification(request):
    # Fișierul de verificare a domeniului din Google Search Console
    # (metoda "fișier HTML") — trebuie servit exact la rădăcina site-ului,
    # nu sub /static/, altfel Google nu-l găsește la verificare.
    verif_path = settings.BASE_DIR / "static" / "google825b1c8a7aef47c7.html"
    try:
        content = verif_path.read_bytes()
    except FileNotFoundError:
        raise Http404("Fișierul de verificare Google lipsește.")
    return HttpResponse(content, content_type="text/html")


urlpatterns += [
    path(
        "google825b1c8a7aef47c7.html",
        _google_site_verification,
        name="google_site_verification",
    )
]


def _service_worker(request):
    # Servit chiar la /sw.js (nu sub /static/, și nu printr-un redirect —
    # browserele resping un script de service worker obținut printr-un
    # redirect) ca scope-ul lui să acopere tot site-ul, nu doar /static/.
    sw_path = settings.BASE_DIR / "static" / "sw.js"
    try:
        content = sw_path.read_bytes()
    except FileNotFoundError:
        raise Http404("sw.js lipsește.")
    return HttpResponse(content, content_type="application/javascript")


urlpatterns += [path("sw.js", _service_worker, name="service_worker")]

# Proiectul ăsta nu are un webserver dedicat (nginx/S3) pentru media în
# producție, așa că Django trebuie să servească pozele de produs indiferent
# de DEBUG. django.conf.urls.static.static() NU face asta — helper-ul e gândit
# strict pentru development și returnează o listă goală când DEBUG=False,
# ceea ce ar lăsa toate pozele de produs să dea 404 în producție. re_path()
# de mai jos înregistrează ruta necondiționat.
# La trafic mare, ideal se mută pe storage extern (S3/Cloudinary) + CDN.
urlpatterns += [
    re_path(
        r"^%s(?P<path>.*)$" % settings.MEDIA_URL.lstrip("/"),
        serve,
        {"document_root": settings.MEDIA_ROOT},
    ),
]
