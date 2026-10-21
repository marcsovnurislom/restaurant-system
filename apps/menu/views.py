from uuid import UUID

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.menu.selectors import dish_list, menu_by_category, tag_list
from apps.tables.models import Table

FEATURED_TAG = "hit"
FEATURED_LIMIT = 6
# Ключ сессии со столом, за которым сидит гость (на этапе 4 к нему привяжется заказ)
TABLE_SESSION_KEY = "table_id"


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    featured = list(dish_list().filter(tags__slug=FEATURED_TAG).distinct()[:FEATURED_LIMIT])
    if not featured:
        featured = list(dish_list()[:FEATURED_LIMIT])
    return render(request, "menu/home.html", {"featured": featured})


@require_GET
def menu_list(request: HttpRequest) -> HttpResponse:
    return _render_menu(request)


@require_GET
def table_menu(request: HttpRequest, token: UUID) -> HttpResponse:
    """Меню, открытое по QR-коду со стола."""
    table = get_object_or_404(Table, qr_token=token, is_active=True)
    request.session[TABLE_SESSION_KEY] = table.pk
    return _render_menu(request, table=table)


@require_GET
def dish_detail(request: HttpRequest, slug: str) -> HttpResponse:
    dish = get_object_or_404(dish_list(), slug=slug)
    return render(request, "menu/dish_detail.html", {"dish": dish})


def _render_menu(request: HttpRequest, table: Table | None = None) -> HttpResponse:
    active_tag = request.GET.get("tag") or None
    context = {
        "categories": menu_by_category(tag_slug=active_tag),
        "tags": tag_list(),
        "active_tag": active_tag,
        "table": table,
    }
    return render(request, "menu/menu_list.html", context)
