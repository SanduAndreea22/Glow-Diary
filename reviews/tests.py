from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import Collection, Comment, Product


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
