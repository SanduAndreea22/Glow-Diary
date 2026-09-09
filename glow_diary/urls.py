"""
URL configuration for glow_diary project.
"""

from django.conf import settings
from django.contrib import admin
from django.http import Http404, HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("reviews.urls")),
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
