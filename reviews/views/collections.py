from django.db.models import Count, Q
from django.views.generic import DetailView, ListView

from ..models import Collection
from ..queries import cu_numar_pareri


class CollectionListView(ListView):
    model = Collection
    template_name = "reviews/collections.html"
    context_object_name = "colectii"

    def get_queryset(self):
        return (
            Collection.objects.annotate(
                produse_count=Count("produse", filter=Q(produse__activ=True), distinct=True)
            )
            .filter(produse_count__gt=0)
        )


class CollectionDetailView(DetailView):
    model = Collection
    template_name = "reviews/collection_detail.html"
    context_object_name = "colectie"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["produse"] = cu_numar_pareri(
            self.object.produse.filter(activ=True).select_related("categorie")
        )
        return ctx
