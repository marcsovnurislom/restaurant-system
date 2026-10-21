from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.tables.models import Table
from apps.tables.services import table_regenerate_qr


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("number", "zone", "capacity", "is_active", "qr_link")
    list_editable = ("capacity", "is_active")
    list_filter = ("zone", "is_active")
    readonly_fields = ("qr_token", "qr_link")
    actions = ("regenerate_qr",)

    @admin.display(description="QR-код")
    def qr_link(self, obj: Table) -> str:
        if not obj.pk:
            return "—"
        url = reverse("tables:table-qr", kwargs={"pk": obj.pk})
        return format_html('<a href="{}" target="_blank">Открыть PNG</a>', url)

    @admin.action(description="Перевыпустить QR-коды")
    def regenerate_qr(self, request, queryset):
        for table in queryset:
            table_regenerate_qr(table)
        self.message_user(request, f"Перевыпущено QR-кодов: {queryset.count()}")
