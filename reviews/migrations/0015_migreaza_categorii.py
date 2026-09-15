from django.db import migrations
from django.utils.text import slugify

# (grup, subcategorie_sau_None, ordine) — structura completă a taxonomiei,
# decisă cu Deea (grupuri fixe, subcategorii editabile ulterior din admin).
TAXONOMIE = [
    ("Parfumuri", None, 10),
    ("Machiaj", None, 20),
    ("Machiaj", "Demachiante", 10),
    ("Machiaj", "Ten", 20),
    ("Machiaj", "Ochi", 30),
    ("Machiaj", "Buze", 40),
    ("Machiaj", "Sprâncene", 50),
    ("Machiaj", "Accesorii", 60),
    ("Îngrijire ten", None, 30),
    ("Îngrijire ten", "Cremă de zi", 10),
    ("Îngrijire ten", "Cremă de noapte", 20),
    ("Îngrijire ten", "Cremă hidratantă", 30),
    ("Îngrijire ten", "Ser", 40),
    ("Îngrijire ten", "Scrub & exfoliant", 50),
    ("Îngrijire ten", "Toner", 60),
    ("Îngrijire ten", "Mască", 70),
    ("Îngrijire ten", "Protecție solară", 80),
    ("Îngrijire ten", "Îngrijire contur ochi", 90),
    ("Îngrijire ten", "Îngrijire buze", 100),
    ("Îngrijire ten", "Îngrijire gene", 110),
    ("Îngrijire ten", "Îngrijire sprâncene", 120),
    ("Baie și corp", None, 40),
    ("Baie și corp", "Gel de duș", 10),
    ("Baie și corp", "Săpun", 20),
    ("Baie și corp", "Scrub și exfoliant corp", 30),
    ("Baie și corp", "Ulei de corp", 40),
    ("Baie și corp", "Cremă de corp", 50),
    ("Baie și corp", "Cremă de mâini", 60),
    ("Baie și corp", "Bodymist-uri", 70),
    ("Păr", None, 50),
    ("Păr", "Șampon", 10),
    ("Păr", "Balsam", 20),
    ("Altele", None, 60),
]

# vechiul slug (CharField, choices) -> (grup, subcategorie_sau_None) unde
# produsul ajunge în noua taxonomie. Toate cele 26 valori vechi acoperite.
MAPARE_VECHI_NOU = {
    "ruj": ("Machiaj", "Buze"),
    "gloss": ("Machiaj", "Buze"),
    "contur-buze": ("Machiaj", "Buze"),
    "blush": ("Machiaj", "Ten"),
    "iluminator": ("Machiaj", "Ten"),
    "pudra": ("Machiaj", "Ten"),
    "fond-de-ten": ("Machiaj", "Ten"),
    "corector": ("Machiaj", "Ten"),
    "primer": ("Machiaj", "Ten"),
    "fixator": ("Machiaj", "Ten"),
    "mascara": ("Machiaj", "Ochi"),
    "farduri-pleoape": ("Machiaj", "Ochi"),
    "creion-ochi": ("Machiaj", "Ochi"),
    "sprancene": ("Machiaj", "Sprâncene"),
    "demachiant": ("Machiaj", "Demachiante"),
    "ser": ("Îngrijire ten", "Ser"),
    "crema-hidratanta": ("Îngrijire ten", "Cremă hidratantă"),
    "crema-ochi": ("Îngrijire ten", "Îngrijire contur ochi"),
    "toner": ("Îngrijire ten", "Toner"),
    "exfoliant": ("Îngrijire ten", "Scrub & exfoliant"),
    "masca": ("Îngrijire ten", "Mască"),
    "ulei-buze": ("Îngrijire ten", "Îngrijire buze"),
    "protectie-solara": ("Îngrijire ten", "Protecție solară"),
    "ulei-corp": ("Baie și corp", "Ulei de corp"),
    "parfum": ("Parfumuri", None),
    # Fără subcategorie de păr mai specifică în vechea listă — pusă temporar
    # pe Șampon; Deea o poate reasigna pe orice produs, din admin, oricând.
    "ingrijire-par": ("Păr", "Șampon"),
    "altele": ("Altele", None),
}


def semeaza_si_remapeaza(apps, schema_editor):
    Categorie = apps.get_model("reviews", "Categorie")
    Product = apps.get_model("reviews", "Product")

    grupuri = {}
    frunze = {}  # (grup_nume, subcat_nume_sau_None) -> instanță Categorie

    # TAXONOMIE listează mereu rândul grupului (subcat_nume=None) înaintea
    # subcategoriilor lui, deci `grupuri[grup_nume]` există deja când e nevoie.
    for grup_nume, subcat_nume, ordine in TAXONOMIE:
        if subcat_nume is None:
            grupuri[grup_nume] = Categorie.objects.create(
                nume=grup_nume, slug=slugify(grup_nume)[:70], ordine=ordine,
            )
            frunze[(grup_nume, None)] = grupuri[grup_nume]
        else:
            sub = Categorie.objects.create(
                nume=subcat_nume, slug=slugify(subcat_nume)[:70],
                grup=grupuri[grup_nume], ordine=ordine,
            )
            frunze[(grup_nume, subcat_nume)] = sub

    for produs in Product.objects.all():
        tinta = MAPARE_VECHI_NOU.get(produs.categorie)
        if tinta:
            produs.categorie_noua = frunze[tinta]
            produs.save(update_fields=["categorie_noua"])


def noop_inapoi(apps, schema_editor):
    # Ireversibil cu adevărat (am pierde maparea), dar nu blocăm `migrate`
    # înapoi — RemoveField-ul din migrarea următoare oricum șterge coloana.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0014_categorie"),
    ]

    operations = [
        migrations.RunPython(semeaza_si_remapeaza, noop_inapoi),
    ]
