from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()

NBSP = " "


@register.filter
def money(value) -> str:
    """45000.00 -> "45 000 сум". Тийины не показываем: в ресторанах цены в целых сумах."""
    try:
        amount = Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return ""
    return f"{amount:,}".replace(",", NBSP) + f"{NBSP}сум"
