from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from ..forms import ContactForm
from ..queries import recomandari_favorite_goale
from ..throttling import RATE_LIMIT_SECONDS, client_ip, global_rate_limited


class FavoritesView(TemplateView):
    template_name = "reviews/favorites.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Randate mereu server-side (nu doar dacă JS-ul detectează lista
        # goală din localStorage) — vizibile imediat, fără flash de conținut.
        ctx["recomandari_favorite_goale"] = recomandari_favorite_goale()
        return ctx


class AboutView(TemplateView):
    template_name = "reviews/about.html"


class ContactView(TemplateView):
    template_name = "reviews/contact.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = kwargs.get("form", ContactForm())
        return ctx

    def post(self, request, *args, **kwargs):
        ip = client_ip(request)
        cache_key = f"contact-rl:{ip}"
        if not cache.add(cache_key, True, RATE_LIMIT_SECONDS):
            messages.error(request, "Ai trimis deja un mesaj recent — revin eu cât pot.")
            return redirect("reviews:contact")

        if global_rate_limited(ip, "contact"):
            cache.delete(cache_key)
            messages.error(request, "Ai trimis prea multe mesaje într-un timp scurt. Încearcă din nou peste câteva minute.")
            return redirect("reviews:contact")

        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Mesajul tău a ajuns la mine, mulțumesc! 💌")
            return redirect("reviews:contact")

        cache.delete(cache_key)

        if form.errors.get("website"):
            # honeypot completat — verificat explicit (nu prin excludere pe
            # celelalte câmpuri), vezi motivul detaliat în ProductDetailView.post.
            messages.error(request, "Nu am putut trimite mesajul — mai încearcă o dată.")
            return redirect("reviews:contact")

        return self.render_to_response(self.get_context_data(form=form))


def csrf_failure(request, reason=""):
    """CSRF_FAILURE_VIEW — pagină în stilul site-ului, nu default-ul Django,
    pentru cazul (sesiune expirată / cookies blocate) în care un formular
    public eșuează la verificarea CSRF."""
    return render(request, "403_csrf.html", status=403)
