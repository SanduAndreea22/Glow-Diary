from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("", views.FeedView.as_view(), name="feed"),
    path("produs/<slug:slug>/", views.ProductDetailView.as_view(), name="product_detail"),
    path("produs/<slug:slug>/story.png", views.product_story_image, name="product_story_image"),
    path("colectii/", views.CollectionListView.as_view(), name="collections"),
    path("colectii/<slug:slug>/", views.CollectionDetailView.as_view(), name="collection_detail"),
    path("favorite/", views.FavoritesView.as_view(), name="favorites"),
    path("api/favorite-data/", views.favorites_data, name="favorites_data"),
    path("api/search/", views.search_data, name="search_data"),
    path("despre/", views.AboutView.as_view(), name="about"),
    path("contact/", views.ContactView.as_view(), name="contact"),
]
