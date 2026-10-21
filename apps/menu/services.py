import logging

from apps.menu.models import Dish

logger = logging.getLogger(__name__)


def dish_set_availability(*, dish: Dish, is_available: bool) -> Dish:
    """Ставит блюдо в стоп-лист или возвращает в меню (делает повар или менеджер)."""
    if dish.is_available == is_available:
        return dish

    dish.is_available = is_available
    dish.save(update_fields=["is_available", "updated_at"])
    logger.info(
        "Блюдо %s %s", dish.slug, "вернули в меню" if is_available else "поставили в стоп-лист"
    )
    return dish
