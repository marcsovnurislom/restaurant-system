from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.exceptions import Conflict


class DomainError(Exception):
    """Нарушение бизнес-правила: понятный текст для пользователя и код для клиента API.

    Сервисы бросают DomainError и ничего не знают об HTTP. Перевод в ответ API
    делает `to_api_error`, а страницы сайта показывают `message` в форме.
    """

    # Коды, которые означают «данные верные, но ресурс сейчас занят или недоступен»
    conflict_codes: frozenset[str] = frozenset()
    # Коды, которые означают «у пользователя нет права на это действие»
    forbidden_codes: frozenset[str] = frozenset({"forbidden"})

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def to_api_error(exc: DomainError) -> Exception:
    if exc.code in exc.forbidden_codes:
        return PermissionDenied(exc.message, code=exc.code)
    if exc.code in exc.conflict_codes:
        return Conflict(exc.message, code=exc.code)
    return ValidationError({"detail": exc.message}, code=exc.code)
