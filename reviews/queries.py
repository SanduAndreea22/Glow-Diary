"""Interogări comune, folosite de mai multe view-uri (feed, colecții, API de
căutare/favorite) — un singur loc, ca ele să nu poată desincroniza."""

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

from .models import Product, Tag

FEED_STATS_CACHE_TTL = 300  # 5 minute
# Sub acest prag, un contor de tip "X produse testate" atrage atenția exact
# spre cât de la început e proiectul — afișăm în schimb data ultimei postări,
# un semnal care nu depinde de volum.
MIN_PRODUSE_PENTRU_CONTOR = 10

SORT_OPTIONS = {
    "recent": ("-data_postarii",),
    "nota": ("-nota_mea", "-data_postarii"),
}
DEFAULT_SORT = "recent"


def filtreaza_produse(qs, request):
    """Filtrele comune (căutare/categorie/notă minimă/sursă/sortare), aplicate
    identic pe feed-ul cu reload și pe căutarea live din /api/search/ — un
    singur loc, ca cele două să nu poată desincroniza."""
    q = request.GET.get("q", "").strip()
    categorie = request.GET.get("categorie", "").strip()
    nota_min = request.GET.get("nota_min", "").strip()
    sursa = request.GET.get("sursa", "").strip()
    tag = request.GET.get("tag", "").strip()
    pret_max = request.GET.get("pret_max", "").strip()
    sort = request.GET.get("sort", "").strip()

    if q:
        qs = qs.filter(Q(nume__icontains=q) | Q(brand__icontains=q))
    if categorie:
        qs = qs.filter(categorie=categorie)
    if nota_min:
        try:
            qs = qs.filter(nota_mea=int(nota_min))
        except ValueError:
            pass
    if sursa:
        qs = qs.filter(sursa=sursa)
    if tag:
        qs = qs.filter(tag_uri__slug=tag)
    if pret_max:
        try:
            qs = qs.filter(pret__lte=Decimal(pret_max))
        except InvalidOperation:
            pass

    return qs.order_by(*SORT_OPTIONS.get(sort, SORT_OPTIONS[DEFAULT_SORT]))


def cu_numar_pareri(qs):
    return qs.annotate(
        comment_count=Count("comentarii", filter=Q(comentarii__aprobat=True))
    ).order_by("-data_postarii")


def produsul_lunii():
    o_luna_in_urma = timezone.now() - timedelta(days=30)
    top = (
        Product.objects.filter(activ=True)
        .annotate(
            comment_count=Count(
                "comentarii",
                filter=Q(comentarii__aprobat=True, comentarii__data__gte=o_luna_in_urma),
            )
        )
        .filter(comment_count__gt=0)
        .order_by("-comment_count", "-data_postarii")
        .first()
    )
    return top.id if top else None


def feed_stats():
    """Cache scurt pentru statisticile din header-ul feed-ului (produsul lunii, total)."""
    stats = cache.get("feed-stats")
    if stats is None:
        active = Product.objects.filter(activ=True)
        ultimul = active.order_by("-data_postarii").values_list(
            "data_postarii", flat=True
        ).first()
        an_curent = timezone.now().year
        stats = {
            "produsul_lunii_id": produsul_lunii(),
            "total_produse": active.count(),
            "ultima_actualizare": ultimul,
            "an_curent": an_curent,
            "an_curent_total": active.filter(data_postarii__year=an_curent).count(),
            "categorii_cu_produse": set(
                active.values_list("categorie", flat=True).distinct()
            ),
            "surse": list(
                active.exclude(sursa="")
                .order_by("sursa")
                .values_list("sursa", flat=True)
                .distinct()
            ),
            "tag_uri": list(
                Tag.objects.filter(produse__in=active)
                .distinct()
                .order_by("nume")
                .values_list("slug", "nume")
            ),
        }
        cache.set("feed-stats", stats, FEED_STATS_CACHE_TTL)
    return stats
