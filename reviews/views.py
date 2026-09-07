from datetime import timedelta

from django.contrib import messages
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from .forms import CommentForm, ContactForm
from .models import CATEGORIE_CHOICES, Collection, Product

RATE_LIMIT_SECONDS = 60


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


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
        ctx["produsul_lunii_id"] = _produsul_lunii()
        ctx["total_produse"] = Product.objects.count()
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
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = CommentForm(request.POST)

        cache_key = f"comment-rl:{_client_ip(request)}:{self.object.pk}"
        if cache.get(cache_key):
            messages.error(
                request, "Ai comentat recent la acest produs — mai încearcă puțin."
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

        return self.render_to_response(self.get_context_data(form=form))


class CollectionListView(ListView):
    model = Collection
    template_name = "reviews/collections.html"
    context_object_name = "colectii"

    def get_queryset(self):
        return Collection.objects.filter(produse__isnull=False).distinct()


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


def favorites_data(request):
    slugs = [s for s in request.GET.get("slugs", "").split(",") if s]
    produse = Product.objects.filter(slug__in=slugs)
    data = [
        {
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
        }
        for p in produse
    ]
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
        cache_key = f"contact-rl:{_client_ip(request)}"
        if cache.get(cache_key):
            messages.error(request, "Ai trimis deja un mesaj recent — revin eu cât pot.")
            return redirect("reviews:contact")

        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            cache.set(cache_key, True, RATE_LIMIT_SECONDS)
            messages.success(request, "Mesajul tău a ajuns la mine, mulțumesc! 💌")
            return redirect("reviews:contact")

        return self.render_to_response(self.get_context_data(form=form))
