from django import template

from apps.menu.templatetags.money import money

register = template.Library()


@register.filter
def kpi_value(kpi: dict) -> str:
    """Значение плитки в нужном формате: сумы, проценты или просто число."""
    value = kpi["value"]
    if kpi["kind"] == "money":
        return money(value)
    if kpi["kind"] == "percent":
        return f"{value * 100:.1f}%"
    return f"{value:,}".replace(",", " ")
