from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from .forms import CommentForm, ContactForm
from .models import CATEGORIE_CHOICES, Collection, Product
from .story_image import render_story_png

RATE_LIMIT_SECONDS = 60
GLOBAL_RATE_LIMIT_MAX = 5
GLOBAL_RATE_LIMIT_WINDOW = 600  # 10 minute

FEED_STATS_CACHE_TTL = 300  # 5 minute


def _client_ip(request):
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _global_rate_limited(ip, scope):
    """Limitează nr. de postări (orice produs/pagină) per IP într-o fereastră mai lungă."""
    key = f"rl-global:{scope}:{ip}"
    count = cache.get(key, 0)
    if count >= GLOBAL_RATE_LIMIT_MAX:
        return True
    cache.set(key, count + 1, GLOBAL_RATE_LIMIT_WINDOW)
    return False


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
        q = self.request.GET.get("q", "").strip()
        categorie = self.request.GET.get("categorie", "").strip()
        nota_min = self.request.GET.get("nota_min", "").strip()

        if q:
            qs = qs.filter(Q(nume__icontains=q) | Q(brand__icontains=q))
        if categorie:
            qs = qs.filter(categorie=categorie)
        if nota_min:
            try:
                qs = qs.filter(nota_mea__gte=int(nota_min))
            except ValueError:
                pass
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categorii"] = CATEGORIE_CHOICES
        ctx["q"] = self.request.GET.get("q", "")
        ctx["categorie_activa"] = self.request.GET.get("categorie", "")
        ctx["nota_min_activa"] = self.request.GET.get("nota_min", "")
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

        cache_key = f"comment-rl:{ip}:{self.object.pk}"
        if cache.get(cache_key):
            messages.error(
                request, "Ai comentat recent la acest produs — mai încearcă puțin."
            )
            return redirect(self.object.get_absolute_url())

        if _global_rate_limited(ip, "comment"):
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
            cache.set(cache_key, True, RATE_LIMIT_SECONDS)
            messages.success(request, "Mulțumesc pentru părere! ✨")
            return redirect(self.object.get_absolute_url())

        if not form.errors.get("comentariu") and not form.errors.get("nume"):
            # eroare "ascunsă" (honeypot) — mesaj generic, fără să dezvăluim mecanismul
            messages.error(request, "Nu am putut trimite comentariul — mai încearcă o dată.")
            return redirect(self.object.get_absolute_url())

        return self.render_to_response(self.get_context_data(form=form))


def product_story_image(request, slug):
    produs = get_object_or_404(Product, slug=slug)
    buf = render_story_png(produs, request.get_host())
    response = FileResponse(buf, content_type="image/png")
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


def favorites_data(request):
    slugs = [s for s in request.GET.get("slugs", "").split(",") if s][:50]
    produse = Product.objects.filter(slug__in=slugs)
    data = [
        _product_card_data(p)
        for p in produse
    ]
    return JsonResponse({"produse": data})


def search_data(request):
    q = request.GET.get("q", "").strip()
    categorie = request.GET.get("categorie", "").strip()
    nota_min = request.GET.get("nota_min", "").strip()

    qs = Product.objects.all()
    if q:
        qs = qs.filter(Q(nume__icontains=q) | Q(brand__icontains=q))
    if categorie:
        qs = qs.filter(categorie=categorie)
    if nota_min:
        try:
            qs = qs.filter(nota_mea__gte=int(nota_min))
        except ValueError:
            pass

    data = [_product_card_data(p) for p in qs.order_by("-data_postarii")[:24]]
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
        if cache.get(cache_key):
            messages.error(request, "Ai trimis deja un mesaj recent — revin eu cât pot.")
            return redirect("reviews:contact")

        if _global_rate_limited(ip, "contact"):
            messages.error(request, "Ai trimis destule mesaje pentru moment — mai încearcă peste câteva minute.")
            return redirect("reviews:contact")

        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            cache.set(cache_key, True, RATE_LIMIT_SECONDS)
            messages.success(request, "Mesajul tău a ajuns la mine, mulțumesc! 💌")
            return redirect("reviews:contact")

        if not form.errors.get("mesaj") and not form.errors.get("email"):
            messages.error(request, "Nu am putut trimite mesajul — mai încearcă o dată.")
            return redirect("reviews:contact")

        return self.render_to_response(self.get_context_data(form=form))
