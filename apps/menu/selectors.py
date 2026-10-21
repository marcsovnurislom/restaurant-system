"""Запросы на чтение меню. Все выборки здесь, чтобы views не плодили N+1."""

from django.db.models import Prefetch, QuerySet

from apps.menu.models import Category, Dish, Tag


def category_list(*, include_inactive: bool = False) -> QuerySet[Category]:
    categories = Category.objects.all()
    if not include_inactive:
        categories = categories.filter(is_active=True)
    return categories


def tag_list() -> QuerySet[Tag]:
    return Tag.objects.all()


def dish_list(*, include_unavailable: bool = False) -> QuerySet[Dish]:
    """Блюда для API. Гостям — только доступные, персоналу — все, включая стоп-лист."""
    dishes = Dish.objects.with_relations().order_by("category__position", "category__name", "name")
    if not include_unavailable:
        dishes = dishes.available()
    return dishes


def menu_by_category(*, tag_slug: str | None = None) -> list[Category]:
    """Меню для сайта: активные категории, у каждой атрибут `menu_dishes`.

    Ровно 3 запроса независимо от размера меню: категории, блюда, теги.
    Пустые категории (всё в стоп-листе или не подходит под фильтр) не показываются.
    """
    dishes = Dish.objects.filter(is_available=True).prefetch_related("tags").order_by("name")
    if tag_slug:
        dishes = dishes.filter(tags__slug=tag_slug)

    categories = category_list().prefetch_related(
        Prefetch("dishes", queryset=dishes, to_attr="menu_dishes"),
    )
    return [category for category in categories if category.menu_dishes]
