"""Views împărțite pe fișiere după zona funcțională (feed, produs, colecții,
API JSON, pagini statice) — reexportate aici ca `reviews.urls` și
`CSRF_FAILURE_VIEW` din settings să continue să le găsească la `reviews.views.X`,
neschimbat."""

from .api import FavoritesDataView, SearchDataView
from .collections import CollectionDetailView, CollectionListView
from .feed import FeedView
from .product import ProductDetailView, ProductStoryImageView
from .recap import AnRecapView
from .static_pages import AboutView, ContactView, FavoritesView, csrf_failure

__all__ = [
    "AboutView",
    "AnRecapView",
    "CollectionDetailView",
    "CollectionListView",
    "ContactView",
    "FavoritesDataView",
    "FavoritesView",
    "FeedView",
    "ProductDetailView",
    "ProductStoryImageView",
    "SearchDataView",
    "csrf_failure",
]
