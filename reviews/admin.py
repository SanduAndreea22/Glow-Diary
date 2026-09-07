from django.contrib import admin

from .models import Collection, Comment, ContactMessage, Product, ProductImage


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ("nume", "nota", "comentariu", "aprobat", "data")
    readonly_fields = ("data",)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("imagine", "ordine")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("nume", "brand", "categorie", "nota_mea", "data_postarii")
    list_filter = ("categorie", "nota_mea")
    search_fields = ("nume", "brand", "nuanta")
    prepopulated_fields = {"slug": ("brand", "nume")}
    inlines = [ProductImageInline, CommentInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("product", "nume", "nota", "aprobat", "data")
    list_filter = ("aprobat", "nota")
    search_fields = ("nume", "comentariu")
    autocomplete_fields = ["product"]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("nume", "data_creare")
    prepopulated_fields = {"slug": ("nume",)}
    filter_horizontal = ("produse",)
    search_fields = ("nume", "descriere")


admin.site.site_header = "Glow Diary by Deea"
admin.site.site_title = "Glow Diary admin"
admin.site.index_title = "Administrare recenzii"


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("nume", "email", "citit", "data")
    list_filter = ("citit",)
    search_fields = ("nume", "email", "mesaj")
