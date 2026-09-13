from django.contrib.humanize.templatetags.humanize import naturaltime
from django.http import JsonResponse
from django.views import View

from ..models import Product
from ..queries import cu_numar_pareri, feed_stats, filtreaza_produse

MAX_SLUGURI_FAVORITE = 50  # cât poate ține realist localStorage-ul de Favorite
MAX_REZULTATE_CAUTARE = 24  # destul pentru câteva "ecrane" de scroll pe /api/search/


def _product_card_data(p, produsul_lunii_id=None):
    # comment_count și produsul_lunii trebuie să existe și aici, nu doar în
    # _product_card.html — altfel sigiliul "PRODUSUL LUNII" și numărul de
    # păreri dispar tăcut de pe cardurile randate din căutarea live/Favorite
    # (cele două căi de randare a unui card au divergut altfel fără să pice
    # niciun test).
    return {
        "nume": p.nume,
        "brand": p.brand,
        "categorie": p.get_categorie_display(),
        "nuanta": p.nuanta,
        "sursa": p.sursa,
        "poza": p.poza.url if p.poza else "",
        "nota": p.nota_mea,
        "il_recumpar": bool(p.il_recumpar),
        "snippet": p.parerea_mea[:140],
        "url": p.get_absolute_url(),
        "slug": p.slug,
        "postat": str(naturaltime(p.data_postarii)),
        "comment_count": getattr(p, "comment_count", 0),
        "produsul_lunii": bool(produsul_lunii_id and p.id == produsul_lunii_id),
    }


class FavoritesDataView(View):
    def get(self, request):
        slugs = [s for s in request.GET.get("slugs", "").split(",") if s][:MAX_SLUGURI_FAVORITE]
        produse = cu_numar_pareri(Product.objects.filter(slug__in=slugs, activ=True))
        produsul_lunii_id = feed_stats()["produsul_lunii_id"]
        data = [_product_card_data(p, produsul_lunii_id) for p in produse]
        return JsonResponse({"produse": data})


class SearchDataView(View):
    def get(self, request):
        qs = filtreaza_produse(cu_numar_pareri(Product.objects.filter(activ=True)), request)
        produsul_lunii_id = feed_stats()["produsul_lunii_id"]
        data = [_product_card_data(p, produsul_lunii_id) for p in qs[:MAX_REZULTATE_CAUTARE]]
        return JsonResponse({"produse": data})
