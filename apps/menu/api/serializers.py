from rest_framework import serializers

from apps.menu.models import Category, Dish, Tag


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "position", "is_active")


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name", "slug")


class DishSerializer(serializers.ModelSerializer):
    # Связи по slug: в запросе пишут "category": "supy", а не непонятный id
    category = serializers.SlugRelatedField(slug_field="slug", queryset=Category.objects.all())
    category_name = serializers.CharField(source="category.name", read_only=True)
    tags = serializers.SlugRelatedField(
        slug_field="slug", queryset=Tag.objects.all(), many=True, required=False
    )

    class Meta:
        model = Dish
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "price",
            "weight_g",
            "image",
            "category",
            "category_name",
            "tags",
            "is_available",
            "updated_at",
        )
        read_only_fields = ("id", "updated_at")


class RequiredBooleanField(serializers.BooleanField):
    """BooleanField, который в form-data не превращает отсутствие поля в False.

    Стандартный BooleanField работает как HTML-чекбокс: нет поля — значит False.
    Для стоп-листа это опасно: пустой PATCH молча убрал бы блюдо из меню.
    """

    default_empty_html = serializers.empty


class DishAvailabilitySerializer(serializers.Serializer):
    is_available = RequiredBooleanField()
