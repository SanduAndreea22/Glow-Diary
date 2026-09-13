from django.conf import settings
from django.core.checks import Error, register


@register()
def verifica_fonturile_story(app_configs, **kwargs):
    """Fără fonturile bundle-uite, imaginile de Story (vezi story_image.py)
    se randează silențios cu fontul implicit PIL — urât, neconform brandului
    — și singurul semnal ar fi un logger.warning pe care nimeni nu-l
    citește garantat. Mai bine un `manage.py check` care eșuează vizibil
    la un deploy cu fonturi lipsă."""
    erori = []
    for nume_fisier in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        cale = settings.BASE_DIR / "static" / "fonts" / nume_fisier
        if not cale.is_file():
            erori.append(
                Error(
                    f"Fontul lipsește: {cale}",
                    hint=(
                        "Imaginile de Story (Descarcă pentru Story) vor folosi "
                        "un font implicit, neconform brandului, în loc de acesta."
                    ),
                    id="reviews.E001",
                )
            )
    return erori
