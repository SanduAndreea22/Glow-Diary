from django.db import migrations

# Set standard, editabil oricând din admin — pornim de la o listă uzuală de
# beauty (tip de ten + atribute frecvent căutate), nu de la una exhaustivă;
# Deea adaugă altele pe măsură ce simte nevoia, direct din admin → Tag-uri.
TAG_URI_STANDARD = [
    "Ten gras",
    "Ten uscat",
    "Ten mixt",
    "Ten sensibil",
    "Vegan",
    "Cruelty-free",
    "Fără parabeni",
    "Rezistent la apă",
    "Cu SPF",
]


def seed_tag_uri(apps, schema_editor):
    Tag = apps.get_model("reviews", "Tag")
    from django.utils.text import slugify

    for nume in TAG_URI_STANDARD:
        Tag.objects.get_or_create(nume=nume, defaults={"slug": slugify(nume)[:50]})


def elimina_tag_uri_seed(apps, schema_editor):
    Tag = apps.get_model("reviews", "Tag")
    Tag.objects.filter(nume__in=TAG_URI_STANDARD).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0007_tag_comment_imagine_product_il_recumpar_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_tag_uri, elimina_tag_uri_seed),
    ]
