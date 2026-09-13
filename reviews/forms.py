from django import forms
from django.utils.text import slugify

from .models import (
    MAX_SLUG_ATTEMPTS,
    NOTA_CHOICES,
    Collection,
    Comment,
    ContactMessage,
    Product,
)


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

    class Meta:
        model = Comment
        fields = ["nume", "nota", "comentariu"]

    def clean_comentariu(self):
        comentariu = self.cleaned_data.get("comentariu", "").strip()
        if not comentariu:
            raise forms.ValidationError("Scrie câteva cuvinte despre experiența ta.")
        return comentariu


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


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = "__all__"

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
