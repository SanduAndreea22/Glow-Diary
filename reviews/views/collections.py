from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.views.generic import DetailView, ListView

from ..models import Collection
from ..queries import ataseaza_poze_colaj, cu_numar_pareri

# Aceeași valoare ca FeedView.paginate_by — fără limită, ambele liste
# (colecții, produse dintr-o colecție) creșteau nemărginit odată cu
# conținutul; redus azi, dar o plasă de siguranță reală la volum mare.
PRODUSE_PE_PAGINA = 12


class CollectionListView(ListView):
    model = Collection
    template_name = "reviews/collections.html"
    context_object_name = "colectii"
    paginate_by = PRODUSE_PE_PAGINA

    def get_queryset(self):
        return list(
            Collection.objects.annotate(
                produse_count=Count("produse", filter=Q(produse__activ=True), distinct=True)
            )
            .filter(produse_count__gt=0)
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ataseaza_poze_colaj(ctx["colectii"])
        if ctx.get("is_paginated"):
            page_obj = ctx["page_obj"]
            ctx["page_range"] = page_obj.paginator.get_elided_page_range(
                page_obj.number, on_each_side=1, on_ends=1
            )
        return ctx


class CollectionDetailView(DetailView):
    model = Collection
    template_name = "reviews/collection_detail.html"
    context_object_name = "colectie"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # order_by explicit — altfel Paginator avertizează (și riscă rezultate
        # inconsistente între pagini): adnotarea cu Count() din cu_numar_pareri()
        # nu păstrează garantat ordinea implicită (Product.Meta.ordering).
        produse = cu_numar_pareri(
            self.object.produse.filter(activ=True)
            .select_related("categorie").prefetch_related("tag_uri")
        ).order_by("-data_postarii")
        paginator = Paginator(produse, PRODUSE_PE_PAGINA)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        ctx["produse"] = page_obj.object_list
        ctx["page_obj"] = page_obj
        ctx["is_paginated"] = page_obj.has_other_pages()
        if ctx["is_paginated"]:
            ctx["page_range"] = paginator.get_elided_page_range(
                page_obj.number, on_each_side=1, on_ends=1
            )
        return ctx
