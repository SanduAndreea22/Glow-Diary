from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path

from .forms import CollectionAdminForm, ProductAdminForm, ProductBulkFormSet
from .models import Categorie, Collection, Comment, ContactMessage, Product, ProductImage, Tag


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ("nume", "nota", "comentariu", "imagine", "aprobat", "data")
    readonly_fields = ("data",)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("imagine", "ordine")


@admin.action(description="Restaurează (fă activ) produsele selectate")
def restaureaza_produse(modeladmin, request, queryset):
    updated = queryset.update(activ=True)
    messages.success(request, f"Restaurat(e) {updated} produs(e).")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = (
        "nume", "brand", "categorie", "nota_mea", "pret", "il_recumpar", "activ", "data_postarii",
    )
    list_select_related = ("categorie", "categorie__grup")
    list_filter = ("activ", "categorie__grup", "categorie", "nota_mea", "il_recumpar", "tag_uri")
    search_fields = ("nume", "brand", "nuanta")
    filter_horizontal = ("tag_uri",)
    inlines = [ProductImageInline, CommentInline]
    change_list_template = "admin/reviews/product/change_list.html"
    actions = ["delete_selected", restaureaza_produse]

    class Media:
        js = ("admin/reviews/product_categorie_cascade.js",)
    fieldsets = (
        (None, {
            "fields": (
                "nume", "brand", "grup", "categorie", "nuanta", "sursa", "poza", "slug",
            ),
        }),
        ("Verdict", {
            "fields": ("nota_mea", "parerea_mea", "pret", "il_recumpar", "tine_cat", "pentru_cine"),
        }),
        ("Filtrare", {"fields": ("tag_uri",)}),
        ("Vizibilitate", {"fields": ("activ",)}),
    )

    def get_prepopulated_fields(self, request, obj=None):
        # Doar la creare — altfel JS-ul de prepopulare rescrie slug-ul live
        # dacă Deea editează brand/nume la un produs existent, ceea ce ar
        # schimba URL-ul lui (linkuri deja distribuite s-ar rupe).
        return {} if obj else {"slug": ("brand", "nume")}

    def get_readonly_fields(self, request, obj=None):
        return ("slug",) if obj else ()

    def delete_queryset(self, request, queryset):
        # queryset.delete() ocolește Product.delete() (Django face un DELETE
        # SQL direct pentru eficiență) — fără asta, "Delete selected" din
        # bulk ar șterge cu adevărat produsele active dintr-o dată, în loc
        # să le ascundă prima dată, ca la ștergerea individuală.
        for obj in queryset:
            obj.delete()

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path(
                "bulk-add/",
                self.admin_site.admin_view(self.bulk_add_view),
                name="reviews_product_bulk_add",
            ),
        ]
        return extra + urls

    def bulk_add_view(self, request):
        # Un rând per produs, fără poză (aceea rămâne de adăugat individual
        # din pagina fiecărui produs) — gândit pentru a intra rapid text
        # pentru mai multe produse deodată, fără dus-întors prin changelist
        # ca la "Save and add another".
        if not self.has_add_permission(request):
            messages.error(request, "Nu ai permisiunea de a adăuga produse.")
            return redirect("admin:reviews_product_changelist")

        if request.method == "POST":
            formset = ProductBulkFormSet(request.POST, queryset=Product.objects.none())
            if formset.is_valid():
                create = [
                    form for form in formset.forms
                    if form.has_changed() and form.cleaned_data
                ]
                for form in create:
                    form.save()
                if create:
                    messages.success(
                        request,
                        f"Am adăugat {len(create)} produs(e). Nu uita să încarci poza "
                        "la fiecare, individual — bulk-add-ul nu include poze.",
                    )
                else:
                    messages.warning(request, "N-ai completat niciun rând — nimic de salvat.")
                return redirect("admin:reviews_product_changelist")
        else:
            formset = ProductBulkFormSet(queryset=Product.objects.none())

        context = {
            **self.admin_site.each_context(request),
            "title": "Adaugă mai multe produse",
            "formset": formset,
            "opts": self.model._meta,
        }
        return render(request, "admin/reviews/product/bulk_add.html", context)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("product", "nume", "nota", "are_poza", "aprobat", "data")
    list_filter = ("aprobat", "nota")
    search_fields = ("nume", "comentariu")
    autocomplete_fields = ["product"]

    @admin.display(description="Poză", boolean=True)
    def are_poza(self, obj):
        return bool(obj.imagine)


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("nume", "grup", "ordine")
    list_filter = ("grup",)
    search_fields = ("nume",)
    prepopulated_fields = {"slug": ("nume",)}
    autocomplete_fields = ["grup"]
    ordering = ["grup__ordine", "grup__nume", "ordine", "nume"]



@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("nume", "slug")
    search_fields = ("nume",)
    prepopulated_fields = {"slug": ("nume",)}


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    form = CollectionAdminForm
    list_display = ("nume", "recomandata_saptamana", "data_creare")
    list_editable = ("recomandata_saptamana",)
    filter_horizontal = ("produse",)
    search_fields = ("nume", "descriere")

    def get_prepopulated_fields(self, request, obj=None):
        return {} if obj else {"slug": ("nume",)}

    def get_readonly_fields(self, request, obj=None):
        return ("slug",) if obj else ()


admin.site.site_header = "Glow Diary by Deea"
admin.site.site_title = "Glow Diary admin"
admin.site.index_title = "Administrare recenzii"


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("nume", "email", "citit", "data")
    list_editable = ("citit",)
    list_filter = ("citit",)
    search_fields = ("nume", "email", "mesaj")
