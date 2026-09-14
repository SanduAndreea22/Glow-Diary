from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.urls import reverse
from django.utils.text import slugify

from .image_utils import optimizeaza_poza

NOTA_CHOICES = [(i, str(i)) for i in range(1, 6)]

MAX_SLUG_ATTEMPTS = 20


def _save_with_unique_slug(instance, base_text, save_fn):
    """
    Generează un slug unic pornind de la `base_text` și salvează `instance`
    prin `save_fn`. Retry pe IntegrityError (nu doar check-then-set) ca să
    evite race condition-ul la creare simultană cu același nume.
    """
    base_slug = slugify(base_text)[:170]
    model_cls = type(instance)
    slug = instance.slug or base_slug
    suffix = 2

    for _ in range(MAX_SLUG_ATTEMPTS):
        instance.slug = slug
        try:
            with transaction.atomic():
                save_fn()
            return
        except IntegrityError:
            slug = f"{base_slug}-{suffix}"
            suffix += 1

    raise IntegrityError(
        f"Nu am putut genera un slug unic pentru {model_cls.__name__} după "
        f"{MAX_SLUG_ATTEMPTS} încercări."
    )

CATEGORIE_CHOICES = [
    ("ruj", "Ruj"),
    ("gloss", "Gloss"),
    ("blush", "Blush"),
    ("iluminator", "Iluminator"),
    ("pudra", "Pudră"),
    ("fond-de-ten", "Fond de ten"),
    ("corector", "Corector"),
    ("primer", "Primer"),
    ("mascara", "Mascara"),
    ("farduri-pleoape", "Farduri de pleoape"),
    ("creion-ochi", "Creion de ochi"),
    ("sprancene", "Sprâncene"),
    ("ser", "Ser"),
    ("crema-hidratanta", "Cremă hidratantă"),
    ("toner", "Toner"),
    ("exfoliant", "Exfoliant"),
    ("demachiant", "Demachiant"),
    ("masca", "Mască"),
    ("protectie-solara", "Protecție solară"),
    ("altele", "Altele"),
]


class Tag(models.Model):
    """Atribut liber de filtrare (tip de ten, ingrediente, etc.) — set
    propus într-o migrare de date, dar complet editabil din admin după
    aceea (Deea poate adăuga/șterge oricând, fără cod)."""

    nume = models.CharField("Nume", max_length=40, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)

    class Meta:
        ordering = ["nume"]
        verbose_name = "Tag"
        verbose_name_plural = "Tag-uri"

    def __str__(self):
        return self.nume

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nume)[:50]
        super().save(*args, **kwargs)


