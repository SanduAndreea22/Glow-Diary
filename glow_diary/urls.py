"""
URL configuration for glow_diary project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("reviews.urls")),
]

# Proiectul ăsta nu are un webserver dedicat (nginx/S3) pentru media în
# producție, așa că Django servește pozele de produs indiferent de DEBUG.
# La trafic mare, ideal se mută pe storage extern (S3/Cloudinary) + CDN.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
