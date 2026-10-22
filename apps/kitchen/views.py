from collections.abc import Callable
from functools import wraps

from django.conf import settings
from django.contrib.auth.views import LoginView, redirect_to_login
from django.core.cache import cache
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


class StaffLoginView(LoginView):
    """Вход персонала с ограничением неудачных попыток с одного IP.

    Счётчик лежит в общем кэше (Redis в продакшене), поэтому лимит общий
    для всех процессов сервера. Успешный вход сбрасывает счётчик.
    """

    template_name = "kitchen/login.html"
    redirect_authenticated_user = True
    locked_message = "Слишком много неудачных попыток. Попробуйте через 15 минут."

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if cache.get(self._key(), 0) >= settings.LOGIN_ATTEMPTS_LIMIT:
            # Пустая форма: пароль даже не проверяется, иначе authenticate()
            # всё равно работал бы и по времени ответа можно было бы подбирать пароль
            context = self.get_context_data(
                form=self.get_form_class()(request=request), lockout_message=self.locked_message
            )
            return self.render_to_response(context, status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = self._key()
        # add() создаёт счётчик с таймаутом, incr() увеличивает атомарно
        cache.add(key, 0, timeout=settings.LOGIN_LOCKOUT_SECONDS)
        cache.incr(key)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._key())
        return super().form_valid(form)

    def _key(self) -> str:
        # За прокси Daphne с --proxy-headers кладёт сюда реальный IP клиента
        return f"staff-login:{self.request.META.get('REMOTE_ADDR', '')}"


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