class Product(models.Model):
    nume = models.CharField("Nume produs", max_length=150)
    brand = models.CharField("Brand", max_length=100)
    categorie = models.CharField(
        "Categorie", max_length=30, choices=CATEGORIE_CHOICES, db_index=True
    )
    nuanta = models.CharField(
        "Nuanță", max_length=100, blank=True,
        help_text="Opțional — nu toate categoriile au nuanță.",
    )
    sursa = models.CharField(
        "Cumpărat de la", max_length=100, blank=True, db_index=True,
        help_text="Ex: Sephora, Douglas, Notino, magazin fizic...",
    )
    poza = models.ImageField("Poză", upload_to="produse/", blank=True)
    nota_mea = models.PositiveSmallIntegerField(
        "Nota mea", choices=NOTA_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    parerea_mea = models.TextField("Părerea mea")
    pret = models.DecimalField(
        "Preț (lei)", max_digits=8, decimal_places=2, null=True, blank=True,
        help_text=(
            "Cât ai plătit pe el — opțional, dar e exact ce vine să afle "
            "cineva care se întreabă dacă merită banii."
        ),
    )
    il_recumpar = models.BooleanField(
        "Îl recumpăr", null=True, blank=True, default=None,
        help_text=(
            "Da/Nu doar dacă te-ai hotărât — lasă necompletat cât timp nu "
            "știi încă, altfel un produs proaspăt postat ar arăta public "
            "„nu-l recumpăr” fără să fi spus tu asta. Da = sigiliu auriu pe card."
        ),
    )
    tine_cat = models.CharField(
        "Cât ține", max_length=60, blank=True,
        help_text="Ex: 8 ore, toată ziua, se șterge repede după masă...",
    )
    pentru_cine = models.CharField(
        "Recomandat pentru", max_length=150, blank=True,
        help_text="Ex: ten gras, buze uscate, începătoare la machiaj...",
    )
    tag_uri = models.ManyToManyField(
        Tag, blank=True, related_name="produse", verbose_name="Tag-uri",
        help_text="Atribute libere de filtrare (tip de ten, ingrediente etc.) — opțional.",
    )
    data_postarii = models.DateTimeField(
        "Data postării", auto_now_add=True, db_index=True
    )
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    activ = models.BooleanField(
        "Activ", default=True, db_index=True,
        help_text=(
            "Debifat = ascuns pe site (soft-delete) — rămâne în admin, cu "
            "comentariile și pozele intacte, și poate fi reactivat oricând."
        ),
    )

    class Meta:
        ordering = ["-data_postarii"]

    def __str__(self):
        return f"{self.brand} — {self.nume}"

    def save(self, *args, **kwargs):
        optimizeaza_poza(self.poza)
        if not self.slug:
            _save_with_unique_slug(
                self, f"{self.brand}-{self.nume}",
                lambda: models.Model.save(self, *args, **kwargs),
            )
        else:
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # "Delete" din admin ascunde prima dată (comentariile/pozele rămân
        # legate, recuperabile) — abia pe un produs deja ascuns, Delete
        # șterge cu adevărat. Fără asta, un click greșit pe Delete era
        # ireversibil.
        if self.activ:
            self.activ = False
            self.save(update_fields=["activ"])
        else:
            super().delete(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("reviews:product_detail", kwargs={"slug": self.slug})

    @property
    def stele(self):
        # Nefolosit intern — randarea reală a stelelor (server + client) se
        # face prin `stars_svg`/`GlowStars.render`. Păstrat doar ca API
        # public (text simplu ★/☆), pentru orice consumator extern viitor.
        return "★" * self.nota_mea + "☆" * (5 - self.nota_mea)


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="imagini"
    )
    imagine = models.ImageField("Imagine", upload_to="produse/galerie/")
    ordine = models.PositiveSmallIntegerField("Ordine", default=0)

    class Meta:
        ordering = ["ordine", "id"]
        verbose_name = "Imagine galerie"
        verbose_name_plural = "Imagini galerie"

    def save(self, *args, **kwargs):
        optimizeaza_poza(self.imagine)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Imagine {self.ordine} — {self.product}"


class Collection(models.Model):
    nume = models.CharField("Nume colecție", max_length=150)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    descriere = models.TextField(
        "Descriere", blank=True,
        help_text="Un rând-două despre ce leagă produsele din colecție.",
    )
    coperta = models.ImageField("Copertă", upload_to="colectii/", blank=True)
    produse = models.ManyToManyField(
        Product, related_name="colectii", blank=True, verbose_name="Produse"
    )
    data_creare = models.DateTimeField("Data creării", auto_now_add=True)

    class Meta:
        ordering = ["-data_creare"]

    def __str__(self):
        return self.nume

    def save(self, *args, **kwargs):
        optimizeaza_poza(self.coperta)
        if not self.slug:
            _save_with_unique_slug(
                self, self.nume,
                lambda: models.Model.save(self, *args, **kwargs),
            )
        else:
            super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("reviews:collection_detail", kwargs={"slug": self.slug})


class Comment(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="comentarii"
    )
    nume = models.CharField(
        "Nume", max_length=60, blank=True, default="anonim"
    )
    nota = models.PositiveSmallIntegerField(
        "Notă", choices=NOTA_CHOICES, null=True, blank=True
    )
    comentariu = models.TextField("Comentariu", max_length=600)
    imagine = models.ImageField(
        # Doar `blank=True` — la fel ca Product.poza/ProductImage.imagine/
        # Collection.coperta. Fără `null=True` (înlăturat aici), un
        # ImageField "fără fișier" e mereu "" (string gol), niciodată NULL —
        # o singură reprezentare pentru "fără poză" în toate modelele,
        # nu două diferite fără motiv funcțional.
        "Poză (opțional)", upload_to="comentarii/", blank=True,
        help_text="O poză cu produsul la tine, dacă vrei să o arăți alături de părere.",
    )
    data = models.DateTimeField("Data", auto_now_add=True)
    aprobat = models.BooleanField(
        "Aprobat", default=True, db_index=True,
        help_text="Debifează pentru a ascunde comentariul din public fără să-l ștergi.",
    )

    class Meta:
        ordering = ["-data"]

    def __str__(self):
        return f"{self.nume or 'anonim'} @ {self.product}"

    def save(self, *args, **kwargs):
        optimizeaza_poza(self.imagine)
        super().save(*args, **kwargs)

    @property
    def stele(self):
        # Nefolosit intern — vezi nota de la Product.stele.
        return "★" * self.nota if self.nota else ""


class ContactMessage(models.Model):
    nume = models.CharField("Nume", max_length=100, blank=True)
    email = models.EmailField("Email")
    mesaj = models.TextField("Mesaj", max_length=4000)
    data = models.DateTimeField("Data", auto_now_add=True)
    citit = models.BooleanField("Citit", default=False)

    class Meta:
        ordering = ["-data"]

    def __str__(self):
        return f"{self.nume or self.email} — {self.data:%d.%m.%Y}"
