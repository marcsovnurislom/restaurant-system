from django.contrib import admin

from apps.reservations.models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("start_at", "table", "guest_name", "phone", "guests_count", "status")
    list_filter = ("status", "table__zone")
    list_select_related = ("table",)
    search_fields = ("guest_name", "phone", "email")
    date_hierarchy = "start_at"
    raw_id_fields = ("user",)
    readonly_fields = ("token", "created_at", "cancelled_at")
