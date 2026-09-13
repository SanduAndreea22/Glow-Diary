import hashlib
import io
import json
import time

from django.contrib import messages
from django.core.cache import cache
from django.db.models import Count, Sum
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.templatetags.static import static
from django.views import View
from django.views.generic import DetailView

from ..forms import CommentForm
from ..models import Product
from ..queries import cu_numar_pareri
from ..story_image import render_story_png
from ..throttling import RATE_LIMIT_SECONDS, client_ip, global_rate_limited

STORY_IMAGE_CACHE_TTL = 60 * 60 * 24  # 24h — randarea cu Pillow e costisitoare


class ProductDetailView(DetailView):
    model = Product
    template_name = "reviews/product_detail.html"
    context_object_name = "produs"

    def get_queryset(self):
        # activ=True — un produs ascuns (soft-delete) trebuie să 404
        # pentru vizitatoare, la fel ca unul șters cu adevărat.
        return Product.objects.filter(activ=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        comentarii_aprobate = self.object.comentarii.filter(aprobat=True)
        ctx["comentarii"] = comentarii_aprobate
        ctx["form"] = kwargs.get("form", CommentForm())

        # Media notelor lăsate de cititoare (doar cele cu notă, nu toate
        # comentariile au una) — separată vizual de nota Deei, ca cititoarea
        # să vadă dintr-o privire dacă părerile converg sau diverg.
        rating_stats = comentarii_aprobate.filter(nota__isnull=False).aggregate(
            suma=Sum("nota"), total=Count("nota")
        )
        vizitatoare_total = rating_stats["total"] or 0
        if vizitatoare_total:
            ctx["nota_cititoarelor"] = round(rating_stats["suma"] / vizitatoare_total, 1)
            ctx["nota_cititoarelor_total"] = vizitatoare_total

        ctx["product_schema_json"] = self._product_schema(
            self.object, rating_stats["suma"] or 0, vizitatoare_total
        )
        galerie = list(self.object.imagini.all())
        pozele = ([self.object.poza] if self.object.poza else []) + [
            img.imagine for img in galerie if img.imagine
        ]
        ctx["galerie"] = pozele
        ctx["similare"] = cu_numar_pareri(
            Product.objects.filter(activ=True, categorie=self.object.categorie)
            .exclude(pk=self.object.pk)
        )[:3]
        return ctx

    def _product_schema(self, produs, suma_note_vizitatoare, total_vizitatoare):
        """JSON-LD Product+Review — permite Google să arate stelele direct
        în rezultatele de căutare, nu doar un link anonim. Combinăm nota
        Deei cu cele ale vizitatoarelor într-un singur agregat, cerut de
        Google pentru orice rating afișat public pe pagină."""
        request = self.request
        base_url = f"{request.scheme}://{request.get_host()}"
        image_url = (
            f"{base_url}{produs.poza.url}" if produs.poza
            else f"{base_url}{static('img/og-image.png')}"
        )
        suma_totala = suma_note_vizitatoare + produs.nota_mea
        numar_total = total_vizitatoare + 1

        data = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": produs.nume,
            "brand": {"@type": "Brand", "name": produs.brand},
            "image": image_url,
            "url": f"{base_url}{produs.get_absolute_url()}",
            "description": produs.parerea_mea,
            "review": {
                "@type": "Review",
                "author": {"@type": "Person", "name": "Deea"},
                "reviewBody": produs.parerea_mea,
                "reviewRating": {
                    "@type": "Rating",
                    "ratingValue": produs.nota_mea,
                    "bestRating": 5,
                    "worstRating": 1,
                },
            },
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": round(suma_totala / numar_total, 1),
                "reviewCount": numar_total,
                "bestRating": 5,
                "worstRating": 1,
            },
        }
        # "</script>" în descriere ar închide prematur tag-ul — improbabil cu
        # text scris de Deea, dar mai sigur decât să presupunem că nu apare.
        return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = CommentForm(request.POST)
        ip = client_ip(request)

        # cache.add e atomic: „ocupă" lacătul doar dacă nu exista deja — spre
        # deosebire de get+set, două cereri simultane nu pot trece amândouă.
        cache_key = f"comment-rl:{ip}:{self.object.pk}"
        if not cache.add(cache_key, True, RATE_LIMIT_SECONDS):
            messages.error(
                request, "Ai comentat recent la acest produs — mai încearcă peste un minut."
            )
            return redirect(self.object.get_absolute_url())

        if global_rate_limited(ip, "comment"):
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
        # www vs. non-www ar fi altfel două chei de cache diferite pentru
        # exact aceeași imagine — normalizăm la o singură formă canonică,
        # folosită atât în cheie cât și ca text afișat pe imagine (brand-ul
        # arată mereu consistent, indiferent pe ce variantă de domeniu a
        # ajuns vizitatoarea).
        host = request.get_host().lower().removeprefix("www.")
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
            if global_rate_limited(client_ip(request), "story-render"):
                return HttpResponse(
                    "Prea multe imagini generate deodată — mai încearcă peste câteva minute.",
                    status=429,
                )
            png_bytes = self._render_with_lock(cache_key, produs, host)
        response = FileResponse(io.BytesIO(png_bytes), content_type="image/png")
        response["Content-Disposition"] = f'attachment; filename="{produs.slug}-story.png"'
        return response

    def _render_with_lock(self, cache_key, produs, host):
        """Evită randări Pillow duplicate când două cereri lovesc simultan
        același cache-miss (ex. un link de Story distribuit și deschis de
        mai multe persoane deodată) — doar prima ține efectiv lacătul și
        randează; restul așteaptă scurt rezultatul ei din cache, în loc să
        randeze fiecare separat aceeași imagine."""
        lock_key = f"story-render-lock:{cache_key}"
        if cache.add(lock_key, True, 30):
            try:
                png_bytes = render_story_png(produs, host).getvalue()
                cache.set(cache_key, png_bytes, STORY_IMAGE_CACHE_TTL)
                return png_bytes
            finally:
                cache.delete(lock_key)

        for _ in range(6):
            time.sleep(0.3)
            png_bytes = cache.get(cache_key)
            if png_bytes is not None:
                return png_bytes
        # Lacătul a expirat/blocat mai mult decât am așteptat — randăm noi
        # înșine, mai bine cu o randare în plus decât cu un request picat.
        png_bytes = render_story_png(produs, host).getvalue()
        cache.set(cache_key, png_bytes, STORY_IMAGE_CACHE_TTL)
        return png_bytes
