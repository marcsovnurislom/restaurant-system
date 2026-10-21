from django_filters import rest_framework as filters

from apps.menu.models import Dish


class DishFilter(filters.FilterSet):
    """?category=supy&tag=ostroe&price_min=20000&price_max=60000"""

    category = filters.CharFilter(field_name="category__slug")
    # distinct: без него JOIN по тегам может вернуть одно блюдо дважды
    tag = filters.CharFilter(field_name="tags__slug", distinct=True)
    price_min = filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = filters.NumberFilter(field_name="price", lookup_expr="lte")

    class Meta:
        model = Dish
        fields = ("category", "tag", "price_min", "price_max", "is_available")
