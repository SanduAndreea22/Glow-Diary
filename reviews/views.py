from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView, TemplateView

from .forms import CommentForm, ContactForm
from .models import CATEGORIE_CHOICES, Product

RATE_LIMIT_SECONDS = 60


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


class FeedView(ListView):
    model = Product
    template_name = "reviews/feed.html"
    context_object_name = "produse"
    paginate_by = 12

    def get_queryset(self):
        qs = Product.objects.all()
        q = self.request.GET.get("q", "").strip()
        categorie = self.request.GET.get("categorie", "").strip()
        nota_min = self.request.GET.get("nota_min", "").strip()

        if q:
            from django.db.models import Q

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
