from django.contrib import admin

from .models import Comment, ContactMessage, Product


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ("nume", "nota", "comentariu", "aprobat", "data")
    readonly_fields = ("data",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("nume", "brand", "categorie", "nota_mea", "data_postarii")
    list_filter = ("categorie", "nota_mea")
    search_fields = ("nume", "brand", "nuanta")
    prepopulated_fields = {"slug": ("brand", "nume")}
    inlines = [CommentInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("product", "nume", "nota", "aprobat", "data")
    list_filter = ("aprobat", "nota")
    search_fields = ("nume", "comentariu")
    autocomplete_fields = ["product"]


admin.site.site_header = "Glow Diary by Deea"
admin.site.site_title = "Glow Diary admin"
admin.site.index_title = "Administrare recenzii"


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("nume", "email", "citit", "data")
    list_filter = ("citit",)
    search_fields = ("nume", "email", "mesaj")
