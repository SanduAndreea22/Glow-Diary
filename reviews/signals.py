from django.core.cache import cache
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models import Categorie, Comment, Product, Tag


@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=Comment)
@receiver([post_save, post_delete], sender=Categorie)
@receiver([post_save, post_delete], sender=Tag)
@receiver(m2m_changed, sender=Product.tag_uri.through)
def invalideaza_feed_stats(sender, **kwargs):
    """Fără asta, badge-ul de pe Acasă, categoriile active din filtru și
    lista de surse rămâneau stale până la 5 minute după ce Deea adaugă,
    editează sau șterge un produs din admin (vezi FEED_STATS_CACHE_TTL).
    Ascultă și pe Comment — `produsul_lunii()` depinde de numărul de
    comentarii din ultimele 30 de zile, deci un comentariu nou/șters
    (aprobat sau nu, ambele pot schimba rezultatul) trebuie să invalideze
    la fel de bine sigiliul "PRODUSUL LUNII" din feed-stats.

    Categorie/Tag ascultate separat — redenumirea sau reordonarea unei
    categorii/tag din admin, fără să atingi niciun produs, altfel nu
    invalida cache-ul (categorii_navigare/tag_uri din feed-stats rămâneau
    cu numele/ordinea veche). m2m_changed pe Product.tag_uri — adăugarea/
    eliminarea unui tag de pe un produs trece prin save_m2m() în admin,
    separat de post_save al produsului, deci are nevoie de propriul semnal."""
    cache.delete("feed-stats")
