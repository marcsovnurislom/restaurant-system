from celery import shared_task

from apps.orders.services import order_cancel_unpaid


@shared_task
def cancel_unpaid_orders() -> int:
    """Периодическая задача (Celery Beat): автоотмена неоплаченных онлайн-заказов."""
    return order_cancel_unpaid()
