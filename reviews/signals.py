from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Product


@receiver([post_save, post_delete], sender=Product)
def invalideaza_feed_stats(sender, **kwargs):
    """Fără asta, badge-ul de pe Acasă, categoriile active din filtru și
    lista de surse rămâneau stale până la 5 minute după ce Deea adaugă,
    editează sau șterge un produs din admin (vezi FEED_STATS_CACHE_TTL)."""
    cache.delete("feed-stats")
