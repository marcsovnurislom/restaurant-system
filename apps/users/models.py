from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.users.managers import UserManager
from apps.users.validators import phone_validator


class User(AbstractUser):
    """Пользователь системы: гость или сотрудник ресторана.

    Роль хранится одним полем, а не через Django Groups: у сотрудника
    ровно одна должность, и проверка `user.role` не требует JOIN.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Администратор"
        MANAGER = "manager", "Менеджер"
        WAITER = "waiter", "Официант"
        COOK = "cook", "Повар"
        COURIER = "courier", "Курьер"
        CUSTOMER = "customer", "Гость"

    STAFF_ROLES = frozenset({Role.ADMIN, Role.MANAGER, Role.WAITER, Role.COOK, Role.COURIER})

    email = models.EmailField("email", unique=True)
    phone = models.CharField("телефон", max_length=20, blank=True, validators=[phone_validator])
    role = models.CharField(
        "роль",
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        db_index=True,
    )

    objects = UserManager()

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
        ordering = ("-date_joined",)

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"

    def has_role(self, *roles: str) -> bool:
        """Администратор и суперпользователь проходят любую проверку роли."""
        if self.is_superuser or self.role == self.Role.ADMIN:
            return True
        return self.role in roles

    @property
    def is_staff_member(self) -> bool:
        return self.is_superuser or self.role in self.STAFF_ROLES
