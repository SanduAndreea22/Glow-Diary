from django.db.models import Avg, Count, Sum
from django.views.generic import TemplateView

from ..models import CATEGORIE_CHOICES, Product
from ..queries import MIN_PRODUSE_PENTRU_RECAP, cu_numar_pareri

# Câte produse candidate luăm în calcul înainte de a filtra "cele mai
# comentate" în Python la primele 3 (vezi mai jos de ce filtrarea se face
# după tăiere, nu într-un query separat) — generos peste 3, ca produsele cu
# 0 comentarii de la coadă să nu excludă din greșeală unele cu comentarii.
CANDIDATI_COMENTATE_LIMITA = 10
TOP_PRODUSE_LIMITA = 3
CELE_MAI_COMENTATE_LIMITA = 3


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
        ctx["are_destule_date"] = total >= MIN_PRODUSE_PENTRU_RECAP
        if not ctx["are_destule_date"]:
            return ctx

        agregate = produse_an.aggregate(medie=Avg("nota_mea"), cheltuit=Sum("pret"))
        ctx["medie_generala"] = round(agregate["medie"], 1) if agregate["medie"] else None
        ctx["total_cheltuit"] = agregate["cheltuit"]
        ctx["recumparate_total"] = produse_an.filter(il_recumpar=True).count()

        ctx["top_produse"] = produse_an.order_by(
            "-nota_mea", "-data_postarii"
        )[:TOP_PRODUSE_LIMITA]
        # Filtrăm în Python (nu queryset[:3]) — un top 3 „cele mai comentate"
        # nu are sens dacă include produse cu 0 comentarii doar ca să umple
        # locul rămas.
        candidati = cu_numar_pareri(produse_an).order_by(
            "-comment_count", "-data_postarii"
        )[:CANDIDATI_COMENTATE_LIMITA]
        ctx["cele_mai_comentate"] = [p for p in candidati if p.comment_count][:CELE_MAI_COMENTATE_LIMITA]

        brand_top = (
            produse_an.values("brand").annotate(total=Count("id")).order_by("-total", "brand").first()
        )
        ctx["brand_preferat"] = brand_top

        # Tiebreaker (`categorie`) adăugat pentru determinism la egalitate —
        # fără el, ordinea la egalitate de "total" nu e garantată de SQL.
        categorie_top = (
            produse_an.values("categorie")
            .annotate(total=Count("id"))
            .order_by("-total", "categorie")
            .first()
        )
        if categorie_top:
            ctx["categorie_preferata"] = dict(CATEGORIE_CHOICES).get(categorie_top["categorie"])
            ctx["categorie_preferata_total"] = categorie_top["total"]

        # Tiebreaker (`-data_postarii`) — la preț egal, arătăm cel mai recent
        # postat, nu un rezultat nedeterminist.
        cel_mai_scump = (
            produse_an.exclude(pret__isnull=True).order_by("-pret", "-data_postarii").first()
        )
        ctx["cel_mai_scump"] = cel_mai_scump

        return ctx
