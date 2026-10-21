from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Category(models.Model):
    name = models.CharField("название", max_length=100)
    slug = models.SlugField("slug", max_length=100, unique=True)
    position = models.PositiveSmallIntegerField("порядок", default=0)
    is_active = models.BooleanField("показывать в меню", default=True)

    class Meta:
        verbose_name = "категория"
        verbose_name_plural = "категории"
        ordering = ("position", "name")

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    name = models.CharField("название", max_length=50, unique=True)
    slug = models.SlugField("slug", max_length=50, unique=True)

    class Meta:
        verbose_name = "тег"
        verbose_name_plural = "теги"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class DishQuerySet(models.QuerySet):
    def available(self) -> "DishQuerySet":
        """Блюда, которые гость может заказать прямо сейчас."""
        return self.filter(is_available=True, category__is_active=True)

    def with_relations(self) -> "DishQuerySet":
        return self.select_related("category").prefetch_related("tags")


class Dish(models.Model):
    category = models.ForeignKey(
        Category,
        verbose_name="категория",
        on_delete=models.PROTECT,
        related_name="dishes",
    )
    name = models.CharField("название", max_length=150)
    slug = models.SlugField("slug", max_length=150, unique=True)
    description = models.TextField("описание", blank=True)
    price = models.DecimalField(
        "цена, сум",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    weight_g = models.PositiveIntegerField("вес, г", null=True, blank=True)
    image = models.ImageField("фото", upload_to="dishes/%Y/%m/", blank=True)
    tags = models.ManyToManyField(Tag, verbose_name="теги", related_name="dishes", blank=True)
    is_available = models.BooleanField(
        "в наличии",
        default=True,
        help_text="Сними галочку, чтобы поставить блюдо в стоп-лист",
    )
    created_at = models.DateTimeField("создано", auto_now_add=True)
    updated_at = models.DateTimeField("изменено", auto_now=True)

    objects = DishQuerySet.as_manager()

    class Meta:
        verbose_name = "блюдо"
        verbose_name_plural = "блюда"
        ordering = ("name",)
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name="dish_price_positive"),
        ]
        indexes = [
            # Основной запрос меню: доступные блюда внутри категории
            models.Index(fields=["category", "is_available"], name="dish_category_available_idx"),
        ]

    def __str__(self) -> str:
        return self.name
