from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("", views.FeedView.as_view(), name="feed"),
    path("produs/<slug:slug>/", views.ProductDetailView.as_view(), name="product_detail"),
    path("despre/", views.AboutView.as_view(), name="about"),
    path("contact/", views.ContactView.as_view(), name="contact"),
]
