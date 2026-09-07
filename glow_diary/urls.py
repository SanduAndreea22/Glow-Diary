"""
URL configuration for glow_diary project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("reviews.urls")),
]


def _service_worker(request):
    # Servit chiar la /sw.js (nu sub /static/, și nu printr-un redirect —
    # browserele resping un script de service worker obținut printr-un
    # redirect) ca scope-ul lui să acopere tot site-ul, nu doar /static/.
    with open(settings.BASE_DIR / "static" / "sw.js", "rb") as f:
        return HttpResponse(f.read(), content_type="application/javascript")


urlpatterns += [path("sw.js", _service_worker, name="service_worker")]

# Proiectul ăsta nu are un webserver dedicat (nginx/S3) pentru media în
# producție, așa că Django servește pozele de produs indiferent de DEBUG.
# La trafic mare, ideal se mută pe storage extern (S3/Cloudinary) + CDN.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
