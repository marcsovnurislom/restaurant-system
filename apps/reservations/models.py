import uuid
from datetime import datetime

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.tables.models import Table
from apps.users.validators import phone_validator


class ReservationQuerySet(models.QuerySet):
    def active(self) -> "ReservationQuerySet":
        """Брони, которые занимают стол."""
        return self.filter(status=Reservation.Status.CONFIRMED)

    def overlapping(self, start_at: datetime, end_at: datetime) -> "ReservationQuerySet":
        """Пересекаются с интервалом [start_at, end_at).

        Брони «впритык» (одна кончается в 19:00, другая начинается в 19:00) не пересекаются.
        """
        return self.filter(start_at__lt=end_at, end_at__gt=start_at)


class Reservation(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Подтверждена"
        COMPLETED = "completed", "Гость пришёл"
        NO_SHOW = "no_show", "Гость не пришёл"
        CANCELLED = "cancelled", "Отменена"

    # Токен для ссылки на бронь: гость без аккаунта может посмотреть и отменить её
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="пользователь",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    table = models.ForeignKey(
        Table, verbose_name="стол", on_delete=models.PROTECT, related_name="reservations"
    )
    guest_name = models.CharField("имя гостя", max_length=100)
    phone = models.CharField("телефон", max_length=20, validators=[phone_validator])
    email = models.EmailField("email", blank=True)
    guests_count = models.PositiveSmallIntegerField(
        "гостей", validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    start_at = models.DateTimeField("начало")
    end_at = models.DateTimeField("конец")
    status = models.CharField(
        "статус", max_length=20, choices=Status.choices, default=Status.CONFIRMED
    )
    comment = models.TextField("комментарий", max_length=500, blank=True)
    created_at = models.DateTimeField("создана", auto_now_add=True)
    cancelled_at = models.DateTimeField("отменена", null=True, blank=True)
    reminder_sent_at = models.DateTimeField("напоминание отправлено", null=True, blank=True)

    objects = ReservationQuerySet.as_manager()

    class Meta:
        verbose_name = "бронь"
        verbose_name_plural = "брони"
        ordering = ("start_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=F("start_at")), name="reservation_end_after_start"
            ),
            models.CheckConstraint(
                condition=Q(guests_count__gte=1) & Q(guests_count__lte=20),
                name="reservation_guests_range",
            ),
            # Запрет пересечения броней одного стола — ExclusionConstraint в миграции 0002
        ]
        indexes = [
            models.Index(fields=["table", "start_at"], name="reservation_table_start_idx"),
            models.Index(fields=["status", "start_at"], name="reservation_status_start_idx"),
        ]

    def __str__(self) -> str:
        local = timezone.localtime(self.start_at)
        return f"{self.guest_name}, {local:%d.%m %H:%M}, стол №{self.table.number}"

    @property
    def is_cancellable(self) -> bool:
        return self.status == self.Status.CONFIRMED and self.start_at > timezone.now()
