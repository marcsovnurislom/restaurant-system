from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from apps.menu.models import Category, Dish, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "position", "is_active", "dish_count")
    list_editable = ("position", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_dish_count=Count("dishes"))

    @admin.display(description="блюд", ordering="_dish_count")
    def dish_count(self, obj: Category) -> int:
        return obj._dish_count


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("image_preview", "name", "category", "price", "is_available")
    list_display_links = ("image_preview", "name")
    list_editable = ("price", "is_available")
    list_filter = ("is_available", "category", "tags")
    list_select_related = ("category",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("tags",)
    readonly_fields = ("image_preview", "created_at", "updated_at")
    actions = ("put_on_stop_list", "remove_from_stop_list")

    @admin.display(description="фото")
    def image_preview(self, obj: Dish) -> str:
        if not obj.image:
            return "—"
        return format_html(
            '<img src="{}" style="height:48px;width:48px;object-fit:cover;border-radius:6px">',
            obj.image.url,
        )

    @admin.action(description="Поставить в стоп-лист")
    def put_on_stop_list(self, request, queryset):
        updated = queryset.update(is_available=False)
        self.message_user(request, f"В стоп-лист: {updated}")

    @admin.action(description="Вернуть в меню")
    def remove_from_stop_list(self, request, queryset):
        updated = queryset.update(is_available=True)
        self.message_user(request, f"Возвращено в меню: {updated}")
