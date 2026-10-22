from collections.abc import Callable
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.kitchen.payloads import active_orders, kitchen_payload
from apps.orders.models import Order


def staff_required(view: Callable) -> Callable:
    """Неавторизованных отправляет на вход, гостей с аккаунтом — на 403."""

    @wraps(view)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff_member:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


@require_GET
@staff_required
def board(request: HttpRequest) -> HttpResponse:
    context = {
        "orders": _serialized_active_orders(),
        "role": "admin" if request.user.is_superuser else request.user.role,
        "columns": [
            (Order.Status.NEW, "Новые"),
            (Order.Status.CONFIRMED, "К приготовлению"),
            (Order.Status.COOKING, "Готовятся"),
            (Order.Status.READY, "Готовы"),
            (Order.Status.DELIVERING, "В пути"),
        ],
    }
    return render(request, "kitchen/board.html", context)


@require_GET
@staff_required
def snapshot(request: HttpRequest) -> JsonResponse:
    """Все активные заказы. Экран запрашивает их после переподключения сокета,
    чтобы не потерять события, пришедшие, пока связи не было."""
    return JsonResponse({"orders": _serialized_active_orders()})


def _serialized_active_orders() -> list[dict]:
    return [kitchen_payload(order) for order in active_orders()]
