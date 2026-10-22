from celery import Task
from django.db import transaction


def delay_on_commit(task: Task, *args) -> None:
    """Поставить Celery-задачу в очередь после коммита транзакции.

    До коммита воркер может взять задачу раньше, чем данные появятся в БД,
    и не найти заказ. robust=True: если брокер недоступен, запрос гостя
    не падает, ошибка уходит в лог.
    """

    def send() -> None:
        task.delay(*args)

    transaction.on_commit(send, robust=True)
