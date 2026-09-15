from django import forms
from django.db.models.functions import Coalesce
from django.utils.text import slugify
from PIL import Image

from .image_utils import MAX_PIXELI_ACCEPTATI
from .models import (
    MAX_SLUG_ATTEMPTS,
    NOTA_CHOICES,
    Categorie,
    Collection,
    Comment,
    ContactMessage,
    Product,
)


def _categorii_frunza():
    """Un produs se leagă mereu de o categorie-frunză (subcategorie, sau
    grup fără subcategorii, ex. Parfumuri/Altele) — niciodată de un grup
    care are subcategorii (ex. „Machiaj” direct, fără să aleagă Ten/Ochi/...)."""
    return (
        Categorie.objects.filter(subcategorii__isnull=True)
        .select_related("grup")
        .annotate(grup_ordine=Coalesce("grup__ordine", "ordine"))
        .order_by("grup_ordine", "grup__nume", "ordine", "nume")
    )

# Endpoint public, fără autentificare — Django nu respinge automat fișiere
# mari (FILE_UPLOAD_MAX_MEMORY_SIZE e doar pragul de spooling pe disc, nu
# un refuz), deci fără plafonul ăsta un vizitator anonim putea încărca
# fișiere oricât de mari, limitat doar de rate-limiting-ul de pe formular.
MAX_UPLOAD_IMAGINE_BYTES = 5 * 1024 * 1024


class HoneypotFormMixin(forms.Form):
    """Câmp ascuns comun anti-spam pe formularele publice (comentariu, contact):
    boții completează orice câmp, oamenii nu văd (și deci nu completează) unul
    ascuns prin CSS."""

    website = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError("Spam detectat.")
        return value


class CommentForm(HoneypotFormMixin, forms.ModelForm):
    """Formular public, fără cont, pentru comentarii pe pagina de produs."""

    # Declarat explicit (nu lăsat să fie generat automat de ModelForm din
    # câmpul modelului) — altfel Django preia `default="anonim"` de pe
    # Comment.nume ca `initial` al câmpului de formular, iar un formular
    # nelegat (pagina goală, la prima încărcare) apare cu "anonim" deja
    # scris în input, ca un bug vizibil, nu ca placeholder.
    nume = forms.CharField(
        label="Nume",
        max_length=60,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Numele tău (opțional)"}),
    )

    nota = forms.TypedChoiceField(
        label="Notă",
        choices=[("", "—")] + list(NOTA_CHOICES),
        coerce=int,
        required=False,
    )

    comentariu = forms.CharField(
        label="Comentariu",
        max_length=600,
        widget=forms.Textarea(attrs={"placeholder": "Scrie părerea ta...", "rows": 3}),
        error_messages={"required": "Scrie câteva cuvinte despre experiența ta."},
    )

    imagine = forms.ImageField(label="Poză (opțional)", required=False)

    class Meta:
        model = Comment
        fields = ["nume", "nota", "comentariu", "imagine"]

    def clean_comentariu(self):
        comentariu = self.cleaned_data.get("comentariu", "").strip()
        if not comentariu:
            raise forms.ValidationError("Scrie câteva cuvinte despre experiența ta.")
        return comentariu

    def clean_imagine(self):
        imagine = self.cleaned_data.get("imagine")
        if not imagine:
            return imagine

        if imagine.size > MAX_UPLOAD_IMAGINE_BYTES:
            raise forms.ValidationError(
                "Poza e prea mare (peste 5MB) — încearcă una mai mică."
            )

        try:
            imagine.seek(0)
            with Image.open(imagine) as img:
                latime, inaltime = img.size
        except Exception:
            raise forms.ValidationError("Fișierul nu pare să fie o imagine validă.")
        finally:
            imagine.seek(0)

        if latime * inaltime > MAX_PIXELI_ACCEPTATI:
            raise forms.ValidationError(
                "Poza are o rezoluție neobișnuit de mare — încearcă una mai mică."
            )
        return imagine


