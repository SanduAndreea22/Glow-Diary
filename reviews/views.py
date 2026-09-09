import hashlib
import io
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from .forms import CommentForm, ContactForm
from .models import CATEGORIE_CHOICES, Collection, Product
from .story_image import render_story_png

RATE_LIMIT_SECONDS = 60
GLOBAL_RATE_LIMIT_MAX = 5
GLOBAL_RATE_LIMIT_WINDOW = 600  # 10 minute

FEED_STATS_CACHE_TTL = 300  # 5 minute
STORY_IMAGE_CACHE_TTL = 60 * 60 * 24  # 24h — randarea cu Pillow e costisitoare


def _client_ip(request):
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _global_rate_limited(ip, scope):
    """Limitează nr. de postări (orice produs/pagină) per IP într-o fereastră mai lungă.

    `add` + `incr` (nu `get` + `set`) ca să fie atomic — două cereri simultane
    de la același IP nu pot amândouă „vedea" contorul vechi și trece de limită.
    """
    key = f"rl-global:{scope}:{ip}"
    if cache.add(key, 1, GLOBAL_RATE_LIMIT_WINDOW):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, GLOBAL_RATE_LIMIT_WINDOW)
        return False
    return count > GLOBAL_RATE_LIMIT_MAX


SORT_OPTIONS = {
    "recent": ("-data_postarii",),
    "nota": ("-nota_mea", "-data_postarii"),
}
DEFAULT_SORT = "recent"


def _filtreaza_produse(qs, request):
    """Filtrele comune (căutare/categorie/notă minimă/sursă/sortare), aplicate
    identic pe feed-ul cu reload și pe căutarea live din /api/search/ — un
    singur loc, ca cele două să nu poată desincroniza."""
    q = request.GET.get("q", "").strip()
    categorie = request.GET.get("categorie", "").strip()
    nota_min = request.GET.get("nota_min", "").strip()
    sursa = request.GET.get("sursa", "").strip()
    sort = request.GET.get("sort", "").strip()

    if q:
        qs = qs.filter(Q(nume__icontains=q) | Q(brand__icontains=q))
    if categorie:
        qs = qs.filter(categorie=categorie)
    if nota_min:
        try:
            qs = qs.filter(nota_mea__gte=int(nota_min))
        except ValueError:
            pass
    if sursa:
        qs = qs.filter(sursa=sursa)

    return qs.order_by(*SORT_OPTIONS.get(sort, SORT_OPTIONS[DEFAULT_SORT]))


def _cu_numar_pareri(qs):
    return qs.annotate(
        comment_count=Count("comentarii", filter=Q(comentarii__aprobat=True))
    ).order_by("-data_postarii")


