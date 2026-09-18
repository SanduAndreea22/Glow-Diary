import io
import os
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .checks import verifica_redis_in_productie
from .forms import MAX_UPLOAD_IMAGINE_BYTES, CommentForm
from .image_utils import MAX_PIXELI_ACCEPTATI, PozaPreaMareError
from .models import Categorie, Collection, Comment, ContactMessage, Product, Tag
from .queries import colectia_saptamanii, colectii_de_sezon, produs_hero_fallback
from .story_image import _safe_text, build_story_image, render_story_png
from .templatetags.glow_extras import stars_svg

# Testele fac cereri HTTP simple (fără TLS) — fără asta, ele pică cu 301 când
# rulate în afara lui DEBUG=True (unde SECURE_SSL_REDIRECT devine implicit True),
# indiferent ce e setat în .env la momentul rulării.
_no_ssl_redirect = override_settings(SECURE_SSL_REDIRECT=False)


class ProductSlugTests(TestCase):
    def test_slug_generat_automat(self):
        p = Product.objects.create(
            nume="Soft Pinch Liquid Blush", brand="Rare Beauty",
            categorie=_cat("ten"), nota_mea=5, parerea_mea="Test.",
        )
        self.assertEqual(p.slug, "rare-beauty-soft-pinch-liquid-blush")

    def test_slug_unic_la_duplicat(self):
        p1 = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"),
            nota_mea=3, parerea_mea="a",
        )
        p2 = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"),
            nota_mea=3, parerea_mea="b",
        )
        self.assertNotEqual(p1.slug, p2.slug)


def _cat(slug):
    """Categoria-frunză cu acest slug, din taxonomia semănată prin migrare
    (reviews/migrations/0015_migreaza_categorii.py) — nu se creează una nouă,
    ca testele să exerseze aceleași date ca producția."""
    return Categorie.objects.get(slug=slug)


