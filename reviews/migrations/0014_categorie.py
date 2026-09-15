import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0013_alter_product_categorie"),
    ]

    operations = [
        migrations.CreateModel(
            name="Categorie",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nume", models.CharField(max_length=60, verbose_name="Nume")),
                ("slug", models.SlugField(blank=True, max_length=70, unique=True)),
                ("ordine", models.PositiveSmallIntegerField(
                    default=0,
                    help_text="Ordinea de afișare (crescător) — între grupuri, sau între subcategoriile aceluiași grup.",
                    verbose_name="Ordine",
                )),
                ("grup", models.ForeignKey(
                    blank=True, null=True,
                    help_text="Lasă gol dacă asta e un grup de nivel 1 (ex. „Machiaj”).",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="subcategorii", to="reviews.categorie",
                    verbose_name="Grup",
                )),
            ],
            options={
                "verbose_name": "Categorie",
                "verbose_name_plural": "Categorii",
                "ordering": ["ordine", "nume"],
            },
        ),
        migrations.AddField(
            model_name="product",
            name="categorie_noua",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="produse", to="reviews.categorie",
                verbose_name="Categorie",
            ),
        ),
    ]
