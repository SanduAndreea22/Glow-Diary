from django.contrib.humanize.templatetags.humanize import naturaltime
from django.http import JsonResponse
from django.views import View

from ..models import Product
from ..queries import cu_numar_pareri, feed_stats, filtreaza_produse

MAX_SLUGURI_FAVORITE = 50  # cât poate ține realist localStorage-ul de Favorite
MAX_REZULTATE_CAUTARE = 24  # destul pentru câteva "ecrane" de scroll pe /api/search/
MAX_RECOMANDARI = 6  # "Recomandat pentru tine" — un rând-două de carduri, nu un feed întreg


def _product_card_data(p, produsul_lunii_id=None):
    # comment_count și produsul_lunii trebuie să existe și aici, nu doar în
    # _product_card.html — altfel sigiliul "PRODUSUL LUNII" și numărul de
    # păreri dispar tăcut de pe cardurile randate din căutarea live/Favorite
    # (cele două căi de randare a unui card au divergut altfel fără să pice
    # niciun test).
    return {
        "nume": p.nume,
        "brand": p.brand,
        "categorie": p.categorie.nume,
        "categorie_slug": p.categorie.slug,
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
        produse = cu_numar_pareri(
            Product.objects.filter(slug__in=slugs, activ=True).select_related("categorie")
        )
        produsul_lunii_id = feed_stats()["produsul_lunii_id"]
        data = [_product_card_data(p, produsul_lunii_id) for p in produse]
        return JsonResponse({"produse": data})


class SearchDataView(View):
    def get(self, request):
        qs = filtreaza_produse(
            cu_numar_pareri(Product.objects.filter(activ=True).select_related("categorie")), request
        )
        produsul_lunii_id = feed_stats()["produsul_lunii_id"]
        data = [_product_card_data(p, produsul_lunii_id) for p in qs[:MAX_REZULTATE_CAUTARE]]
        return JsonResponse({"produse": data})


class RecomandariDataView(View):
    """"Recomandat pentru tine" — folosit doar client-side (vezi feed.html):
    JS-ul citește favoritele din localStorage, calculează categoria cea mai
    frecventă dintre ele prin /api/favorite-data/, apoi cere aici alte
    produse din acea categorie. Fără `categorie`, nu are ce recomanda."""

    def get(self, request):
        categorie = request.GET.get("categorie", "").strip()
        if not categorie:
            return JsonResponse({"produse": []})

        exclude = [s for s in request.GET.get("exclude", "").split(",") if s][:MAX_SLUGURI_FAVORITE]
        qs = (
            cu_numar_pareri(
                Product.objects.filter(activ=True, categorie__slug=categorie)
                .exclude(slug__in=exclude)
                .select_related("categorie")
            )
            .order_by("-nota_mea", "-data_postarii")
        )
        produsul_lunii_id = feed_stats()["produsul_lunii_id"]
        data = [_product_card_data(p, produsul_lunii_id) for p in qs[:MAX_RECOMANDARI]]
        return JsonResponse({"produse": data})
