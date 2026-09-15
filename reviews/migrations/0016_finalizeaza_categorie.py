import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0015_migreaza_categorii"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="product",
            name="categorie",
        ),
        migrations.RenameField(
            model_name="product",
            old_name="categorie_noua",
            new_name="categorie",
        ),
        migrations.AlterField(
            model_name="product",
            name="categorie",
            field=models.ForeignKey(
                help_text="O subcategorie (ex. Machiaj → Buze), sau un grup fără subcategorii (ex. Parfumuri, Altele).",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="produse", to="reviews.categorie",
                verbose_name="Categorie",
            ),
        ),
    ]
