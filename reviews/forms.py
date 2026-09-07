from django import forms

from .models import Comment, ContactMessage, NOTA_CHOICES


class CommentForm(forms.ModelForm):
    """Formular public, fără cont, pentru comentarii pe pagina de produs."""

    nota = forms.TypedChoiceField(
        label="Notă",
        choices=[("", "—")] + list(NOTA_CHOICES),
        coerce=int,
        required=False,
    )
    # honeypot: câmp ascuns prin CSS; boturile îl completează, oamenii nu.
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    comentariu = forms.CharField(
        label="Comentariu",
        max_length=600,
        widget=forms.Textarea(attrs={"placeholder": "Scrie părerea ta...", "rows": 3}),
        error_messages={"required": "Scrie câteva cuvinte despre experiența ta."},
    )

    class Meta:
        model = Comment
        fields = ["nume", "nota", "comentariu"]
        widgets = {
            "nume": forms.TextInput(attrs={"placeholder": "Numele tău (opțional)"}),
        }

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError("Spam detectat.")
        return value

    def clean_comentariu(self):
        comentariu = self.cleaned_data.get("comentariu", "").strip()
        if not comentariu:
            raise forms.ValidationError("Scrie câteva cuvinte despre experiența ta.")
        return comentariu


class ContactForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput())

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
        widget=forms.Textarea(attrs={"placeholder": "Scrie-mi mesajul tău...", "rows": 5}),
        error_messages={"required": "Scrie-mi câteva rânduri, ca să știu despre ce e vorba."},
    )

    class Meta:
        model = ContactMessage
        fields = ["nume", "email", "mesaj"]
        widgets = {
            "nume": forms.TextInput(attrs={"placeholder": "Numele tău (opțional)"}),
        }

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError("Spam detectat.")
        return value
