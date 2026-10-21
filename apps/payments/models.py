from django.db import models
from django.db.models import Q

from apps.orders.models import Order


class Payment(models.Model):
    """Попытка онлайн-оплаты. У заказа может быть несколько: гость закрыл окно и начал заново."""

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает оплаты"
        SUCCEEDED = "succeeded", "Оплачен"
        FAILED = "failed", "Не прошёл"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField("провайдер", max_length=20)
    # id сессии у провайдера. NULL, а не "", пока провайдер не ответил:
    # несколько NULL не нарушают уникальность, а несколько "" — нарушили бы
    external_id = models.CharField(  # noqa: DJ001
        "id у провайдера", max_length=255, null=True, blank=True
    )
    amount = models.DecimalField("сумма", max_digits=12, decimal_places=2)
    status = models.CharField(
        "статус", max_length=20, choices=Status.choices, default=Status.PENDING
    )
    raw_payload = models.JSONField("данные webhook", default=dict, blank=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("изменён", auto_now=True)

    class Meta:
        verbose_name = "платёж"
        verbose_name_plural = "платежи"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_id"],
                condition=Q(external_id__isnull=False),
                name="payment_unique_external_id",
            ),
        ]

    def __str__(self) -> str:
        return f"Платёж {self.pk} ({self.provider}) за заказ №{self.order_id}"
