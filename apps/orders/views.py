from decimal import Decimal
from uuid import UUID

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from apps.menu.models import Dish
from apps.menu.views import TABLE_SESSION_KEY
from apps.orders.cart import Cart
from apps.orders.forms import CheckoutForm
from apps.orders.models import MAX_QUANTITY, Order
from apps.orders.rules import DELIVERY_FEE, FREE_DELIVERY_FROM, MIN_DELIVERY_ORDER, OrderError
from apps.orders.selectors import order_queryset
from apps.orders.services import order_cancel_by_customer, order_create
from apps.payments.services import PaymentError, payment_start
from apps.tables.models import Table


@require_GET
def cart_view(request: HttpRequest) -> HttpResponse:
    _warn_about_unavailable(request, Cart(request.session))
    table = _session_table(request)
    form = CheckoutForm(has_table=table is not None, initial=_initial_for(request))
    return _render_cart(request, form, table)


@require_POST
def cart_add(request: HttpRequest, slug: str) -> HttpResponse:
    dish = get_object_or_404(Dish.objects.available(), slug=slug)
    Cart(request.session).add(dish, _quantity_from(request, default=1))
    messages.success(request, f"«{dish.name}» в корзине")
    return _redirect_back(request)


@require_POST
def cart_update(request: HttpRequest, slug: str) -> HttpResponse:
    # Без фильтра по наличию: убрать из корзины можно и блюдо из стоп-листа
    dish = get_object_or_404(Dish, slug=slug)
    Cart(request.session).set(dish, _quantity_from(request, default=0))
    return redirect("orders:cart")


@require_POST
def checkout(request: HttpRequest) -> HttpResponse:
    cart = Cart(request.session)
    # Блюдо закончилось, пока гость заполнял форму: сумма изменилась, пусть проверит заказ
    if _warn_about_unavailable(request, cart):
        return redirect("orders:cart")
    table = _session_table(request)
    form = CheckoutForm(request.POST, has_table=table is not None)
    if not form.is_valid():
        return _render_cart(request, form, table)

    data = form.cleaned_data
    try:
        order = order_create(
            items=cart.as_order_items(),
            order_type=data["type"],
            customer_name=data["customer_name"],
            phone=data["phone"],
            payment_method=data["payment_method"],
            address=data["address"],
            comment=data["comment"],
            table=table,
            user=request.user if request.user.is_authenticated else None,
        )
    except OrderError as exc:
        form.add_error(None, exc.message)
        return _render_cart(request, form, table)

    cart.clear()
    if order.payment_method == Order.PaymentMethod.ONLINE:
        return _start_payment(request, order)
    messages.success(request, "Заказ принят! Мы скоро его подтвердим.")
    return redirect("orders:detail", token=order.token)


@require_GET
def order_detail(request: HttpRequest, token: UUID) -> HttpResponse:
    order = get_object_or_404(order_queryset(), token=token)
    return render(request, "orders/detail.html", {"order": order})


@require_POST
def order_cancel(request: HttpRequest, token: UUID) -> HttpResponse:
    order = get_object_or_404(Order, token=token)
    try:
        order_cancel_by_customer(order=order)
    except OrderError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(request, "Заказ отменён.")
    return redirect("orders:detail", token=token)


@require_POST
def order_pay(request: HttpRequest, token: UUID) -> HttpResponse:
    return _start_payment(request, get_object_or_404(Order, token=token))


def _start_payment(request: HttpRequest, order: Order) -> HttpResponse:
    try:
        session = payment_start(order=order)
    except PaymentError as exc:
        messages.error(request, exc.message)
        return redirect("orders:detail", token=order.token)
    return redirect(session.redirect_url)


def _render_cart(request: HttpRequest, form: CheckoutForm, table: Table | None) -> HttpResponse:
    lines = Cart(request.session).lines()
    items_total = sum((line.total for line in lines), Decimal("0"))
    context = {
        "lines": lines,
        "items_total": items_total,
        "form": form,
        "table": table,
        "max_quantity": MAX_QUANTITY,
        "delivery_fee": DELIVERY_FEE,
        "free_delivery_from": FREE_DELIVERY_FROM,
        "min_delivery_order": MIN_DELIVERY_ORDER,
    }
    return render(request, "orders/cart.html", context)


def _warn_about_unavailable(request: HttpRequest, cart: Cart) -> bool:
    removed = cart.remove_unavailable()
    if removed:
        messages.warning(
            request, f"Эти блюда закончились и убраны из корзины: {', '.join(removed)}."
        )
    return bool(removed)


def _session_table(request: HttpRequest) -> Table | None:
    table_id = request.session.get(TABLE_SESSION_KEY)
    if table_id is None:
        return None
    return Table.objects.filter(pk=table_id, is_active=True).first()


def _initial_for(request: HttpRequest) -> dict:
    user = request.user
    if not user.is_authenticated:
        return {}
    return {"customer_name": user.get_full_name() or user.username, "phone": user.phone}


def _quantity_from(request: HttpRequest, *, default: int) -> int:
    try:
        return max(0, min(int(request.POST.get("quantity", default)), MAX_QUANTITY))
    except (TypeError, ValueError):
        return default


def _redirect_back(request: HttpRequest) -> HttpResponse:
    """Возврат на страницу, откуда добавили блюдо. Только на свой сайт: защита от open redirect."""
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("orders:cart")
