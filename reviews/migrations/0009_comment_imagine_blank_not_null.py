from django.db import migrations, models


def normalizeaza_imagine_null(apps, schema_editor):
    """Convertește NULL în '' (șir gol) pe rândurile existente, înainte de
    a interzice NULL pe coloană — fără asta, ALTER TABLE de mai jos ar eșua
    pe orice comentariu existent fără poză."""
    Comment = apps.get_model("reviews", "Comment")
    Comment.objects.filter(imagine__isnull=True).update(imagine="")


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0008_seed_tag_uri_standard"),
    ]

    operations = [
        migrations.RunPython(normalizeaza_imagine_null, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="comment",
            name="imagine",
            field=models.ImageField(
                blank=True,
                help_text="O poză cu produsul la tine, dacă vrei să o arăți alături de părere.",
                upload_to="comentarii/",
                verbose_name="Poză (opțional)",
            ),
        ),
    ]