def _poza_falsa(width, height, nume="test.jpg", format="JPEG"):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(255, 0, 0)).save(buf, format=format)
    buf.seek(0)
    return SimpleUploadedFile(nume, buf.read(), content_type=f"image/{format.lower()}")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImageOptimizationTests(TestCase):
    def test_poza_mare_e_redimensionata(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=3, parerea_mea="a",
            poza=_poza_falsa(3000, 2000),
        )
        with Image.open(produs.poza.path) as img:
            self.assertLessEqual(max(img.size), 1600)

    def test_poza_mica_ramane_neatinsa(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=3, parerea_mea="a",
            poza=_poza_falsa(400, 300),
        )
        with Image.open(produs.poza.path) as img:
            self.assertEqual(img.size, (400, 300))

    def test_poza_mica_pierde_exif_ul(self):
        # O poză sub pragul de redimensionare trecea neatinsă (deci și cu
        # EXIF-ul original, posibil GPS) — acum orice poză e reîncodată,
        # indiferent de dimensiune.
        buf = io.BytesIO()
        img = Image.new("RGB", (400, 300), color=(0, 255, 0))
        exif = img.getexif()
        exif[271] = "TestCamera"
        img.save(buf, format="JPEG", exif=exif)
        buf.seek(0)
        fisier = SimpleUploadedFile("mic.jpg", buf.read(), content_type="image/jpeg")

        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=3, parerea_mea="a",
            poza=fisier,
        )
        with Image.open(produs.poza.path) as salvata:
            self.assertNotIn(271, salvata.getexif())

    def test_poza_peste_pragul_de_pixeli_e_respinsa(self):
        # Latură ~= sqrt(prag) * 1.2, ca să depășească clar MAX_PIXELI_ACCEPTATI
        # fără să depindă de o valoare hardcodată a constantei.
        latura = int((MAX_PIXELI_ACCEPTATI ** 0.5) * 1.2)
        with self.assertRaises(PozaPreaMareError):
            Product.objects.create(
                nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=3, parerea_mea="a",
                poza=_poza_falsa(latura, latura),
            )


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OrphanFileCleanupTests(TestCase):
    """django-cleanup — fără el, fișierele fizice rămâneau orfane pe disc
    la ștergere/înlocuire (Django nu face asta implicit pentru FileField)."""

    def test_fisierul_e_sters_la_stergerea_definitiva(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=3, parerea_mea="a",
            poza=_poza_falsa(400, 300), activ=False,  # deja ascuns => delete() șterge cu adevărat
        )
        cale = produs.poza.path
        self.assertTrue(os.path.isfile(cale))
        # django-cleanup rulează ștergerea fișierului în transaction.on_commit
        # — fără captureOnCommitCallbacks, hook-ul nu se declanșează deloc
        # în interiorul tranzacției (derulate înapoi, nu comise) a unui TestCase.
        with self.captureOnCommitCallbacks(execute=True):
            produs.delete()
        self.assertFalse(os.path.isfile(cale))

    def test_fisierul_vechi_e_sters_la_inlocuirea_pozei(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=3, parerea_mea="a",
            poza=_poza_falsa(400, 300),
        )
        cale_veche = produs.poza.path
        produs.poza = _poza_falsa(200, 200, nume="noua.jpg")
        with self.captureOnCommitCallbacks(execute=True):
            produs.save()
        self.assertFalse(os.path.isfile(cale_veche))


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
                nume="Produs", brand="Brand", categorie=_cat("altele"),
                nota_mea=3, parerea_mea="x", slug=slug,
            )

    def test_formularul_respinge_cu_mesaj_clar(self):
        r = self.client.post(reverse("admin:reviews_product_add"), {
            "nume": "Produs", "brand": "Brand", "categorie": str(_cat("altele").pk),
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
            nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=3, parerea_mea="a",
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
            nume="A", brand="B", categorie=_cat("altele"), nota_mea=3, parerea_mea="x",
        )
        r = self.client.get(reverse("reviews:feed"))
        self.assertContains(r, "Actualizat")
        self.assertNotContains(r, "produs testat")
        self.assertNotContains(r, "produse testate")

    def test_peste_prag_arata_contorul(self):
        for i in range(10):
            Product.objects.create(
                nume=f"P{i}", brand="B", categorie=_cat("altele"), nota_mea=3, parerea_mea="x",
            )
        r = self.client.get(reverse("reviews:feed"))
        self.assertContains(r, "10 produse testate")


@_no_ssl_redirect
class FiltreCategoriiTests(TestCase):
    def setUp(self):
        cache.clear()
        Product.objects.create(
            nume="A", brand="B", categorie=_cat("ten"), nota_mea=3, parerea_mea="x",
        )
        # Peste MIN_PRODUSE_PENTRU_CONTOR — sub prag, rândul de categorii e
        # ascuns complet (simplificare UI cât conținutul e redus, vezi
        # feed.html), deci testele de mai jos n-ar mai avea ce verifica.
        for i in range(9):
            Product.objects.create(
                nume=f"P{i}", brand="B", categorie=_cat("altele"), nota_mea=3, parerea_mea="x",
            )

    def test_categoria_cu_produse_e_link_activ(self):
        r = self.client.get(reverse("reviews:feed"))
        self.assertContains(r, "categorie=ten")
        content = r.content.decode()
        self.assertIn('<a href="?categorie=ten', content)

    def test_categoria_fara_produse_nu_apare_deloc(self):
        # Fără produse în "Buze", categoria nici măcar nu apare în filtru
        # (nu doar estompată) — vezi _categorii_navigare în queries.py.
        r = self.client.get(reverse("reviews:feed"))
        content = r.content.decode()
        self.assertNotIn("categorie=buze", content)
        self.assertNotIn("chip-disabled", content)


class CategorieIerarhieTests(TestCase):
    """Categorie e pe maximum 2 niveluri (grup -> subcategorie) — vezi
    Categorie.clean() și _categorii_frunza() din forms.py."""

    def test_un_grup_de_nivel_1_e_valid(self):
        grup = Categorie.objects.create(nume="Grup Test")
        grup.full_clean()  # nu ridică ValidationError

    def test_o_subcategorie_sub_un_grup_e_valida(self):
        grup = Categorie.objects.create(nume="Grup Test 2")
        sub = Categorie(nume="Sub Test", grup=grup)
        sub.full_clean()  # nu ridică ValidationError

    def test_al_treilea_nivel_e_respins(self):
        grup = Categorie.objects.create(nume="Grup Test 3")
        sub = Categorie.objects.create(nume="Sub Test 3", grup=grup)
        nepot = Categorie(nume="Nepot", grup=sub)
        with self.assertRaises(ValidationError):
            nepot.full_clean()

    def test_slug_generat_automat_din_nume(self):
        c = Categorie.objects.create(nume="Categorie Nouă Testată")
        self.assertEqual(c.slug, "categorie-noua-testata")

    def test_str_arata_grup_sageata_nume_pentru_subcategorie(self):
        grup = Categorie.objects.create(nume="Grup Test 4")
        sub = Categorie.objects.create(nume="Sub Test 4", grup=grup)
        self.assertEqual(str(sub), "Grup Test 4 → Sub Test 4")

    def test_str_arata_doar_numele_pentru_un_grup(self):
        grup = Categorie.objects.create(nume="Grup Test 5")
        self.assertEqual(str(grup), "Grup Test 5")


@_no_ssl_redirect
class CategorieAdminFormTests(TestCase):
    """Un produs se leagă mereu de o categorie-frunză — niciodată de un grup
    care are subcategorii (ex. „Machiaj” direct, fără Ten/Ochi/...)."""

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="deea-cat", password="parola-puternica-123", is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.staff)

    def test_grup_cu_subcategorii_nu_e_optiune_valida(self):
        machiaj = Categorie.objects.get(slug="machiaj")
        r = self.client.post(reverse("admin:reviews_product_add"), {
            "nume": "Produs", "brand": "Brand", "categorie": str(machiaj.pk),
            "nota_mea": "3", "parerea_mea": "y", "slug": "",
            "imagini-TOTAL_FORMS": "0", "imagini-INITIAL_FORMS": "0",
            "imagini-MIN_NUM_FORMS": "0", "imagini-MAX_NUM_FORMS": "1000",
            "comentarii-TOTAL_FORMS": "0", "comentarii-INITIAL_FORMS": "0",
            "comentarii-MIN_NUM_FORMS": "0", "comentarii-MAX_NUM_FORMS": "1000",
        })
        self.assertEqual(r.status_code, 200)  # re-randează formularul, nu redirect
        self.assertFalse(Product.objects.filter(nume="Produs").exists())

    def test_o_subcategorie_e_optiune_valida(self):
        r = self.client.post(reverse("admin:reviews_product_add"), {
            "nume": "Produs", "brand": "Brand", "categorie": str(_cat("buze").pk),
            "nota_mea": "3", "parerea_mea": "y", "slug": "",
            "imagini-TOTAL_FORMS": "0", "imagini-INITIAL_FORMS": "0",
            "imagini-MIN_NUM_FORMS": "0", "imagini-MAX_NUM_FORMS": "1000",
            "comentarii-TOTAL_FORMS": "0", "comentarii-INITIAL_FORMS": "0",
            "comentarii-MIN_NUM_FORMS": "0", "comentarii-MAX_NUM_FORMS": "1000",
        })
        self.assertRedirects(r, reverse("admin:reviews_product_changelist"))
        self.assertTrue(Product.objects.filter(nume="Produs").exists())


