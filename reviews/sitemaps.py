from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Collection, Product


class ProductSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return Product.objects.filter(activ=True)

    def lastmod(self, obj):
        return obj.data_postarii


class CollectionSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Collection.objects.all()

    def lastmod(self, obj):
        return obj.data_creare


class StaticViewSitemap(Sitemap):
    # Contact/Favorite excluse deliberat — pagini utilitare, fără conținut
    # unic de indexat (Favorite depinde oricum de localStorage per vizitator).
    priority = 0.5
    changefreq = "weekly"

    def items(self):
        return ["reviews:feed", "reviews:collections", "reviews:about"]

    def location(self, item):
        return reverse(item)


sitemaps = {
    "produse": ProductSitemap,
    "colectii": CollectionSitemap,
    "pagini": StaticViewSitemap,
}
