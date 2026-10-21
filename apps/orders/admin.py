from django.contrib import admin

from apps.orders.models import Order, OrderItem, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("dish_name", "unit_price", "quantity")
    readonly_fields = fields
    can_delete = False


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    fields = ("from_status", "to_status", "changed_by", "changed_at")
    readonly_fields = fields
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Только просмотр: статусы меняются через API и экран кухни, где работают правила."""

    list_display = ("id", "created_at", "type", "status", "payment_status", "total", "phone")
    list_filter = ("status", "type", "payment_status", "payment_method")
    search_fields = ("id", "customer_name", "phone")
    date_hierarchy = "created_at"
    list_select_related = ("table",)
    inlines = (OrderItemInline, OrderStatusHistoryInline)
    readonly_fields = [field.name for field in Order._meta.fields]

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
