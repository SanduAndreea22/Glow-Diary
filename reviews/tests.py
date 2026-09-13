import io
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

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


def _poza_falsa(width, height, nume="test.jpg", format="JPEG"):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(255, 0, 0)).save(buf, format=format)
    buf.seek(0)
    return SimpleUploadedFile(nume, buf.read(), content_type=f"image/{format.lower()}")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImageOptimizationTests(TestCase):
    def test_poza_mare_e_redimensionata(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie="altele", nota_mea=3, parerea_mea="a",
            poza=_poza_falsa(3000, 2000),
        )
        with Image.open(produs.poza.path) as img:
            self.assertLessEqual(max(img.size), 1600)

    def test_poza_mica_ramane_neatinsa(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie="altele", nota_mea=3, parerea_mea="a",
            poza=_poza_falsa(400, 300),
        )
        with Image.open(produs.poza.path) as img:
            self.assertEqual(img.size, (400, 300))


@_no_ssl_redirect
class ProductAdminSlugExhaustionTests(TestCase):
    """La epuizarea încercărilor de slug unic, admin-ul trebuie să arate o
    eroare de formular clară, nu un 500 brut (IntegrityError necaptat)."""

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="deea2", password="parola-puternica-123", is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.staff)
        for i in range(1, 21):
            slug = "brand-produs" if i == 1 else f"brand-produs-{i}"
            Product.objects.create(
                nume="Produs", brand="Brand", categorie="altele",
                nota_mea=3, parerea_mea="x", slug=slug,
            )

    def test_formularul_respinge_cu_mesaj_clar(self):
        r = self.client.post(reverse("admin:reviews_product_add"), {
            "nume": "Produs", "brand": "Brand", "categorie": "altele",
            "nota_mea": "3", "parerea_mea": "y", "slug": "",
            "imagini-TOTAL_FORMS": "0", "imagini-INITIAL_FORMS": "0",
            "imagini-MIN_NUM_FORMS": "0", "imagini-MAX_NUM_FORMS": "1000",
            "comentarii-TOTAL_FORMS": "0", "comentarii-INITIAL_FORMS": "0",
            "comentarii-MIN_NUM_FORMS": "0", "comentarii-MAX_NUM_FORMS": "1000",
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "completează manual câmpul Slug")
        self.assertEqual(Product.objects.filter(nume="Produs").count(), 20)


@_no_ssl_redirect
class SoftDeleteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = get_user_model().objects.create_user(
            username="deea3", password="parola-puternica-123", is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.staff)
        self.produs = Product.objects.create(
            nume="Test", brand="Brand", categorie="altele", nota_mea=3, parerea_mea="a",
        )
        Comment.objects.create(product=self.produs, comentariu="Super!", aprobat=True)

    def test_delete_din_admin_ascunde_prima_data(self):
        url = reverse("admin:reviews_product_delete", args=[self.produs.pk])
        r = self.client.post(url, {"post": "yes"})
        self.assertRedirects(r, reverse("admin:reviews_product_changelist"))

        self.produs.refresh_from_db()
        self.assertFalse(self.produs.activ)
        self.assertTrue(Product.objects.filter(pk=self.produs.pk).exists())
        self.assertEqual(Comment.objects.filter(product=self.produs).count(), 1)

    def test_delete_a_doua_oara_sterge_definitiv(self):
        self.produs.activ = False
        self.produs.save(update_fields=["activ"])

        url = reverse("admin:reviews_product_delete", args=[self.produs.pk])
        self.client.post(url, {"post": "yes"})

        self.assertFalse(Product.objects.filter(pk=self.produs.pk).exists())
        self.assertEqual(Comment.objects.filter(product_id=self.produs.pk).count(), 0)

    def test_bulk_delete_selected_ascunde_nu_sterge(self):
        url = reverse("admin:reviews_product_changelist")
        r = self.client.post(url, {
            "action": "delete_selected",
            "_selected_action": [str(self.produs.pk)],
            "post": "yes",
        })
        self.assertEqual(r.status_code, 302)
        self.produs.refresh_from_db()
        self.assertFalse(self.produs.activ)
        self.assertTrue(Product.objects.filter(pk=self.produs.pk).exists())

    def test_actiunea_de_restaurare(self):
        self.produs.activ = False
        self.produs.save(update_fields=["activ"])

        url = reverse("admin:reviews_product_changelist")
        self.client.post(url, {
            "action": "restaureaza_produse",
            "_selected_action": [str(self.produs.pk)],
        })
        self.produs.refresh_from_db()
        self.assertTrue(self.produs.activ)

    def test_produs_ascuns_nu_apare_public(self):
        self.produs.activ = False
        self.produs.save(update_fields=["activ"])
        cache.clear()

        r = self.client.get(reverse("reviews:feed"))
        self.assertNotContains(r, self.produs.nume)

        r = self.client.get(self.produs.get_absolute_url())
        self.assertEqual(r.status_code, 404)

        r = self.client.get(reverse("reviews:search_data"))
        self.assertEqual(r.json()["produse"], [])

        r = self.client.get(reverse("reviews:favorites_data"), {"slugs": self.produs.slug})
        self.assertEqual(r.json()["produse"], [])


@_no_ssl_redirect
class FeedBadgeTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_sub_prag_arata_data_ultimei_postari_nu_contorul(self):
        Product.objects.create(
            nume="A", brand="B", categorie="altele", nota_mea=3, parerea_mea="x",
        )
        r = self.client.get(reverse("reviews:feed"))
        self.assertContains(r, "Actualizat")
        self.assertNotContains(r, "produs testat")
        self.assertNotContains(r, "produse testate")

    def test_peste_prag_arata_contorul(self):
        for i in range(10):
            Product.objects.create(
                nume=f"P{i}", brand="B", categorie="altele", nota_mea=3, parerea_mea="x",
            )
        r = self.client.get(reverse("reviews:feed"))
        self.assertContains(r, "10 produse testate")


@_no_ssl_redirect
class FiltreCategoriiTests(TestCase):
    def setUp(self):
        cache.clear()
        Product.objects.create(
            nume="A", brand="B", categorie="blush", nota_mea=3, parerea_mea="x",
        )

    def test_categoria_cu_produse_e_link_activ(self):
        r = self.client.get(reverse("reviews:feed"))
        self.assertContains(r, "categorie=blush")
        content = r.content.decode()
        self.assertIn('<a href="?categorie=blush', content)

    def test_categoria_fara_produse_e_span_needitabil(self):
        r = self.client.get(reverse("reviews:feed"))
        content = r.content.decode()
        self.assertNotIn("categorie=ruj", content)
        self.assertIn('<span class="chip chip-disabled"', content)


@_no_ssl_redirect
class SocialLinksTests(TestCase):
    @override_settings(INSTAGRAM_URL="", TIKTOK_URL="")
    def test_fara_linkuri_footerul_nu_arata_iconite(self):
        r = self.client.get(reverse("reviews:feed"))
        self.assertNotContains(r, "footer-social")

    @override_settings(INSTAGRAM_URL="https://www.instagram.com/exemplu", TIKTOK_URL="")
    def test_cu_instagram_apare_iconita(self):
        r = self.client.get(reverse("reviews:feed"))
        self.assertContains(r, "footer-social")
        self.assertContains(r, "https://www.instagram.com/exemplu")
        self.assertNotContains(r, "pe TikTok")


@_no_ssl_redirect
class FeedViewTests(TestCase):
    def setUp(self):
        self.p1 = Product.objects.create(
            nume="Soft Pinch Liquid Blush", brand="Rare Beauty", categorie="blush",
            nota_mea=5, parerea_mea="Text.", sursa="Sephora",
        )
        self.p2 = Product.objects.create(
            nume="Gloss Bomb", brand="Fenty Beauty", categorie="gloss",
            nota_mea=4, parerea_mea="Text.", sursa="Douglas",
        )

    def test_feed_incarca(self):
        r = self.client.get(reverse("reviews:feed"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Rare Beauty")
        self.assertContains(r, "Fenty Beauty")

    def test_feed_filtru_sursa(self):
        r = self.client.get(reverse("reviews:feed"), {"sursa": "Sephora"})
        self.assertContains(r, "Rare Beauty")
        self.assertNotContains(r, "Fenty Beauty")

    def test_feed_panoul_de_filtre_listeaza_sursele_existente(self):
        r = self.client.get(reverse("reviews:feed"))
        self.assertContains(r, "Sephora")
        self.assertContains(r, "Douglas")

    def test_feed_cautare(self):
        r = self.client.get(reverse("reviews:feed"), {"q": "fenty"})
        self.assertContains(r, "Fenty Beauty")
        self.assertNotContains(r, "Rare Beauty")

    def test_feed_filtru_categorie(self):
        r = self.client.get(reverse("reviews:feed"), {"categorie": "blush"})
        self.assertContains(r, "Rare Beauty")
        self.assertNotContains(r, "Fenty Beauty")

    def test_feed_filtru_nota_e_exact_nu_minim(self):
        r = self.client.get(reverse("reviews:feed"), {"nota_min": "4"})
        self.assertContains(r, "Fenty Beauty")
        self.assertNotContains(r, "Rare Beauty")


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
        self.client.post(self.produs.get_absolute_url(), {
            "nume": "Bot", "nota": "1", "comentariu": "spam", "website": "http://spam.com",
        })
        self.assertEqual(Comment.objects.filter(product=self.produs).count(), 0)

    def test_comentariu_gol_respins(self):
        self.client.post(self.produs.get_absolute_url(), {
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

    def test_comment_count_apare_in_json(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie="altele",
            nota_mea=3, parerea_mea="a",
        )
        Comment.objects.create(product=produs, comentariu="Super!", aprobat=True)
        r = self.client.get(reverse("reviews:favorites_data"), {"slugs": produs.slug})
        self.assertEqual(r.json()["produse"][0]["comment_count"], 1)


@_no_ssl_redirect
class SearchDataApiTests(TestCase):
    def setUp(self):
        self.p1 = Product.objects.create(
            nume="Soft Pinch Liquid Blush", brand="Rare Beauty", categorie="blush",
            nota_mea=5, parerea_mea="Text.", sursa="Sephora",
        )
        self.p2 = Product.objects.create(
            nume="Gloss Bomb", brand="Fenty Beauty", categorie="gloss",
            nota_mea=4, parerea_mea="Text.", sursa="Douglas",
        )

    def test_filtru_sursa(self):
        r = self.client.get(reverse("reviews:search_data"), {"sursa": "Sephora"})
        slugs = [p["slug"] for p in r.json()["produse"]]
        self.assertEqual(slugs, [self.p1.slug])

    def test_sortare_dupa_nota(self):
        r = self.client.get(reverse("reviews:search_data"), {"sort": "nota"})
        slugs = [p["slug"] for p in r.json()["produse"]]
        self.assertEqual(slugs, [self.p1.slug, self.p2.slug])

    def test_sortare_implicita_dupa_cele_mai_noi(self):
        r = self.client.get(reverse("reviews:search_data"))
        slugs = [p["slug"] for p in r.json()["produse"]]
        self.assertEqual(slugs, [self.p2.slug, self.p1.slug])

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

    def test_produsul_lunii_si_comment_count_apar_in_json(self):
        Comment.objects.create(product=self.p1, comentariu="Super!", aprobat=True)
        r = self.client.get(reverse("reviews:search_data"))
        by_slug = {p["slug"]: p for p in r.json()["produse"]}
        self.assertEqual(by_slug[self.p1.slug]["comment_count"], 1)
        self.assertTrue(by_slug[self.p1.slug]["produsul_lunii"])
        self.assertFalse(by_slug[self.p2.slug]["produsul_lunii"])


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
            "reviews.views.product.render_story_png", wraps=render_story_png
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
        self.client.post(reverse("reviews:contact"), {
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


@_no_ssl_redirect
class ProductBulkAddAdminTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="deea", password="parola-puternica-123", is_staff=True, is_superuser=True,
        )
        self.url = reverse("admin:reviews_product_bulk_add")

    def _management_form(self, total):
        return {
            "form-TOTAL_FORMS": str(total),
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
        }

    def test_neautentificat_e_redirectionat_la_login(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)

    def test_pagina_incarca_pentru_staff(self):
        self.client.force_login(self.staff)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_salveaza_doar_randurile_completate(self):
        self.client.force_login(self.staff)
        data = self._management_form(3)
        data.update({
            "form-0-brand": "Rare Beauty", "form-0-nume": "Soft Pinch",
            "form-0-categorie": "blush", "form-0-nuanta": "", "form-0-sursa": "Sephora",
            "form-0-nota_mea": "5", "form-0-parerea_mea": "Super produs.",
            # rândul 1 rămâne complet gol — trebuie ignorat, nu trebuie să dea eroare
            "form-1-brand": "", "form-1-nume": "", "form-1-categorie": "",
            "form-1-nuanta": "", "form-1-sursa": "", "form-1-nota_mea": "",
            "form-1-parerea_mea": "",
            "form-2-brand": "Fenty Beauty", "form-2-nume": "Gloss Bomb",
            "form-2-categorie": "gloss", "form-2-nuanta": "", "form-2-sursa": "Douglas",
            "form-2-nota_mea": "4", "form-2-parerea_mea": "Mi-a plăcut mult.",
        })
        r = self.client.post(self.url, data)
        self.assertRedirects(r, reverse("admin:reviews_product_changelist"))
        self.assertEqual(Product.objects.count(), 2)
        self.assertTrue(Product.objects.filter(brand="Rare Beauty").exists())
        self.assertTrue(Product.objects.filter(brand="Fenty Beauty").exists())