@_no_ssl_redirect
class SimplificareUISubPragTests(TestCase):
    """Sub MIN_PRODUSE_PENTRU_CONTOR, bara de căutare+filtre și rândul de
    categorii sunt "mobilier" fără rost — ascunse temporar, nu șterse."""

    def setUp(self):
        cache.clear()
        Product.objects.create(
            nume="A", brand="B", categorie=_cat("ten"), nota_mea=3, parerea_mea="x",
        )

    def test_sub_prag_fara_filtru_activ_ascunde_ui_ul(self):
        r = self.client.get(reverse("reviews:feed"))
        content = r.content.decode()
        self.assertNotIn('id="search-bar"', content)
        self.assertNotIn('id="filter-panel"', content)
        self.assertNotIn("categorie=ten", content)

    def test_sub_prag_cu_cautare_activa_arata_ui_ul(self):
        # Vizitatoare ajunsă cu un link deja filtrat/cu căutare — nu rămâne
        # blocată fără context, chiar dacă suntem sub pragul de produse.
        r = self.client.get(reverse("reviews:feed"), {"q": "a"})
        content = r.content.decode()
        self.assertIn('id="search-bar"', content)

    def test_sub_prag_cu_categorie_activa_arata_ui_ul(self):
        r = self.client.get(reverse("reviews:feed"), {"categorie": "ten"})
        content = r.content.decode()
        self.assertIn('id="search-bar"', content)


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
            nume="Soft Pinch Liquid Blush", brand="Rare Beauty", categorie=_cat("ten"),
            nota_mea=5, parerea_mea="Text.", sursa="Sephora",
        )
        self.p2 = Product.objects.create(
            nume="Gloss Bomb", brand="Fenty Beauty", categorie=_cat("buze"),
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
        r = self.client.get(reverse("reviews:feed"), {"categorie": "ten"})
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
            nume="Soft Pinch Liquid Blush", brand="Rare Beauty", categorie=_cat("ten"),
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
        # ?prima-parere=1 — primul comentariu de pe acest produs declanșează
        # confetti pe client (vezi ProductDetailView.post).
        self.assertRedirects(r, self.produs.get_absolute_url() + "?prima-parere=1")
        self.assertEqual(Comment.objects.filter(product=self.produs).count(), 1)

    def test_comentariu_fara_nota_se_salveaza(self):
        # Nota e explicit opțională ("Notă (opțional)") — lăsată nealeasă,
        # formularul trimitea '' (nu None) pe câmpul nullable Comment.nota,
        # ceea ce făcea save()-ul să pice cu ValueError la INSERT. Bug real,
        # reproductibil pe orice comentariu fără stea, indiferent de audit.
        r = self.client.post(self.produs.get_absolute_url(), {
            "nume": "Ana", "nota": "", "comentariu": "Fără notă, doar părere.", "website": "",
        })
        self.assertRedirects(r, self.produs.get_absolute_url() + "?prima-parere=1")
        comentariu = Comment.objects.get(product=self.produs)
        self.assertIsNone(comentariu.nota)

    def test_al_doilea_comentariu_nu_are_parametrul_de_confetti(self):
        # ?prima-parere=1 declanșează confetti pe client — doar chiar primul
        # comentariu al unui produs merită asta, nu fiecare comentariu.
        Comment.objects.create(product=self.produs, nume="Prima", comentariu="Primul comentariu.")
        r = self.client.post(self.produs.get_absolute_url(), {
            "nume": "A doua", "nota": "4", "comentariu": "Al doilea comentariu.", "website": "",
        })
        self.assertRedirects(r, self.produs.get_absolute_url())
        self.assertEqual(Comment.objects.filter(product=self.produs).count(), 2)

    def test_honeypot_respinge_comentariul(self):
        self.client.post(self.produs.get_absolute_url(), {
            "nume": "Bot", "nota": "1", "comentariu": "spam", "website": "http://spam.com",
        })
        self.assertEqual(Comment.objects.filter(product=self.produs).count(), 0)

    def test_honeypot_cu_comentariu_gol_ramane_mesaj_generic(self):
        # Bot care completează honeypot-ul ȘI lasă comentariul gol — verifică
        # explicit că ramura "silențioasă" (mesaj generic) ia prioritate,
        # nu ramura normală de eroare de validare (care ar dezvălui indirect
        # structura de validare unui bot).
        r = self.client.post(self.produs.get_absolute_url(), {
            "nume": "Bot", "nota": "1", "comentariu": "", "website": "http://spam.com",
        }, follow=True)
        self.assertEqual(Comment.objects.filter(product=self.produs).count(), 0)
        text_mesaje = [str(m) for m in r.context["messages"]]
        self.assertTrue(any("Nu am putut trimite comentariul" in m for m in text_mesaje))

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
class CollectionSitemapTests(TestCase):
    def test_colectie_fara_produse_active_nu_apare_in_sitemap(self):
        from .sitemaps import CollectionSitemap

        Collection.objects.create(nume="Goală")
        produs_inactiv = Product.objects.create(
            nume="P", brand="B", categorie=_cat("altele"), nota_mea=3, parerea_mea="x",
            activ=False,
        )
        colectie_doar_inactive = Collection.objects.create(nume="Doar inactive")
        colectie_doar_inactive.produse.add(produs_inactiv)

        colectie_vizibila = Collection.objects.create(nume="Vizibilă")
        produs_activ = Product.objects.create(
            nume="P2", brand="B", categorie=_cat("altele"), nota_mea=3, parerea_mea="x",
        )
        colectie_vizibila.produse.add(produs_activ)

        nume = [c.nume for c in CollectionSitemap().items()]
        self.assertEqual(nume, ["Vizibilă"])


class CollectionTests(TestCase):
    def test_colectie_fara_produse_nu_apare_in_lista(self):
        Collection.objects.create(nume="Goală")
        r = self.client.get(reverse("reviews:collections"))
        self.assertNotContains(r, "Goală")

    def test_colectie_cu_produse_apare_si_afiseaza_produsul(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"),
            nota_mea=3, parerea_mea="a",
        )
        colectie = Collection.objects.create(nume="Vara")
        colectie.produse.add(produs)

        r = self.client.get(reverse("reviews:collections"))
        self.assertContains(r, "Vara")

        r = self.client.get(colectie.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Test")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class CollectionsListQueryCountTests(TestCase):
    """Verifică regresia N+1 din queries.ataseaza_poze_colaj — nr. de
    query-uri pe /colectii/ nu trebuie să crească odată cu nr. de colecții
    fără copertă manuală (Prefetch, nu un query per colecție)."""

    def _colectie_cu_produs(self, nume):
        produs = Product.objects.create(
            nume=nume, brand="B", categorie=_cat("altele"), nota_mea=3, parerea_mea="x",
            poza=_poza_falsa(200, 200, nume=f"{nume}.jpg"),
        )
        colectie = Collection.objects.create(nume=nume)
        colectie.produse.add(produs)
        return colectie

    def test_numarul_de_queryuri_nu_creste_cu_numarul_de_colectii(self):
        self._colectie_cu_produs("Una")
        self._colectie_cu_produs("Doua")
        with CaptureQueriesContext(connection) as putine:
            self.client.get(reverse("reviews:collections"))

        for i in range(3, 8):
            self._colectie_cu_produs(f"Colectie{i}")
        with CaptureQueriesContext(connection) as multe:
            self.client.get(reverse("reviews:collections"))

        self.assertEqual(len(putine.captured_queries), len(multe.captured_queries))


class ColectiaSaptamaniiQueryTests(TestCase):
    """Testează queries.colectia_saptamanii() direct, fără HTTP."""

    def _produs(self, nume="P"):
        return Product.objects.create(
            nume=nume, brand="B", categorie=_cat("altele"), nota_mea=3, parerea_mea="x",
        )

    def test_fara_nicio_colectie_bifata_intoarce_none(self):
        Collection.objects.create(nume="Neutru")
        self.assertIsNone(colectia_saptamanii())

    def test_colectie_bifata_dar_fara_produse_active_nu_conteaza(self):
        Collection.objects.create(nume="Goală", recomandata_saptamana=True)
        self.assertIsNone(colectia_saptamanii())

    def test_colectie_bifata_cu_produs_activ_e_intoarsa(self):
        colectie = Collection.objects.create(nume="Vara", recomandata_saptamana=True)
        colectie.produse.add(self._produs())
        self.assertEqual(colectia_saptamanii(), colectie)

    def test_produs_inactiv_nu_conteaza_ca_activ(self):
        colectie = Collection.objects.create(nume="Ascunsă", recomandata_saptamana=True)
        produs = self._produs()
        produs.activ = False
        produs.save(update_fields=["activ"])
        colectie.produse.add(produs)
        self.assertIsNone(colectia_saptamanii())

    def test_mai_multe_bifate_ia_cea_mai_recent_modificata(self):
        veche = Collection.objects.create(nume="Veche", recomandata_saptamana=True)
        veche.produse.add(self._produs("P1"))
        noua = Collection.objects.create(nume="Nouă", recomandata_saptamana=True)
        noua.produse.add(self._produs("P2"))
        # Resalvăm "veche" ca s-o facem mai recentă decât "noua" (auto_now).
        veche.save()
        self.assertEqual(colectia_saptamanii(), veche)


@_no_ssl_redirect
class ColectiaSaptamaniiFeedTests(TestCase):
    def setUp(self):
        cache.clear()
        self.produs = Product.objects.create(
            nume="P", brand="B", categorie=_cat("altele"), nota_mea=3, parerea_mea="x",
        )
        self.colectie = Collection.objects.create(nume="Vara", recomandata_saptamana=True)
        self.colectie.produse.add(self.produs)

    def test_nu_mai_apare_pe_prima_pagina_de_la_redesign(self):
        # Blocul "Colecția săptămânii"/"Alegerea mea" a fost scos din Acasă
        # odată cu redesign-ul (Deea a cerut explicit să dispară, homepage-ul
        # nou merge direct din hero în grila de produse) — vezi și
        # ProdusHeroFallbackFeedTests mai jos. Datele/query-urile rămân
        # intacte, doar nu se mai randează.
        r = self.client.get(reverse("reviews:feed"))
        self.assertNotContains(r, "Colecția săptămânii")

    def test_nu_apare_cu_cautare_activa(self):
        r = self.client.get(reverse("reviews:feed"), {"q": "p"})
        self.assertNotContains(r, "Colecția săptămânii")

    def test_nu_apare_fara_nicio_colectie_bifata(self):
        self.colectie.recomandata_saptamana = False
        self.colectie.save()
        r = self.client.get(reverse("reviews:feed"))
        self.assertNotContains(r, "Colecția săptămânii")


class ProdusHeroFallbackQueryTests(TestCase):
    def test_alege_cel_mai_bine_notat(self):
        slab = Product.objects.create(
            nume="Slab", brand="B", categorie=_cat("altele"), nota_mea=3, parerea_mea="x",
        )
        bun = Product.objects.create(
            nume="Bun", brand="B", categorie=_cat("altele"), nota_mea=5, parerea_mea="x",
        )
        self.assertEqual(produs_hero_fallback(), bun)
        self.assertNotEqual(produs_hero_fallback(), slab)

    def test_produs_inactiv_nu_e_ales(self):
        produs = Product.objects.create(
            nume="Ascuns", brand="B", categorie=_cat("altele"), nota_mea=5,
            parerea_mea="x", activ=False,
        )
        self.assertNotEqual(produs_hero_fallback(), produs)


@_no_ssl_redirect
class ProdusHeroFallbackFeedTests(TestCase):
    def setUp(self):
        cache.clear()
        self.produs = Product.objects.create(
            nume="Cel mai bun", brand="Brand", categorie=_cat("altele"),
            nota_mea=5, parerea_mea="Text.",
        )

    def test_nu_mai_apare_de_la_redesign(self):
        # Vezi ColectiaSaptamaniiFeedTests.test_nu_mai_apare_pe_prima_pagina_de_la_redesign
        # — produs_hero_fallback() rămâne funcțional (query-ul e testat separat
        # în ProdusHeroFallbackQueryTests), doar nu se mai randează pe Acasă.
        r = self.client.get(reverse("reviews:feed"))
        self.assertNotContains(r, "Alegerea mea")


class ColectiiDeSezonQueryTests(TestCase):
    """Testează queries.colectii_de_sezon() direct, fără HTTP."""

    def _produs(self, nume="P"):
        return Product.objects.create(
            nume=nume, brand="B", categorie=_cat("altele"), nota_mea=3, parerea_mea="x",
        )

    def test_fara_nicio_colectie_bifata_e_goala(self):
        Collection.objects.create(nume="Neutru")
        self.assertEqual(list(colectii_de_sezon()), [])

    def test_colectie_bifata_fara_produse_active_nu_apare(self):
        Collection.objects.create(nume="Goală", recomandata_sezon=True)
        self.assertEqual(list(colectii_de_sezon()), [])

    def test_mai_multe_colectii_bifate_apar_toate(self):
        c1 = Collection.objects.create(nume="Vara", recomandata_sezon=True)
        c1.produse.add(self._produs("P1"))
        c2 = Collection.objects.create(nume="Iarna", recomandata_sezon=True)
        c2.produse.add(self._produs("P2"))
        self.assertEqual(set(colectii_de_sezon()), {c1, c2})


@_no_ssl_redirect
class ColectiiDeSezonFeedTests(TestCase):
    def setUp(self):
        cache.clear()
        self.produs = Product.objects.create(
            nume="P", brand="B", categorie=_cat("altele"), nota_mea=3, parerea_mea="x",
        )
        self.colectie = Collection.objects.create(nume="Vara", recomandata_sezon=True)
        self.colectie.produse.add(self.produs)

    def test_apare_pe_prima_pagina(self):
        r = self.client.get(reverse("reviews:feed"))
        self.assertContains(r, "De sezon acum")
        self.assertContains(r, "Vara")

    def test_nu_apare_fara_nicio_colectie_bifata(self):
        self.colectie.recomandata_sezon = False
        self.colectie.save()
        r = self.client.get(reverse("reviews:feed"))
        self.assertNotContains(r, "De sezon acum")


@_no_ssl_redirect
class FavoritesApiTests(TestCase):
    def test_slug_necunoscut_da_lista_goala(self):
        r = self.client.get(reverse("reviews:favorites_data"), {"slugs": "nu-exista"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"produse": []})

    def test_slug_valid_intoarce_produsul(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"),
            nota_mea=3, parerea_mea="a",
        )
        r = self.client.get(reverse("reviews:favorites_data"), {"slugs": produs.slug})
        self.assertEqual(r.json()["produse"][0]["slug"], produs.slug)

    def test_comment_count_apare_in_json(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"),
            nota_mea=3, parerea_mea="a",
        )
        Comment.objects.create(product=produs, comentariu="Super!", aprobat=True)
        r = self.client.get(reverse("reviews:favorites_data"), {"slugs": produs.slug})
        self.assertEqual(r.json()["produse"][0]["comment_count"], 1)

    def test_categorie_slug_apare_in_json(self):
        # Necesar în JS (recommendations.js) ca să ceară recomandări din
        # aceeași categorie ca favoritele — vezi RecomandariDataView.
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("ten"),
            nota_mea=3, parerea_mea="a",
        )
        r = self.client.get(reverse("reviews:favorites_data"), {"slugs": produs.slug})
        self.assertEqual(r.json()["produse"][0]["categorie_slug"], "ten")


@_no_ssl_redirect
class RecomandariApiTests(TestCase):
    def setUp(self):
        self.favorit = Product.objects.create(
            nume="Favorit", brand="B", categorie=_cat("ten"), nota_mea=4, parerea_mea="x",
        )
        self.recomandat = Product.objects.create(
            nume="Recomandat", brand="B", categorie=_cat("ten"), nota_mea=5, parerea_mea="x",
        )
        self.alta_categorie = Product.objects.create(
            nume="Altă categorie", brand="B", categorie=_cat("buze"), nota_mea=5, parerea_mea="x",
        )

    def test_fara_categorie_intoarce_lista_goala(self):
        r = self.client.get(reverse("reviews:recomandari_data"))
        self.assertEqual(r.json(), {"produse": []})

    def test_recomanda_din_aceeasi_categorie_excluzand_favoritele(self):
        r = self.client.get(reverse("reviews:recomandari_data"), {
            "categorie": "ten", "exclude": self.favorit.slug,
        })
        slugs = [p["slug"] for p in r.json()["produse"]]
        self.assertEqual(slugs, [self.recomandat.slug])
        self.assertNotIn(self.alta_categorie.slug, slugs)

    def test_produs_inactiv_nu_e_recomandat(self):
        self.recomandat.activ = False
        self.recomandat.save(update_fields=["activ"])
        r = self.client.get(reverse("reviews:recomandari_data"), {"categorie": "ten"})
        slugs = [p["slug"] for p in r.json()["produse"]]
        self.assertNotIn(self.recomandat.slug, slugs)


@_no_ssl_redirect
class SearchDataApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.p1 = Product.objects.create(
            nume="Soft Pinch Liquid Blush", brand="Rare Beauty", categorie=_cat("ten"),
            nota_mea=5, parerea_mea="Text.", sursa="Sephora",
        )
        self.p2 = Product.objects.create(
            nume="Gloss Bomb", brand="Fenty Beauty", categorie=_cat("buze"),
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
        r = self.client.get(reverse("reviews:search_data"), {"categorie": "buze"})
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

    def test_cautare_normala_nu_atinge_limita(self):
        # Căutarea live trimite o cerere per literă tastată — un prag prea
        # strict ar rupe folosirea normală, nu doar abuzul.
        cache.clear()
        for _ in range(20):
            r = self.client.get(reverse("reviews:search_data"), {"q": "a"})
            self.assertEqual(r.status_code, 200)

    def test_rate_limit_dupa_prag(self):
        cache.clear()
        self.addCleanup(cache.clear)
        for _ in range(60):
            self.client.get(reverse("reviews:search_data"))
        r = self.client.get(reverse("reviews:search_data"))
        self.assertEqual(r.status_code, 429)


@_no_ssl_redirect
class StoryImageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.produs = Product.objects.create(
            nume="Soft Pinch Liquid Blush", brand="Rare Beauty", categorie=_cat("ten"),
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

    def test_produs_dezactivat_da_404(self):
        self.produs.activ = False
        self.produs.save()
        r = self.client.get(
            reverse("reviews:product_story_image", args=[self.produs.slug])
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

    def test_emoji_din_parere_e_scos_nu_arata_ca_patratel_gol(self):
        # Fonturile bundle-uite (Fraunces/DejaVu) n-au glyph-uri de emoji —
        # fără sanitizare, un 🍉 scris într-o părere reală apărea ca un
        # pătrățel gol ("tofu") pe imaginea generată.
        self.assertNotIn("🍉", _safe_text("Mi-a plăcut 🍉 mult."))

    def test_safe_text_pastreaza_punctuatia_uzuala_din_denumiri(self):
        # + & / apar des în denumiri reale (ex: "PHA+BHA") — nu trebuie
        # scoase odată cu emoji-urile.
        self.assertEqual(
            _safe_text('Toner PHA+BHA & Ser "de zi"/noapte'),
            'Toner PHA+BHA & Ser "de zi"/noapte',
        )

    def test_genereaza_imaginea_fara_eroare_cu_emoji_in_parere(self):
        produs = Product.objects.create(
            nume="Watermelon Glow Toner", brand="Glow Recipe", categorie=_cat("altele"),
            nota_mea=5, parerea_mea="Mi-a plăcut mult 🍉 și are PHA+BHA.",
        )
        build_story_image(produs, "glowdiary.pythonanywhere.com")


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

    def test_contact_honeypot_cu_mesaj_gol_ramane_mesaj_generic(self):
        cache.clear()
        r = self.client.post(reverse("reviews:contact"), {
            "nume": "Bot", "email": "bot@spam.com", "mesaj": "",
            "website": "http://spam.com",
        }, follow=True)
        self.assertEqual(ContactMessage.objects.count(), 0)
        text_mesaje = [str(m) for m in r.context["messages"]]
        self.assertTrue(any("Nu am putut trimite mesajul" in m for m in text_mesaje))

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
            "form-0-categorie": str(_cat("ten").pk), "form-0-nuanta": "", "form-0-sursa": "Sephora",
            "form-0-nota_mea": "5", "form-0-parerea_mea": "Super produs.",
            # rândul 1 rămâne complet gol — trebuie ignorat, nu trebuie să dea eroare
            "form-1-brand": "", "form-1-nume": "", "form-1-categorie": "",
            "form-1-nuanta": "", "form-1-sursa": "", "form-1-nota_mea": "",
            "form-1-parerea_mea": "",
            "form-2-brand": "Fenty Beauty", "form-2-nume": "Gloss Bomb",
            "form-2-categorie": str(_cat("buze").pk), "form-2-nuanta": "", "form-2-sursa": "Douglas",
            "form-2-nota_mea": "4", "form-2-parerea_mea": "Mi-a plăcut mult.",
        })
        r = self.client.post(self.url, data)
        self.assertRedirects(r, reverse("admin:reviews_product_changelist"))
        self.assertEqual(Product.objects.count(), 2)
        self.assertTrue(Product.objects.filter(brand="Rare Beauty").exists())
        self.assertTrue(Product.objects.filter(brand="Fenty Beauty").exists())


class StarsSvgTagTests(TestCase):
    def test_valoare_intreaga_da_stele_pline_si_goale(self):
        html = stars_svg(3)
        self.assertEqual(html.count("star-ico-empty"), 2)
        self.assertEqual(html.count('class="star-ico"'), 3)
        self.assertNotIn("star-ico-half", html)

    def test_valoare_fractionara_da_o_jumatate_de_stea(self):
        html = stars_svg(4.6)
        self.assertIn("star-ico-half", html)

    def test_valoare_in_afara_intervalului_e_limitata(self):
        html = stars_svg(9)
        self.assertEqual(html.count('class="star-ico"'), 5)
        self.assertNotIn("star-ico-empty", html)


@_no_ssl_redirect
class VerdictFieldsTests(TestCase):
    def test_recumpar_adevarat_arata_badge_si_da(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=5, parerea_mea="a",
            pret="99.90", il_recumpar=True, tine_cat="8 ore",
        )
        r = self.client.get(produs.get_absolute_url())
        self.assertContains(r, "badge-recumpar")
        self.assertContains(r, "99,90 lei")
        self.assertContains(r, "Da ↻")
        self.assertContains(r, "verdict-value-yes")
        self.assertContains(r, "8 ore")

    def test_recumpar_fals_arata_nu_fara_badge(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=3, parerea_mea="a",
            il_recumpar=False,
        )
        r = self.client.get(produs.get_absolute_url())
        self.assertNotContains(r, "badge-recumpar")
        self.assertContains(r, "Îl recumpăr?")

    def test_recumpar_nedecis_nu_arata_nici_da_nici_nu(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=3, parerea_mea="a",
        )
        r = self.client.get(produs.get_absolute_url())
        self.assertNotContains(r, "badge-recumpar")
        self.assertNotContains(r, "verdict-card")

    def test_tag_uri_apar_pe_pagina_produsului(self):
        produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=3, parerea_mea="a",
        )
        produs.tag_uri.add(Tag.objects.get_or_create(nume="Vegan")[0])
        r = self.client.get(produs.get_absolute_url())
        self.assertContains(r, "Vegan")


@_no_ssl_redirect
class TagSiPretFilterTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ieftin = Product.objects.create(
            nume="Ieftin", brand="A", categorie=_cat("buze"), nota_mea=4, parerea_mea="x", pret="40",
        )
        self.scump = Product.objects.create(
            nume="Scump", brand="B", categorie=_cat("buze"), nota_mea=4, parerea_mea="x", pret="250",
        )
        self.vegan_tag = Tag.objects.get_or_create(nume="Vegan")[0]
        self.ieftin.tag_uri.add(self.vegan_tag)

    def test_filtru_tag_in_feed(self):
        r = self.client.get(reverse("reviews:feed"), {"tag": self.vegan_tag.slug})
        self.assertContains(r, "Ieftin")
        self.assertNotContains(r, "Scump")

    def test_filtru_pret_max_in_feed(self):
        r = self.client.get(reverse("reviews:feed"), {"pret_max": "100"})
        self.assertContains(r, "Ieftin")
        self.assertNotContains(r, "Scump")

    def test_filtru_tag_in_api_cautare(self):
        r = self.client.get(reverse("reviews:search_data"), {"tag": self.vegan_tag.slug})
        slugs = [p["slug"] for p in r.json()["produse"]]
        self.assertEqual(slugs, [self.ieftin.slug])

    def test_json_api_trimite_nota_numerica(self):
        r = self.client.get(reverse("reviews:search_data"))
        primul = r.json()["produse"][0]
        self.assertIn("nota", primul)
        self.assertIn("il_recumpar", primul)
        self.assertNotIn("stele", primul)


@_no_ssl_redirect
class ComentariuCuPozaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.produs = Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=3, parerea_mea="a",
        )

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_poza_atasata_se_salveaza_si_apare(self):
        r = self.client.post(self.produs.get_absolute_url(), {
            "nume": "Ana", "nota": "5", "comentariu": "Super, uite poza!",
            "website": "", "imagine": _poza_falsa(500, 500, nume="comentariu.jpg"),
        })
        self.assertRedirects(r, self.produs.get_absolute_url() + "?prima-parere=1")
        comentariu = Comment.objects.get(product=self.produs)
        self.assertTrue(comentariu.imagine)

        r2 = self.client.get(self.produs.get_absolute_url())
        self.assertContains(r2, "comment-photo")

    def test_fara_poza_ramane_optional(self):
        r = self.client.post(self.produs.get_absolute_url(), {
            "nume": "Ana", "nota": "5", "comentariu": "Fără poză, tot bine.", "website": "",
        })
        self.assertRedirects(r, self.produs.get_absolute_url() + "?prima-parere=1")
        self.assertEqual(Comment.objects.filter(product=self.produs).count(), 1)

    def test_poza_peste_5mb_e_respinsa_de_formular(self):
        # Test direct pe formular (nu prin HTTP): encoder-ul multipart al
        # clientului de test trimite conținutul real al fișierului (mic),
        # ignorând un `.size` suprascris manual — clean_imagine citește
        # `imagine.size`, deci verificăm exact asta, la nivel de formular.
        poza_marcata_mare = _poza_falsa(10, 10, nume="mica.jpg")
        poza_marcata_mare.size = MAX_UPLOAD_IMAGINE_BYTES + 1
        form = CommentForm(
            data={"comentariu": "Poză uriașă.", "website": ""},
            files={"imagine": poza_marcata_mare},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("mai mare de 5 MB", str(form.errors["imagine"]))

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_poza_cu_rezolutie_extrema_e_respinsa(self):
        # Peste MAX_PIXELI_ACCEPTATI (40MP) — tratată ca posibilă decompression bomb.
        poza_bomba = _poza_falsa(7000, 6000, nume="bomba.jpg")
        r = self.client.post(self.produs.get_absolute_url(), {
            "nume": "Ana", "nota": "5", "comentariu": "Poză cu rezoluție extremă.",
            "website": "", "imagine": poza_bomba,
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Comment.objects.filter(product=self.produs).count(), 0)
        self.assertContains(r, "dimensiuni prea mari")


class RedisDeployCheckTests(TestCase):
    def test_debug_true_ignora_lipsa_redis(self):
        with override_settings(DEBUG=True), mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(verifica_redis_in_productie(None), [])

    def test_debug_false_fara_redis_fara_single_worker_e_eroare(self):
        with override_settings(DEBUG=False), mock.patch.dict(os.environ, {}, clear=True):
            erori = verifica_redis_in_productie(None)
        self.assertEqual(len(erori), 1)
        self.assertEqual(erori[0].id, "reviews.E002")

    def test_debug_false_cu_redis_url_e_curat(self):
        with override_settings(DEBUG=False), mock.patch.dict(
            os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=True
        ):
            self.assertEqual(verifica_redis_in_productie(None), [])

    def test_debug_false_cu_single_worker_e_curat(self):
        with override_settings(DEBUG=False), mock.patch.dict(
            os.environ, {"SINGLE_WORKER": "True"}, clear=True
        ):
            self.assertEqual(verifica_redis_in_productie(None), [])


@_no_ssl_redirect
class AnRecapTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_sub_prag_arata_mesaj_prietenos_nu_eroare(self):
        Product.objects.create(
            nume="Test", brand="Brand", categorie=_cat("altele"), nota_mea=3, parerea_mea="a",
        )
        r = self.client.get(reverse("reviews:an_recap", args=[timezone.now().year]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "prea puține")

    def test_peste_prag_arata_statistici(self):
        for i in range(10):
            Product.objects.create(
                nume=f"Produs {i}", brand="Rare Beauty", categorie=_cat("ten"),
                nota_mea=5, parerea_mea="x", pret="50", il_recumpar=(i % 2 == 0),
            )
        r = self.client.get(reverse("reviews:an_recap", args=[timezone.now().year]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Rare Beauty")
        self.assertContains(r, "10")
