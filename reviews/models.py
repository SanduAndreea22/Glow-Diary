from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

NOTA_CHOICES = [(i, str(i)) for i in range(1, 6)]

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
    ("altele", "Altele"),
]


class Product(models.Model):
    nume = models.CharField("Nume produs", max_length=150)
    brand = models.CharField("Brand", max_length=100)
    categorie = models.CharField(
        "Categorie", max_length=30, choices=CATEGORIE_CHOICES
    )
    nuanta = models.CharField(
        "Nuanță", max_length=100, blank=True,
        help_text="Opțional — nu toate categoriile au nuanță.",
    )
    sursa = models.CharField(
        "Cumpărat de la", max_length=100, blank=True,
        help_text="Ex: Sephora, Douglas, Notino, magazin fizic...",
    )
    poza = models.ImageField("Poză", upload_to="produse/", blank=True)
    nota_mea = models.PositiveSmallIntegerField(
        "Nota mea", choices=NOTA_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    parerea_mea = models.TextField("Părerea mea")
    data_postarii = models.DateTimeField("Data postării", auto_now_add=True)
    slug = models.SlugField(max_length=180, unique=True, blank=True)

    class Meta:
        ordering = ["-data_postarii"]

    def __str__(self):
        return f"{self.brand} — {self.nume}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.brand}-{self.nume}")[:170]
            slug = base_slug
            i = 2
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("reviews:product_detail", kwargs={"slug": self.slug})

    @property
    def stele(self):
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
        if not self.slug:
            base_slug = slugify(self.nume)[:170]
            slug = base_slug
            i = 2
            while Collection.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{i}"
                i += 1
            self.slug = slug
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
    data = models.DateTimeField("Data", auto_now_add=True)
    aprobat = models.BooleanField(
        "Aprobat", default=True,
        help_text="Debifează pentru a ascunde comentariul din public fără să-l ștergi.",
    )

    class Meta:
        ordering = ["-data"]

    def __str__(self):
        return f"{self.nume or 'anonim'} @ {self.product}"

    @property
    def stele(self):
        return "★" * self.nota if self.nota else ""


class ContactMessage(models.Model):
    nume = models.CharField("Nume", max_length=100, blank=True)
    email = models.EmailField("Email")
    mesaj = models.TextField("Mesaj")
    data = models.DateTimeField("Data", auto_now_add=True)
    citit = models.BooleanField("Citit", default=False)

    class Meta:
        ordering = ["-data"]

    def __str__(self):
        return f"{self.nume or self.email} — {self.data:%d.%m.%Y}"
