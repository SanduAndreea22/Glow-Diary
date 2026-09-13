from django.db.models import Avg, Count, Sum
from django.views.generic import TemplateView

from ..models import CATEGORIE_CHOICES, Product
from ..queries import MIN_PRODUSE_PENTRU_CONTOR, cu_numar_pareri


class AnRecapView(TemplateView):
    """„Best of anul" — un rezumat generat direct din datele existente, nu
    conținut scris separat de Deea. Sub pragul de produse dintr-un an,
    arătăm un mesaj prietenos, nu un 404 — un an nou, cu puține produse
    postate, e o stare validă, nu o eroare."""

    template_name = "reviews/an_recap.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        an = kwargs["an"]
        ctx["an"] = an

        produse_an = Product.objects.filter(activ=True, data_postarii__year=an)
        total = produse_an.count()
        ctx["total_produse"] = total
        ctx["are_destule_date"] = total >= MIN_PRODUSE_PENTRU_CONTOR
        if not ctx["are_destule_date"]:
            return ctx

        agregate = produse_an.aggregate(medie=Avg("nota_mea"), cheltuit=Sum("pret"))
        ctx["medie_generala"] = round(agregate["medie"], 1) if agregate["medie"] else None
        ctx["total_cheltuit"] = agregate["cheltuit"]
        ctx["recumparate_total"] = produse_an.filter(il_recumpar=True).count()

        ctx["top_produse"] = produse_an.order_by("-nota_mea", "-data_postarii")[:3]
        # Filtrăm în Python (nu queryset[:3]) — un top 3 „cele mai comentate"
        # nu are sens dacă include produse cu 0 comentarii doar ca să umple
        # locul rămas.
        candidati = cu_numar_pareri(produse_an).order_by("-comment_count", "-data_postarii")[:10]
        ctx["cele_mai_comentate"] = [p for p in candidati if p.comment_count][:3]

        brand_top = (
            produse_an.values("brand").annotate(total=Count("id")).order_by("-total", "brand").first()
        )
        ctx["brand_preferat"] = brand_top

        categorie_top = (
            produse_an.values("categorie").annotate(total=Count("id")).order_by("-total").first()
        )
        if categorie_top:
            ctx["categorie_preferata"] = dict(CATEGORIE_CHOICES).get(categorie_top["categorie"])
            ctx["categorie_preferata_total"] = categorie_top["total"]

        cel_mai_scump = produse_an.exclude(pret__isnull=True).order_by("-pret").first()
        ctx["cel_mai_scump"] = cel_mai_scump

        return ctx
