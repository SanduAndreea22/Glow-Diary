from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Comment, Product


@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=Comment)
def invalideaza_feed_stats(sender, **kwargs):
    """Fără asta, badge-ul de pe Acasă, categoriile active din filtru și
    lista de surse rămâneau stale până la 5 minute după ce Deea adaugă,
    editează sau șterge un produs din admin (vezi FEED_STATS_CACHE_TTL).
    Ascultă și pe Comment — `produsul_lunii()` depinde de numărul de
    comentarii din ultimele 30 de zile, deci un comentariu nou/șters
    (aprobat sau nu, ambele pot schimba rezultatul) trebuie să invalideze
    la fel de bine sigiliul "PRODUSUL LUNII" din feed-stats."""
    cache.delete("feed-stats")
