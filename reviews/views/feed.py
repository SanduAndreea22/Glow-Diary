from django.views.generic import ListView

from ..models import Product
from ..queries import (
    DEFAULT_SORT,
    MIN_PRODUSE_PENTRU_CONTOR,
    colectia_saptamanii,
    cu_numar_pareri,
    feed_stats,
    filtreaza_produse,
)


class FeedView(ListView):
    model = Product
    template_name = "reviews/feed.html"
    context_object_name = "produse"
    paginate_by = 12

    def get_queryset(self):
        qs = cu_numar_pareri(Product.objects.filter(activ=True).select_related("categorie"))
        return filtreaza_produse(qs, self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["categorie_activa"] = self.request.GET.get("categorie", "")
        ctx["nota_min_activa"] = self.request.GET.get("nota_min", "")
        ctx["sursa_activa"] = self.request.GET.get("sursa", "")
        ctx["tag_activ"] = self.request.GET.get("tag", "")
        ctx["pret_max_activ"] = self.request.GET.get("pret_max", "")
        ctx["sort_activ"] = self.request.GET.get("sort", "") or DEFAULT_SORT
        ctx["filtre_active"] = bool(
            ctx["nota_min_activa"] or ctx["sursa_activa"] or ctx["tag_activ"]
            or ctx["pret_max_activ"] or self.request.GET.get("sort", "")
        )
        stats = feed_stats()
        ctx["produsul_lunii_id"] = stats["produsul_lunii_id"]
        ctx["total_produse"] = stats["total_produse"]
        ctx["ultima_actualizare"] = stats["ultima_actualizare"]
        ctx["arata_contor_produse"] = stats["total_produse"] >= MIN_PRODUSE_PENTRU_CONTOR
        ctx["surse"] = stats["surse"]
        ctx["tag_uri_disponibile"] = stats["tag_uri"]
        ctx["categorii_navigare"] = stats["categorii_navigare"]
        if stats["an_curent_total"] >= MIN_PRODUSE_PENTRU_CONTOR:
            ctx["an_recap_an"] = stats["an_curent"]
        # Doar pe prima pagină, fără filtre — un hero nu are sens în mijlocul
        # unei liste deja filtrate/paginate.
        if self.request.GET.get("page") in (None, "1") and not ctx["filtre_active"] and not ctx["q"]:
            ctx["colectia_saptamanii"] = colectia_saptamanii()

        extra = self.request.GET.copy()
        extra.pop("page", None)
        ctx["querystring_extra"] = ("&" + extra.urlencode()) if extra else ""

        # Un singur loc care păstrează filtrele active (q/nota_min/sursa/sort)
        # atunci când se schimbă categoria — înainte, fiecare link de
        # categorie repeta manual, inline în template, același lanț de
        # {% if %}, cu risc mare ca un filtru nou adăugat să fie uitat la
        # unul din linkuri.
        fara_categorie = self.request.GET.copy()
        fara_categorie.pop("page", None)
        fara_categorie.pop("categorie", None)
        ctx["querystring_fara_categorie"] = fara_categorie.urlencode()

        if ctx.get("is_paginated"):
            page_obj = ctx["page_obj"]
            ctx["page_range"] = page_obj.paginator.get_elided_page_range(
                page_obj.number, on_each_side=1, on_ends=1
            )
        return ctx
