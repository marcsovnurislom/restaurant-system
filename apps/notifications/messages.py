"""Тексты уведомлений. Всё, что ввёл гость, экранируется: parse_mode=HTML."""

from html import escape

from django.utils import timezone

from apps.menu.templatetags.money import money
from apps.orders.models import Order
from apps.reservations.models import Reservation


def new_order_text(order: Order) -> str:
    lines = [
        f"<b>Новый заказ №{order.pk}</b> · {escape(order.get_type_display())}",
        f"{escape(order.customer_name)}, {escape(order.phone)}",
    ]
    if order.table:
        lines.append(f"Стол №{order.table.number}")
    if order.address:
        lines.append(f"Адрес: {escape(order.address)}")
    lines.append("")
    lines += [f"{item.quantity}× {escape(item.dish_name)}" for item in order.items.all()]
    lines.append("")
    payment = (
        "оплачен онлайн" if order.payment_status == Order.PaymentStatus.PAID else "при получении"
    )
    lines.append(f"Итого: <b>{money(order.total)}</b> ({payment})")
    if order.comment:
        lines.append(f"Комментарий: {escape(order.comment)}")
    return "\n".join(lines)


def new_reservation_text(reservation: Reservation) -> str:
    start = timezone.localtime(reservation.start_at)
    lines = [
        "<b>Новая бронь</b>",
        f"{start:%d.%m} в {start:%H:%M}, стол №{reservation.table.number}, "
        f"гостей: {reservation.guests_count}",
        f"{escape(reservation.guest_name)}, {escape(reservation.phone)}",
    ]
    if reservation.comment:
        lines.append(f"Пожелания: {escape(reservation.comment)}")
    return "\n".join(lines)
