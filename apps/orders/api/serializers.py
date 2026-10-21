from rest_framework import serializers

from apps.menu.models import Dish
from apps.orders.models import MAX_QUANTITY, Order, OrderItem, OrderStatusHistory
from apps.orders.rules import allowed_transitions
from apps.tables.models import Table
from apps.users.validators import phone_validator


class OrderItemInputSerializer(serializers.Serializer):
    dish = serializers.SlugRelatedField(slug_field="slug", queryset=Dish.objects.all())
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY)


class OrderCreateSerializer(serializers.Serializer):
    """Заказ через API передаёт позиции в теле запроса — без серверной корзины.

    Цены клиент не присылает: их берёт сервис из БД.
    """

    type = serializers.ChoiceField(choices=Order.Type.choices)
    items = OrderItemInputSerializer(many=True, allow_empty=False)
    customer_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=20, validators=[phone_validator])
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    comment = serializers.CharField(max_length=500, required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices)
    table_token = serializers.UUIDField(
        required=False, help_text="Токен из QR-кода стола, для заказа в зале"
    )

    def validate_table_token(self, value) -> Table:
        table = Table.objects.filter(qr_token=value, is_active=True).first()
        if table is None:
            raise serializers.ValidationError("Стол не найден.")
        return table


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ("dish_name", "unit_price", "quantity", "line_total")


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusHistory
        fields = ("from_status", "to_status", "changed_at")


class OrderSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    table_number = serializers.IntegerField(source="table.number", read_only=True, default=None)
    items = OrderItemSerializer(many=True, read_only=True)
    history = OrderStatusHistorySerializer(many=True, read_only=True)
    next_statuses = serializers.SerializerMethodField(
        help_text="Куда можно перевести заказ (без учёта роли)"
    )

    class Meta:
        model = Order
        fields = (
            "id",
            "token",
            "type",
            "type_display",
            "status",
            "status_display",
            "payment_method",
            "payment_status",
            "customer_name",
            "phone",
            "address",
            "comment",
            "table_number",
            "items",
            "items_total",
            "delivery_fee",
            "total",
            "history",
            "next_statuses",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_next_statuses(self, obj: Order) -> list[str]:
        return allowed_transitions(obj)


class OrderTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
