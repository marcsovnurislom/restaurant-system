import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse


class Table(models.Model):
    class Zone(models.TextChoices):
        HALL = "hall", "Основной зал"
        TERRACE = "terrace", "Терраса"
        VIP = "vip", "VIP-комната"

    # Валидаторы дают понятную ошибку 400 в API и админке, constraint страхует на уровне БД
    number = models.PositiveSmallIntegerField(
        "номер", unique=True, validators=[MinValueValidator(1)]
    )
    capacity = models.PositiveSmallIntegerField(
        "мест", validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    zone = models.CharField("зона", max_length=20, choices=Zone.choices, default=Zone.HALL)
    # Случайный токен вместо номера в QR: по ссылке /t/5/ легко перебрать чужие столы
    qr_token = models.UUIDField("токен QR", default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField("работает", default=True)

    class Meta:
        verbose_name = "стол"
        verbose_name_plural = "столы"
        ordering = ("number",)
        constraints = [
            models.CheckConstraint(
                condition=Q(capacity__gte=1) & Q(capacity__lte=20),
                name="table_capacity_range",
            ),
        ]

    def __str__(self) -> str:
        return f"Стол №{self.number}"

    def get_absolute_url(self) -> str:
        return reverse("menu:table-menu", kwargs={"token": self.qr_token})