class ContactForm(HoneypotFormMixin, forms.ModelForm):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"placeholder": "emailul tău"}),
        error_messages={
            "required": "Lasă-mi un email ca să-ți pot răspunde.",
            "invalid": "Verifică emailul — pare să fie greșit.",
        },
    )
    mesaj = forms.CharField(
        label="Mesaj",
        max_length=4000,
        widget=forms.Textarea(attrs={"placeholder": "Scrie-mi mesajul tău...", "rows": 5}),
        error_messages={"required": "Scrie-mi câteva rânduri, ca să știu despre ce e vorba."},
    )

    class Meta:
        model = ContactMessage
        fields = ["nume", "email", "mesaj"]
        widgets = {
            "nume": forms.TextInput(attrs={"placeholder": "Numele tău (opțional)"}),
        }


class ProductBulkForm(forms.ModelForm):
    """Un rând din formularul de adăugare în bulk (admin) — fără poză;
    aceea rămâne de adăugat individual, per produs, după import."""

    categorie = forms.ModelChoiceField(queryset=_categorii_frunza(), label="Categorie")

    class Meta:
        model = Product
        fields = ["brand", "nume", "categorie", "nuanta", "sursa", "nota_mea", "parerea_mea"]
        widgets = {
            "parerea_mea": forms.Textarea(attrs={"rows": 2}),
        }


ProductBulkFormSet = forms.modelformset_factory(
    Product, form=ProductBulkForm, extra=8, can_delete=False,
)


def _slug_ar_epuiza_incercarile(model_cls, base_text):
    """Verificare preventivă: dacă baza de slug e deja ocupată de
    MAX_SLUG_ATTEMPTS variante (base, base-2, base-3, ...), generarea
    automată din save() ar epuiza toate încercările și ar ridica un
    IntegrityError necaptat — mai bine un mesaj clar în formular decât
    o eroare 500 în admin."""
    base_slug = slugify(base_text)[:170]
    existente = model_cls.objects.filter(slug__startswith=base_slug).count()
    return existente >= MAX_SLUG_ATTEMPTS


class CategorieSelect(forms.Select):
    """`<select>` obișnuit, dar cu `data-grup` pe fiecare `<option>` — JS-ul
    de cascadă (static/admin/reviews/product_categorie_cascade.js) filtrează
    lista vizibilă de subcategorii după grupul ales, fără AJAX."""

    grup_dupa_categorie = {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            grup_id = self.grup_dupa_categorie.get(value.value if hasattr(value, "value") else value)
            if grup_id is not None:
                option["attrs"]["data-grup"] = grup_id
        return option


class ProductAdminForm(forms.ModelForm):
    # Nu e câmp de model — doar ajută JS-ul de cascadă să filtreze
    # dropdown-ul de mai jos (`categorie`) la subcategoriile grupului ales.
    # Câmpul salvat efectiv rămâne `categorie` (o frunză), niciodată `grup`.
    grup = forms.ModelChoiceField(
        queryset=Categorie.objects.filter(grup__isnull=True).order_by("ordine", "nume"),
        required=False, label="Grup",
        help_text="Alege întâi grupul — categoria de mai jos se filtrează automat.",
    )

    class Meta:
        model = Product
        fields = "__all__"
        widgets = {"categorie": CategorieSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        frunze = _categorii_frunza()
        self.fields["categorie"].queryset = frunze
        self.fields["categorie"].widget.grup_dupa_categorie = {
            str(c.pk): str(c.grup_id or c.pk) for c in frunze
        }
        if self.instance.pk and self.instance.categorie_id:
            leaf = self.instance.categorie
            self.initial["grup"] = leaf.grup_id or leaf.pk

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and not cleaned.get("slug"):
            base_text = f"{cleaned.get('brand', '')}-{cleaned.get('nume', '')}"
            if _slug_ar_epuiza_incercarile(Product, base_text):
                raise forms.ValidationError(
                    "Există deja prea multe produse cu acest brand+nume — "
                    "completează manual câmpul Slug cu ceva distinctiv."
                )
        return cleaned


class CollectionAdminForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and not cleaned.get("slug"):
            if _slug_ar_epuiza_incercarile(Collection, cleaned.get("nume", "")):
                raise forms.ValidationError(
                    "Există deja prea multe colecții cu acest nume — "
                    "completează manual câmpul Slug cu ceva distinctiv."
                )
        return cleaned