def _produsul_lunii():
    o_luna_in_urma = timezone.now() - timedelta(days=30)
    top = (
        Product.objects.annotate(
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


def _feed_stats():
    """Cache scurt pentru statisticile din header-ul feed-ului (produsul lunii, total)."""
    stats = cache.get("feed-stats")
    if stats is None:
        stats = {
            "produsul_lunii_id": _produsul_lunii(),
            "total_produse": Product.objects.count(),
        }
        cache.set("feed-stats", stats, FEED_STATS_CACHE_TTL)
    return stats


class FeedView(ListView):
    model = Product
    template_name = "reviews/feed.html"
    context_object_name = "produse"
    paginate_by = 12

    def get_queryset(self):
        qs = _cu_numar_pareri(Product.objects.all())
        return _filtreaza_produse(qs, self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categorii"] = CATEGORIE_CHOICES
        ctx["q"] = self.request.GET.get("q", "")
        ctx["categorie_activa"] = self.request.GET.get("categorie", "")
        ctx["nota_min_activa"] = self.request.GET.get("nota_min", "")
        ctx["sursa_activa"] = self.request.GET.get("sursa", "")
        ctx["sort_activ"] = self.request.GET.get("sort", "") or DEFAULT_SORT
        ctx["surse"] = (
            Product.objects.exclude(sursa="")
            .order_by("sursa")
            .values_list("sursa", flat=True)
            .distinct()
        )
        ctx["filtre_active"] = bool(
            ctx["nota_min_activa"] or ctx["sursa_activa"] or self.request.GET.get("sort", "")
        )
        stats = _feed_stats()
        ctx["produsul_lunii_id"] = stats["produsul_lunii_id"]
        ctx["total_produse"] = stats["total_produse"]

        extra = self.request.GET.copy()
        extra.pop("page", None)
        ctx["querystring_extra"] = ("&" + extra.urlencode()) if extra else ""

        if ctx.get("is_paginated"):
            page_obj = ctx["page_obj"]
            ctx["page_range"] = page_obj.paginator.get_elided_page_range(
                page_obj.number, on_each_side=1, on_ends=1
            )
        return ctx


class ProductDetailView(DetailView):
    model = Product
    template_name = "reviews/product_detail.html"
    context_object_name = "produs"

    def get_queryset(self):
        return Product.objects.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["comentarii"] = self.object.comentarii.filter(aprobat=True)
        ctx["form"] = kwargs.get("form", CommentForm())
        galerie = list(self.object.imagini.all())
        pozele = ([self.object.poza] if self.object.poza else []) + [
            img.imagine for img in galerie if img.imagine
        ]
        ctx["galerie"] = pozele
        ctx["similare"] = _cu_numar_pareri(
            Product.objects.filter(categorie=self.object.categorie).exclude(pk=self.object.pk)
        )[:3]
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = CommentForm(request.POST)
        ip = _client_ip(request)

        # cache.add e atomic: „ocupă" lacătul doar dacă nu exista deja — spre
        # deosebire de get+set, două cereri simultane nu pot trece amândouă.
        cache_key = f"comment-rl:{ip}:{self.object.pk}"
        if not cache.add(cache_key, True, RATE_LIMIT_SECONDS):
            messages.error(
                request, "Ai comentat recent la acest produs — mai încearcă peste un minut."
            )
            return redirect(self.object.get_absolute_url())

        if _global_rate_limited(ip, "comment"):
            cache.delete(cache_key)
            messages.error(
                request,
                "Ai lăsat destule păreri pentru moment — mai încearcă peste câteva minute.",
            )
            return redirect(self.object.get_absolute_url())

        if form.is_valid():
            comment = form.save(commit=False)
            comment.product = self.object
            if not comment.nume:
                comment.nume = "anonim"
            comment.save()
            messages.success(request, "Mulțumesc pentru părere! ✨")
            return redirect(self.object.get_absolute_url())

        # nu a fost o postare reală (validare eșuată/honeypot) — eliberăm lacătul
        cache.delete(cache_key)

        if not form.errors.get("comentariu") and not form.errors.get("nume"):
            # eroare "ascunsă" (honeypot) — mesaj generic, fără să dezvăluim mecanismul
            messages.error(request, "Nu am putut trimite comentariul — mai încearcă o dată.")
            return redirect(self.object.get_absolute_url())

        return self.render_to_response(self.get_context_data(form=form))


class ProductStoryImageView(View):
    def get(self, request, slug):
        produs = get_object_or_404(Product, slug=slug)
        host = request.get_host()
        # Cheia include poza, nota și un hash pe brand/nume (ambele desenate
        # pe imagine) — ca imaginea din cache să nu rămână învechită dacă
        # Deea corectează o greșeală de tastare sau schimbă poza/nota.
        content_hash = hashlib.md5(
            f"{produs.brand}|{produs.nume}".encode()
        ).hexdigest()[:12]
        cache_key = (
            f"story-img:{produs.slug}:{produs.poza.name if produs.poza else ''}"
            f":{produs.nota_mea}:{content_hash}:{host}"
        )
        png_bytes = cache.get(cache_key)
        if png_bytes is None:
            # Randarea propriu-zisă (Pillow) e de departe cel mai costisitor
            # request din site — limităm doar cazurile de cache miss (nu și
            # descărcările repetate ale unei imagini deja randate), ca cineva
            # care parcurge sistematic toate sluglurile să nu poată forța
            # randări simultane nelimitate.
            if _global_rate_limited(_client_ip(request), "story-render"):
                return HttpResponse(
                    "Prea multe imagini generate deodată — mai încearcă peste câteva minute.",
                    status=429,
                )
            png_bytes = render_story_png(produs, host).getvalue()
            cache.set(cache_key, png_bytes, STORY_IMAGE_CACHE_TTL)
        response = FileResponse(io.BytesIO(png_bytes), content_type="image/png")
        response["Content-Disposition"] = f'attachment; filename="{produs.slug}-story.png"'
        return response


class CollectionListView(ListView):
    model = Collection
    template_name = "reviews/collections.html"
    context_object_name = "colectii"

    def get_queryset(self):
        return (
            Collection.objects.annotate(produse_count=Count("produse", distinct=True))
            .filter(produse_count__gt=0)
        )


class CollectionDetailView(DetailView):
    model = Collection
    template_name = "reviews/collection_detail.html"
    context_object_name = "colectie"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["produse"] = _cu_numar_pareri(self.object.produse.all())
        return ctx


class FavoritesView(TemplateView):
    template_name = "reviews/favorites.html"


def _product_card_data(p):
    return {
        "nume": p.nume,
        "brand": p.brand,
        "categorie": p.get_categorie_display(),
        "nuanta": p.nuanta,
        "sursa": p.sursa,
        "poza": p.poza.url if p.poza else "",
        "stele": p.stele,
        "snippet": p.parerea_mea[:140],
        "url": p.get_absolute_url(),
        "slug": p.slug,
        "postat": str(naturaltime(p.data_postarii)),
    }


class FavoritesDataView(View):
    def get(self, request):
        slugs = [s for s in request.GET.get("slugs", "").split(",") if s][:50]
        produse = Product.objects.filter(slug__in=slugs)
        data = [_product_card_data(p) for p in produse]
        return JsonResponse({"produse": data})


class SearchDataView(View):
    def get(self, request):
        qs = _filtreaza_produse(Product.objects.all(), request)
        data = [_product_card_data(p) for p in qs[:24]]
        return JsonResponse({"produse": data})


class AboutView(TemplateView):
    template_name = "reviews/about.html"


class ContactView(TemplateView):
    template_name = "reviews/contact.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = kwargs.get("form", ContactForm())
        return ctx

    def post(self, request, *args, **kwargs):
        ip = _client_ip(request)
        cache_key = f"contact-rl:{ip}"
        if not cache.add(cache_key, True, RATE_LIMIT_SECONDS):
            messages.error(request, "Ai trimis deja un mesaj recent — revin eu cât pot.")
            return redirect("reviews:contact")

        if _global_rate_limited(ip, "contact"):
            cache.delete(cache_key)
            messages.error(request, "Ai trimis destule mesaje pentru moment — mai încearcă peste câteva minute.")
            return redirect("reviews:contact")

        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Mesajul tău a ajuns la mine, mulțumesc! 💌")
            return redirect("reviews:contact")

        cache.delete(cache_key)

        if not form.errors.get("mesaj") and not form.errors.get("email"):
            messages.error(request, "Nu am putut trimite mesajul — mai încearcă o dată.")
            return redirect("reviews:contact")

        return self.render_to_response(self.get_context_data(form=form))


def csrf_failure(request, reason=""):
    """CSRF_FAILURE_VIEW — pagină în stilul site-ului, nu default-ul Django,
    pentru cazul (sesiune expirată / cookies blocate) în care un formular
    public eșuează la verificarea CSRF."""
    return render(request, "403_csrf.html", status=403)
