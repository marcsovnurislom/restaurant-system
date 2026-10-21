from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from apps.payments.models import Payment


@dataclass(frozen=True)
class CheckoutSession:
    external_id: str
    redirect_url: str


@dataclass(frozen=True)
class WebhookEvent:
    external_id: str
    succeeded: bool
    amount: Decimal
    raw: dict = field(default_factory=dict)


class InvalidWebhook(Exception):
    """Подпись не сошлась или тело запроса испорчено: такой webhook игнорируем."""


class PaymentProvider(ABC):
    """Общий интерфейс платёжных систем.

    Сервисы работают только с этим интерфейсом, поэтому подключить Payme или Click
    значит написать ещё один класс, не трогая логику заказов.
    """

    name: str

    @abstractmethod
    def create_checkout(
        self, *, payment: Payment, success_url: str, cancel_url: str
    ) -> CheckoutSession:
        """Создаёт страницу оплаты у провайдера и возвращает ссылку на неё."""

    @abstractmethod
    def parse_webhook(self, *, body: bytes, headers: Mapping[str, str]) -> WebhookEvent | None:
        """Проверяет подпись и разбирает уведомление.

        Возвращает None для событий, которые нас не интересуют.
        Бросает InvalidWebhook, если подпись неверна.
        """
