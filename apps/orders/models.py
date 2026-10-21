import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.menu.models import Dish
from apps.tables.models import Table
from apps.users.validators import phone_validator

MAX_QUANTITY = 20


class Order(models.Model):
    class Type(models.TextChoices):
        DELIVERY = "delivery", "Доставка"
        PICKUP = "pickup", "Самовывоз"
        DINE_IN = "dine_in", "В зале"

    class Status(models.TextChoices):
        NEW = "new", "Новый"
        CONFIRMED = "confirmed", "Подтверждён"
        COOKING = "cooking", "Готовится"
        READY = "ready", "Готов"
        DELIVERING = "delivering", "В пути"
        COMPLETED = "completed", "Выполнен"
        CANCELLED = "cancelled", "Отменён"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Наличными или картой при получении"
        ONLINE = "online", "Онлайн картой"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Не оплачен"
        PAID = "paid", "Оплачен"

    # Токен для страницы заказа: гость без аккаунта видит статус и может оплатить
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="пользователь",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    table = models.ForeignKey(
        Table,
        verbose_name="стол",
        # PROTECT, а не SET_NULL: иначе удаление стола нарушило бы order_dine_in_has_table
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
    )
    type = models.CharField("тип", max_length=20, choices=Type.choices)
    status = models.CharField("статус", max_length=20, choices=Status.choices, default=Status.NEW)
    payment_method = models.CharField("способ оплаты", max_length=20, choices=PaymentMethod.choices)
    payment_status = models.CharField(
        "оплата", max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    customer_name = models.CharField("имя", max_length=100)
    phone = models.CharField("телефон", max_length=20, validators=[phone_validator])
    address = models.CharField("адрес доставки", max_length=255, blank=True)
    comment = models.TextField("комментарий", max_length=500, blank=True)
    items_total = models.DecimalField("сумма блюд", max_digits=12, decimal_places=2)
    delivery_fee = models.DecimalField(
        "доставка", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    total = models.DecimalField("итого", max_digits=12, decimal_places=2)
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        verbose_name = "заказ"
        verbose_name_plural = "заказы"
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(type="delivery") | ~Q(address=""),
                name="order_delivery_has_address",
            ),
            models.CheckConstraint(
                condition=~Q(type="dine_in") | Q(table__isnull=False),
                name="order_dine_in_has_table",
            ),
            models.CheckConstraint(
                condition=Q(total=F("items_total") + F("delivery_fee")),
                name="order_total_is_sum",
            ),
            models.CheckConstraint(condition=Q(items_total__gt=0), name="order_not_empty"),
        ]
        indexes = [
            models.Index(fields=["status", "created_at"], name="order_status_created_idx"),
        ]

    def __str__(self) -> str:
        return f"Заказ №{self.pk}"

    @property
    def awaits_online_payment(self) -> bool:
        return (
            self.payment_method == self.PaymentMethod.ONLINE
            and self.payment_status == self.PaymentStatus.UNPAID
            and self.status == self.Status.NEW
        )


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    # PROTECT: блюдо из истории заказов нельзя удалить, только поставить в стоп-лист
    dish = models.ForeignKey(Dish, on_delete=models.PROTECT, related_name="order_items")
    # Снимок на момент заказа: если блюдо переименуют или изменят цену, старый заказ не изменится
    dish_name = models.CharField("блюдо", max_length=150)
    unit_price = models.DecimalField("цена", max_digits=12, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(
        "количество", validators=[MinValueValidator(1), MaxValueValidator(MAX_QUANTITY)]
    )

    class Meta:
        verbose_name = "позиция заказа"
        verbose_name_plural = "позиции заказа"
        constraints = [
            models.UniqueConstraint(fields=["order", "dish"], name="order_item_unique_dish"),
            models.CheckConstraint(
                condition=Q(quantity__gte=1) & Q(quantity__lte=MAX_QUANTITY),
                name="order_item_quantity_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.dish_name} × {self.quantity}"

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField("было", max_length=20, blank=True)
    to_status = models.CharField("стало", max_length=20, choices=Order.Status.choices)
    # null — изменение сделала система (например, после онлайн-оплаты) или гость без аккаунта
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    changed_at = models.DateTimeField("когда", auto_now_add=True)

    class Meta:
        verbose_name = "смена статуса"
        verbose_name_plural = "история статусов"
        ordering = ("changed_at", "pk")

    def __str__(self) -> str:
        return f"{self.from_status or '—'} → {self.to_status}"
