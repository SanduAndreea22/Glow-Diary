from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Collection, Comment, ContactMessage, Product
from .story_image import render_story_png

# Testele fac cereri HTTP simple (fără TLS) — fără asta, ele pică cu 301 când
# rulate în afara lui DEBUG=True (unde SECURE_SSL_REDIRECT devine implicit True),
# indiferent ce e setat în .env la momentul rulării.
_no_ssl_redirect = override_settings(SECURE_SSL_REDIRECT=False)


class ProductSlugTests(TestCase):
    def test_slug_generat_automat(self):
        p = Product.objects.create(
            nume="Soft Pinch Liquid Blush", brand="Rare Beauty",
            categorie="blush", nota_mea=5, parerea_mea="Test.",
        )
        self.assertEqual(p.slug, "rare-beauty-soft-pinch-liquid-blush")

    def test_slug_unic_la_duplicat(self):
        p1 = Product.objects.create(
            nume="Test", brand="Brand", categorie="altele",
            nota_mea=3, parerea_mea="a",
        )
        p2 = Product.objects.create(
            nume="Test", brand="Brand", categorie="altele",
            nota_mea=3, parerea_mea="b",
        )
        self.assertNotEqual(p1.slug, p2.slug)


@_no_ssl_redirect
class FeedViewTests(TestCase):
    def setUp(self):
        self.p1 = Product.objects.create(
            nume="Soft Pinch Liquid Blush", brand="Rare Beauty", categorie="blush",
            nota_mea=5, parerea_mea="Text.",
        )
        self.p2 = Product.objects.create(
            nume="Gloss Bomb", brand="Fenty Beauty", categorie="gloss",
            nota_mea=4, parerea_mea="Text.",
        )

    def test_feed_incarca(self):
        r = self.client.get(reverse("reviews:feed"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Rare Beauty")
        self.assertContains(r, "Fenty Beauty")

    def test_feed_cautare(self):
        r = self.client.get(reverse("reviews:feed"), {"q": "fenty"})
        self.assertContains(r, "Fenty Beauty")
        self.assertNotContains(r, "Rare Beauty")

    def test_feed_filtru_categorie(self):
        r = self.client.get(reverse("reviews:feed"), {"categorie": "blush"})
        self.assertContains(r, "Rare Beauty")
        self.assertNotContains(r, "Fenty Beauty")

    def test_feed_filtru_nota_minima(self):
        r = self.client.get(reverse("reviews:feed"), {"nota_min": "5"})
        self.assertContains(r, "Rare Beauty")
        self.assertNotContains(r, "Fenty Beauty")


@_no_ssl_redirect
class ProductDetailAndCommentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.produs = Product.objects.create(
            nume="Soft Pinch Liquid Blush", brand="Rare Beauty", categorie="blush",
            nota_mea=5, parerea_mea="Text.",
        )

    def test_detail_incarca(self):
        r = self.client.get(self.produs.get_absolute_url())
        self.assertEqual(r.status_code, 200)

    def test_produs_inexistent_da_404(self):
        r = self.client.get("/produs/nu-exista/")
        self.assertEqual(r.status_code, 404)

    def test_comentariu_valid_se_salveaza(self):
        r = self.client.post(self.produs.get_absolute_url(), {
            "nume": "Miruna", "nota": "5", "comentariu": "Super produs!", "website": "",
        })
        self.assertRedirects(r, self.produs.get_absolute_url())
        self.assertEqual(Comment.objects.filter(product=self.produs).count(), 1)

    def test_honeypot_respinge_comentariul(self):
        r = self.client.post(self.produs.get_absolute_url(), {
            "nume": "Bot", "nota": "1", "comentariu": "spam", "website": "http://spam.com",
        })
        self.assertEqual(Comment.objects.filter(product=self.produs).count(), 0)

    def test_comentariu_gol_respins(self):
        r = self.client.post(self.produs.get_absolute_url(), {
            "nume": "Cineva", "nota": "5", "comentariu": "", "website": "",
        })
        self.assertEqual(Comment.objects.filter(product=self.produs).count(), 0)

    def test_rate_limit_per_produs(self):
        data = {"nume": "Ana", "nota": "5", "comentariu": "Bun!", "website": ""}
        self.client.post(self.produs.get_absolute_url(), data)
        self.client.post(self.produs.get_absolute_url(), {
            "nume": "Alta", "nota": "4", "comentariu": "Si mie mi-a placut", "website": "",
        })
        self.assertEqual(Comment.objects.filter(product=self.produs).count(), 1)


@_no_ssl_redirect
class CollectionTests(TestCase):
    def test_colectie_fara_produse_nu_apare_in_lista(self):
        Collection.objects.create(nume="Goală")
        r = self.client.get(reverse("reviews:collections"))
        self.assertNotContains(r, "Goală")

    def test_colectie_cu_produse_apare_si_afiseaza_produsul(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie="altele",
            nota_mea=3, parerea_mea="a",
        )
        colectie = Collection.objects.create(nume="Vara")
        colectie.produse.add(produs)

        r = self.client.get(reverse("reviews:collections"))
        self.assertContains(r, "Vara")

        r = self.client.get(colectie.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Test")


@_no_ssl_redirect
class FavoritesApiTests(TestCase):
    def test_slug_necunoscut_da_lista_goala(self):
        r = self.client.get(reverse("reviews:favorites_data"), {"slugs": "nu-exista"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"produse": []})

    def test_slug_valid_intoarce_produsul(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie="altele",
            nota_mea=3, parerea_mea="a",
        )
        r = self.client.get(reverse("reviews:favorites_data"), {"slugs": produs.slug})
        self.assertEqual(r.json()["produse"][0]["slug"], produs.slug)


@_no_ssl_redirect
class SearchDataApiTests(TestCase):
    def setUp(self):
        self.p1 = Product.objects.create(
            nume="Soft Pinch Liquid Blush", brand="Rare Beauty", categorie="blush",
            nota_mea=5, parerea_mea="Text.",
        )
        self.p2 = Product.objects.create(
            nume="Gloss Bomb", brand="Fenty Beauty", categorie="gloss",
            nota_mea=4, parerea_mea="Text.",
        )

    def test_cautare_dupa_brand(self):
        r = self.client.get(reverse("reviews:search_data"), {"q": "fenty"})
        self.assertEqual(r.status_code, 200)
        slugs = [p["slug"] for p in r.json()["produse"]]
        self.assertEqual(slugs, [self.p2.slug])

    def test_fara_query_intoarce_toate_produsele(self):
        r = self.client.get(reverse("reviews:search_data"))
        self.assertEqual(len(r.json()["produse"]), 2)

    def test_filtru_categorie(self):
        r = self.client.get(reverse("reviews:search_data"), {"categorie": "gloss"})
        slugs = [p["slug"] for p in r.json()["produse"]]
        self.assertEqual(slugs, [self.p2.slug])

    def test_filtru_nota_min_invalida_e_ignorata(self):
        r = self.client.get(reverse("reviews:search_data"), {"nota_min": "abc"})
        self.assertEqual(len(r.json()["produse"]), 2)


@_no_ssl_redirect
class StoryImageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.produs = Product.objects.create(
            nume="Soft Pinch Liquid Blush", brand="Rare Beauty", categorie="blush",
            nota_mea=5, parerea_mea="Text.",
        )

    def test_genereaza_png_descarcabil(self):
        r = self.client.get(
            reverse("reviews:product_story_image", args=[self.produs.slug])
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertTrue(b"".join(r.streaming_content).startswith(b"\x89PNG"))

    def test_produs_inexistent_da_404(self):
        r = self.client.get(
            reverse("reviews:product_story_image", args=["nu-exista"])
        )
        self.assertEqual(r.status_code, 404)

    def test_a_doua_cerere_foloseste_cache(self):
        url = reverse("reviews:product_story_image", args=[self.produs.slug])
        with mock.patch(
            "reviews.views.render_story_png", wraps=render_story_png
        ) as spy:
            r1 = self.client.get(url)
            r2 = self.client.get(url)
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(
            b"".join(r1.streaming_content), b"".join(r2.streaming_content)
        )

    def test_editarea_produsului_invalideaza_cache_ul(self):
        url = reverse("reviews:product_story_image", args=[self.produs.slug])
        r1 = self.client.get(url)
        continut_initial = b"".join(r1.streaming_content)

        self.produs.nume = "Nume complet diferit"
        self.produs.save()

        r2 = self.client.get(url)
        continut_dupa_editare = b"".join(r2.streaming_content)
        self.assertNotEqual(continut_initial, continut_dupa_editare)


@_no_ssl_redirect
class StaticPagesTests(TestCase):
    def test_despre_si_contact_incarca(self):
        self.assertEqual(self.client.get(reverse("reviews:about")).status_code, 200)
        self.assertEqual(self.client.get(reverse("reviews:contact")).status_code, 200)

    def test_contact_form_valid(self):
        cache.clear()
        r = self.client.post(reverse("reviews:contact"), {
            "nume": "Test", "email": "test@test.com", "mesaj": "Salut!", "website": "",
        })
        self.assertRedirects(r, reverse("reviews:contact"))
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_contact_honeypot_respinge_mesajul(self):
        cache.clear()
        r = self.client.post(reverse("reviews:contact"), {
            "nume": "Bot", "email": "bot@spam.com", "mesaj": "spam",
            "website": "http://spam.com",
        })
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_contact_rate_limit_per_ip(self):
        cache.clear()
        data = {"nume": "Ana", "email": "ana@test.com", "mesaj": "Salut!", "website": ""}
        self.client.post(reverse("reviews:contact"), data)
        self.client.post(reverse("reviews:contact"), {
            "nume": "Alta", "email": "alta@test.com", "mesaj": "Salut din nou!", "website": "",
        })
        self.assertEqual(ContactMessage.objects.count(), 1)
